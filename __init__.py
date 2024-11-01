# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

bl_info = {
    "name": "Push To Talk",
    "author": "Inês Almeida, Francesco Siddi",
    "version": (0, 4, 0),
    "blender": (3, 3, 0),
    "location": "Video Sequence Editor",
    "description": "Convenient recording of scratch dialog for an edit",
    "doc_url": "https://github.com/britalmeida/blender_addon_push_to_talk",
    "category": "Sequencer",
}


import datetime
import logging
import os
import platform
import re
import shlex
import shutil
import time

from string import whitespace
from subprocess import Popen, PIPE, TimeoutExpired

import bpy
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, Panel, AddonPreferences


log = logging.getLogger(__name__)
os_platform = platform.system()  # 'Linux', 'Darwin', 'Java', 'Windows'
supported_platforms = {'Linux', 'Darwin', 'Windows'}
ffmpeg_exe_path = shutil.which("ffmpeg")
NO_DEVICE = "no audio device found"


# Audio Device Configuration #######################################################################


def get_audio_devices_list_linux():
    """Get list of audio devices on Linux."""

    # Get named devices using ALSA and arecord.
    arecord_exe_path = shutil.which("arecord")
    if not arecord_exe_path:
        return []

    sound_cards = []
    with Popen(args=[arecord_exe_path, "-L"], stdout=PIPE) as proc:
        arecord_output = proc.stdout.read()
        for line in arecord_output.splitlines():
            line = line.decode('utf-8')

            # Skip indented lines, search only for PCM names
            if line.startswith(tuple(w for w in whitespace)) == False:
                # Show only names which are likely to be an input device.
                # Skip names that are known to be something else.
                if not (
                    line in ["null", "oss", "pulse", "speex"]
                    or line.startswith(("surround", "usbstream", "front"))
                    or line.endswith(("rate", "mix", "snoop"))
                ):
                    # Found one!
                    sound_cards.append(line)

    return sound_cards


def get_audio_devices_list_darwin():
    """Get list of audio devices on macOS."""

    if not ffmpeg_exe_path:
        return []
    ffmpeg_args = "-f avfoundation -list_devices true -hide_banner -i dummy"
    args = [ffmpeg_exe_path] + shlex.split(ffmpeg_args)

    av_device_lines = []
    with Popen(args=args, stdout=PIPE, stderr=PIPE) as proc:
        command_output = proc.stderr.read()
        for line in command_output.splitlines():
            line = line.decode('utf-8')

            if line.startswith("[AVFoundation"):
                av_device_lines.append(line)

    sound_cards = []

    # Strip video devices from list
    include_entries = False
    for av_device_line in av_device_lines:
        if 'AVFoundation video devices:' in av_device_line:
            include_entries = False
        elif 'AVFoundation audio devices:' in av_device_line:
            include_entries = True
        # When in the "audio devices" part of the list, include entries.
        elif include_entries:
            sound_cards.append(av_device_line)

    # Parse the remaining items so they go from:
    # [AVFoundation input device @ 0x7f9c0a604340] [0] Unknown USB Audio Device
    # to:
    # Unknown USB Audio Device"
    pattern = r'\[.*?\]'
    sound_cards = [re.sub(pattern, '', sound_card).strip() for sound_card in sound_cards]
    # Important: we assume that the device number (e.g. [0]) matches the order
    # of the device in the list. This is used to build the ffmpeg command in
    # the start_recording function.
    return sound_cards


def get_audio_devices_list_windows():
    """Get list of audio devices on Windows."""

    if not ffmpeg_exe_path:
        return []
    ffmpeg_args = "-f dshow -list_devices true -hide_banner -i dummy"
    args = [ffmpeg_exe_path] + shlex.split(ffmpeg_args)

    # dshow list_devices may output either individual devices tagged with '(audio)', e.g.:
    # [dshow @ 00000137146e4800] "Microphone (HD Pro Webcam)" (audio)
    # or all audio devices grouped after a 'DirectShow audio devices' heading, e.g.:
    # [dshow @ 02cec400] DirectShow audio devices
    # [dshow @ 02cec400]  "Desktop Microphone (3- Studio -"
    # [dshow @ 02cec400]     Alternative name "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\Desktop Microphone (3- Studio -"
    grouped_output_version = False

    av_device_lines = []
    with Popen(args=args, stdout=PIPE, stderr=PIPE) as proc:
        command_output = proc.stderr.read()
        for line in command_output.splitlines():
            line = line.decode('utf-8')

            # Start by optimistically adding all (audio) lines, regardless of mode.
            # What could possibly go wrong? right?
            if line.endswith("(audio)"):
                av_device_lines.append(line)
            # If at some point we find the audio header, we switch mode.
            elif "DirectShow audio devices" in line:
                grouped_output_version = True
            # In grouped mode, add lines that should have device names (skip input file errors).
            elif grouped_output_version:
                if "Alternative name" not in line and "Error" not in line:
                    av_device_lines.append(line)

    # Extract the device names from the lines.
    sound_cards = []
    pattern = r'\[.*?\]'
    for av_device_line in av_device_lines:
        names_within_quotes = re.findall(r'"(.+?)"', av_device_line)
        if len(names_within_quotes) == 1:
            sound_cards.append(names_within_quotes[0])
        else:
            # Keep it for the user to see, it might help them figure out their audio setup.
            sound_cards.append(f"error parsing entry '{av_device_line}'")

    return sound_cards


def populate_enum_items_for_sound_devices(self, context):
    """Query the system for available audio devices and populate enum items."""

    # Re-use the existing enum values if they weren't generated too long ago.
    # Note: this generate function is called often, on draw of the UI element
    # that renders the enum property and per each enum item when the dropdown
    # is expanded.
    # To avoid bogging down the UI render pass, we avoid calling this function
    # too often, but we still want to call it occasionally, in case the user
    # plugs in a new audio device while Blender is running.
    try:
        last_executed = populate_enum_items_for_sound_devices.last_executed
        if (time.time() - last_executed) < 5:  # seconds
            return populate_enum_items_for_sound_devices.enum_items
    except AttributeError:
        # First time that the enum is being generated.
        pass

    log.debug("Polling system sound cards to update audio input drop-down")

    # Detect existing sound cards and devices
    if os_platform == 'Linux':
        sound_cards = get_audio_devices_list_linux()
    elif os_platform == 'Darwin':
        sound_cards = get_audio_devices_list_darwin()
    elif os_platform == 'Windows':
        sound_cards = get_audio_devices_list_windows()

    if not sound_cards:
        sound_cards = [NO_DEVICE]

    # Generate items to show in the enum dropdown.
    # TODO: get_audio_devices functions could return the full tuple instead, e.g.:
    # linux: [("sysdefault:CARD=PCH", "HDA Intel PCH, ALC269VC Analog", "Default Audio Device")]
    # macOS: [(0, "Unknown USB Audio Device", "Unknown USB Audio Device")]
    enum_items = []
    for idx, sound_card in enumerate(sound_cards):
        enum_items.append((sound_card, sound_card, sound_card))

    # Update the cached enum items and the generation timestamp
    populate_enum_items_for_sound_devices.enum_items = enum_items
    populate_enum_items_for_sound_devices.last_executed = time.time()

    log.debug(f"Scanned & found sound devices: {populate_enum_items_for_sound_devices.enum_items}")
    return populate_enum_items_for_sound_devices.enum_items


def save_sound_card_preference(self, context):
    """Sync the chosen audio device to the user preferences.

    Called when the enum property is set.
    Sync the chosen audio device from the UI enum to the persisted user
    preferences according to the current OS.
    """

    addon_prefs = context.preferences.addons[__name__].preferences
    audio_device = addon_prefs.audio_input_device

    log.debug(f"Set audio input preference to '{audio_device}' for {os_platform}")

    if os_platform == 'Linux':
        addon_prefs.audio_device_linux = audio_device
    elif os_platform == 'Darwin':
        addon_prefs.audio_device_darwin = audio_device
    elif os_platform == 'Windows':
        addon_prefs.audio_device_windows = audio_device


# Operator #########################################################################################


class SEQUENCER_OT_push_to_talk(Operator):
    bl_idname = "sequencer.push_to_talk"
    bl_label = "Start Recording"
    bl_description = "Add a sound strip with audio recorded from the microphone"
    bl_options = {'UNDO', 'REGISTER'}

    # Runtime state shared between instances of this operator
    should_stop = False
    is_running = False
    visual_feedback_strip = None
    strip_channel = 1

    def __init__(self):
        self.recording_process = None
        self._timer = None
        self.was_playing = None
        self.frame_start = None

    def add_visual_feedback_strip(self, context):
        """Add a color strip to mark the current progress of the recording."""

        scene = context.scene
        self.frame_start = scene.frame_current

        strip = scene.sequence_editor.sequences.new_effect(
            name="Recording...",
            type='COLOR',
            channel=1,
            frame_start=self.frame_start,
            frame_end=self.frame_start + 1,
        )
        strip.color = (0.5607842206954956, 0.21560697257518768, 0.1903851181268692)
        strip.blend_alpha = 0.0

        SEQUENCER_OT_push_to_talk.visual_feedback_strip = strip

    @classmethod
    def poll(cls, context):
        if os_platform not in supported_platforms:
            cls.poll_message_set(f"recording not supported on {os_platform}")
            return False

        if not ffmpeg_exe_path:
            cls.poll_message_set("ffmpeg not found separately installed")
            return False

        addon_prefs = context.preferences.addons[__name__].preferences
        if addon_prefs.audio_input_device == NO_DEVICE:
            cls.poll_message_set("no audio device found. Is there a microphone plugged in?")
            return False

        # This operator is available only in the sequencer area of the sequence editor.
        return context.space_data.type == 'SEQUENCE_EDITOR' and (
            context.space_data.view_type == 'SEQUENCER'
            or context.space_data.view_type == 'SEQUENCER_PREVIEW'
        )

    def generate_filename(self, context) -> bool:
        """Check filename availability for the sound file."""

        addon_prefs = context.preferences.addons[__name__].preferences

        # Resolve possible paths relative to the blend file to a system path
        sounds_dir_sys = bpy.path.abspath(addon_prefs.sounds_dir)
        if not os.path.isdir(sounds_dir_sys):
            if bpy.path.abspath('//') == '':
                reason = ".blend file needs to be saved so the sound clips go in the same directory"
            else:
                reason = f"directory to save the sound clips does not exist: '{sounds_dir_sys}'"
            self.report({'ERROR'}, f"Could not record audio: {reason}")
            return False

        if not os.access(sounds_dir_sys, os.W_OK):
            self.report(
                {'ERROR'},
                "Could not record audio: the directory to save the sound clips is not writable",
            )
            return False

        timestamp = datetime.datetime.now().strftime("_%Y-%m-%d_%H-%M-%S")

        self.filepath = f"{sounds_dir_sys}{addon_prefs.prefix}{timestamp}.wav"

        if os.path.exists(self.filepath):
            self.report(
                {'ERROR'},
                (
                    f"Could not record audio: ",
                    f"a file already exists where the sound clip would be saved: {self.filepath}",
                ),
            )
            return False

        return True

    def start_recording(self, context) -> bool:
        """Start a process to record audio."""

        assert ffmpeg_exe_path and os_platform in supported_platforms  # poll() should have failed

        addon_prefs = context.preferences.addons[__name__].preferences
        audio_device = addon_prefs.audio_input_device

        # macOS uses an index, eg.: '0', but the enum stores a more meaningful identifier string
        # for resilience with devices being (un)plugged at runtime and between Blender runs.
        if os_platform == 'Darwin':
            device_idx = 0
            for idx, enum_item in enumerate(populate_enum_items_for_sound_devices.enum_items):
                if enum_item[1] == audio_device:
                    audio_device = idx
                    break

        # Set platform dependent arguments.
        if os_platform == 'Linux':
            ffmpeg_command = f'-f alsa -i "{audio_device}"'
        elif os_platform == 'Darwin':
            ffmpeg_command = f'-f avfoundation -i ":{audio_device}"'
        elif os_platform == 'Windows':
            ffmpeg_command = f'-f dshow -i audio="{audio_device}"'

        # This block size command tells ffmpeg to use a small blocksize and save the output to disk ASAP
        file_block_size = "-blocksize 2048 -flush_packets 1"

        # Run the ffmpeg command.
        ffmpeg_command += f' {file_block_size} "{self.filepath}"'
        args = [ffmpeg_exe_path] + shlex.split(ffmpeg_command)
        self.recording_process = Popen(args)

        log.debug("PushToTalk: Started audio recording process")
        log.debug(f"PushToTalk: {ffmpeg_exe_path} {ffmpeg_command}")
        return True

    def invoke(self, context, event):
        """Called when this operator is starting."""

        log.debug("PushToTalk: invoke")

        # If this operator is already running modal, this second invocation is
        # the toggle to stop it. Set a variable that the first modal operator
        # instance will listen to in order to terminate.
        if SEQUENCER_OT_push_to_talk.is_running:
            SEQUENCER_OT_push_to_talk.should_stop = True
            return {'FINISHED'}

        SEQUENCER_OT_push_to_talk.is_running = True

        # Generate the name to save the audio file.
        if not self.generate_filename(context):
            SEQUENCER_OT_push_to_talk.is_running = False
            return {'CANCELLED'}

        if not self.start_recording(context):
            SEQUENCER_OT_push_to_talk.is_running = False
            return {'CANCELLED'}

        self.add_visual_feedback_strip(context)

        # Ensure that the timeline is playing
        self.was_playing = context.screen.is_animation_playing
        if not self.was_playing:
            bpy.ops.screen.animation_play()

        # Start this operator as modal
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Periodic update to draw and check if this operator should stop."""

        # Cancel. Delete the current recording.
        if event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        # Confirm. Create a strip with the current recording.
        if event.type in {'RET'}:
            return self.execute(context)

        # Periodic update
        if event.type == 'TIMER':
            # Listen for signal to stop
            if SEQUENCER_OT_push_to_talk.should_stop:
                return self.execute(context)
            # Stop if the timeline was paused
            if not context.screen.is_animation_playing:
                self.was_playing = True
                return self.execute(context)
            # Stop if the timeline looped around
            if context.scene.frame_current < self.frame_start:
                return self.execute(context)
            # Stop if the user deletes the visual feedback strip
            color_strip = SEQUENCER_OT_push_to_talk.visual_feedback_strip
            if not color_strip:
                return self.cancel(context)

        # Don't consume the input, otherwise it is impossible to click the stop button.
        return {'PASS_THROUGH'}

    def on_cancel_or_finish(self, context):
        """Called when this operator is finishing (confirm) or got canceled."""

        # Unregister from the periodic modal calls.
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)

        # Restore the play state (stop it if it wasn't running).
        # Do this before terminating the recording so that the new sound strip doesn't look shorter
        # than the playhead position which would continue while waiting for ffmpeg to finish.
        if not self.was_playing:
            bpy.ops.screen.animation_play()

        # Finish the sound recording process.
        if self.recording_process:
            self.recording_process.terminate()
            # The maximum amount of time for us to wait for ffmpeg to shutdown in seconds
            maximum_shutdown_wait_time = 3
            try:
                # Wait for ffmpeg to exit until we try to read the saved audio file.
                self.recording_process.wait(maximum_shutdown_wait_time)
            except TimeoutExpired:
                log.warning(
                    "ffmpeg did not gracefully shutdown within "
                    f"{maximum_shutdown_wait_time} seconds."
                )

        # Remove the temporary visual feedback strip.
        color_strip = SEQUENCER_OT_push_to_talk.visual_feedback_strip
        if color_strip and color_strip.name:
            SEQUENCER_OT_push_to_talk.visual_feedback_strip = None
            sequence_ed = context.scene.sequence_editor
            sequence_ed.sequences.remove(color_strip)

        # Update this operator's state.
        SEQUENCER_OT_push_to_talk.is_running = False
        SEQUENCER_OT_push_to_talk.should_stop = False

    def execute(self, context):
        """Called to finish this operator's action.

        Create the sound strip with the finished audio recording.
        """

        log.debug("PushToTalk: execute")

        # Cleanup execution state
        self.on_cancel_or_finish(context)

        sequence_ed = context.scene.sequence_editor
        addon_prefs = context.preferences.addons[__name__].preferences

        # Create a new sound strip in the place of the dummy strip.
        name = addon_prefs.prefix
        sound_strip = sequence_ed.sequences.new_sound(
            name, self.filepath, self.strip_channel, self.frame_start
        )

        return {'FINISHED'}

    def cancel(self, context):
        """Cleanup temporary state if canceling during modal execution."""

        log.debug("PushToTalk: cancel")

        # Cleanup execution state
        self.on_cancel_or_finish(context)

        # If the timeline wasn't playing, restore the playhead to the original position.
        if not self.was_playing:
            scene = context.scene
            scene.frame_current = self.frame_start

        return {'CANCELLED'}

    @classmethod
    def update_on_main_thread(cls):
        """Ticks even when the operator is not running. Needed to safely access the color strip."""

        delta_s = 0.05  # Update frequency

        color_strip = SEQUENCER_OT_push_to_talk.visual_feedback_strip

        # If the color_strip is None, the operator isn't running. Nothing to do.
        if not color_strip:
            return delta_s

        # Check if the color strip got deleted by Blender. Signal the operator to stop.
        if not color_strip.name:
            # Cleanly set our reference to None, which can be checked in modal().
            # Accessing the strip directly in modal() is not thread safe.
            SEQUENCER_OT_push_to_talk.visual_feedback_strip = None
            return delta_s

        # Increase the visual feedback strip's size.
        color_strip.frame_final_end = bpy.context.scene.frame_current

        # Keep track of the current channel for the recorded strip.
        # In case the color strip gets deleted, we have up to date info.
        SEQUENCER_OT_push_to_talk.strip_channel = color_strip.channel

        return delta_s


# UI ###############################################################################################


def draw_push_to_talk_button(self, context):
    # Show only in the sequencer area (not on the preview area).
    if (
        context.space_data.view_type != 'SEQUENCER'
        and context.space_data.view_type != 'SEQUENCER_PREVIEW'
    ):
        return

    layout = self.layout
    if SEQUENCER_OT_push_to_talk.is_running:
        # 'SNAP_FACE' is used because it looks like 'STOP', which was removed.
        layout.operator("sequencer.push_to_talk", text="Stop Recording", icon='SNAP_FACE')
    else:
        layout.operator("sequencer.push_to_talk", text="Start Recording", icon='REC')


class SEQUENCER_PT_push_to_talk(Panel):
    bl_label = "Configuration"
    bl_category = "Push To Talk"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        # Show this panel only in the sequence editor in the right-side panel
        # of the sequencer area (not on the preview area).
        return context.space_data.type == 'SEQUENCE_EDITOR' and (
            context.space_data.view_type == 'SEQUENCER'
            or context.space_data.view_type == 'SEQUENCER_PREVIEW'
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        problem_found = ""
        if os_platform not in supported_platforms:
            problem_found = f"Recording on {os_platform} is not supported"
        elif not ffmpeg_exe_path:
            problem_found = "ffmpeg not found separately installed"

        col = layout.column()
        if problem_found:
            col.label(text=problem_found, icon='ERROR')
            col = col.column()
            col.enabled = False

        addon_prefs = context.preferences.addons[__name__].preferences

        col.prop(addon_prefs, "prefix")
        col.prop(addon_prefs, "sounds_dir")

        col.separator()
        col.prop(addon_prefs, "audio_input_device")
        # DEBUG
        # col.prop(addon_prefs, "audio_device_linux", text="(linux Debug)")
        # col.prop(addon_prefs, "audio_device_darwin", text="(macOS Debug)")
        # col.prop(addon_prefs, "audio_device_windows", text="(Win Debug)")

        # Show a save button for the user preferences if they aren't automatically saved.
        prefs = context.preferences
        if not prefs.use_preferences_save:
            col.separator()
            col.operator(
                "wm.save_userpref",
                text=f"Save Preferences{' *' if prefs.is_dirty else ''}",
            )


# Settings #########################################################################################


class SEQUENCER_PushToTalk_Preferences(AddonPreferences):
    bl_idname = __name__

    prefix: StringProperty(
        name="Prefix",
        description="A label to name the created sound strips and files",
        default="temp_dialog",
    )
    sounds_dir: StringProperty(
        name="Sounds",
        description="Directory where to save the generated audio files",
        default="//",
        subtype="FILE_PATH",
    )
    # Explicitly save an audio configuration per platform in case the same user uses Blender in
    # different platforms and syncs user settings.
    audio_device_linux: StringProperty(
        name="Audio Input Device (Linux)",
        description="Hardware slot of the audio input device given by 'arecord -L'",
        default="default",
    )
    audio_device_darwin: StringProperty(
        name="Audio Input Device (macOS)",
        description="Hardware slot of the audio input device given by 'ffmpeg'",
        default="setting not synced yet",
    )
    audio_device_windows: StringProperty(
        name="Audio Input Device (Windows)",
        description="Hardware slot of the audio input device given by 'ffmpeg'",
        default="setting not synced yet",
    )
    # The runtime audio device, depending on platform.
    audio_input_device: EnumProperty(
        items=populate_enum_items_for_sound_devices,
        name="Audio Input",
        description="Audio input device to be used, from the ones found on this computer",
        options={'SKIP_SAVE'},
        update=save_sound_card_preference,
    )


# Add-on Registration #############################################################################

classes = (
    SEQUENCER_OT_push_to_talk,
    SEQUENCER_PT_push_to_talk,
    SEQUENCER_PushToTalk_Preferences,
)


def register():
    log.debug("--------Registering Push to Talk---------------------")

    # Log warnings and continue without raising errors.
    # This add-on should keep on functioning and gracefully disable the interface for recording.
    if os_platform not in supported_platforms:
        log.warning(
            f"PushToTalk add-on is not supported on {os_platform}. Recording will not work."
        )
    if not ffmpeg_exe_path:
        log.warning(
            f"PushToTalk add-on could not find ffmpeg separately installed. Recording will not work."
        )

    # Register as normal.
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_HT_header.append(draw_push_to_talk_button)

    bpy.app.timers.register(
        SEQUENCER_OT_push_to_talk.update_on_main_thread, persistent=True
    )  # Keep timer running across file loads

    # Sync system detected audio devices with the saved preferences
    addon_prefs = bpy.context.preferences.addons[__name__].preferences
    prop_rna = addon_prefs.rna_type.properties['audio_input_device']
    audio_input_devices = {
        'Linux': addon_prefs.audio_device_linux,
        'Darwin': addon_prefs.audio_device_darwin,
        'Windows': addon_prefs.audio_device_windows,
    }
    saved_setting_value = audio_input_devices[os_platform]

    audio_devices_found = populate_enum_items_for_sound_devices(prop_rna, bpy.context)
    assert audio_devices_found  # Should always have an option also when no device is found.

    found_preferred_mic = False
    for enum_item in audio_devices_found:
        if enum_item[1] == saved_setting_value:
            found_preferred_mic = True
            break

    if found_preferred_mic:
        # Set the runtime setting to the user setting.
        addon_prefs.audio_input_device = saved_setting_value
    else:
        # Set the runtime setting to the first audio device.
        # This will also update the user setting via the enum's update function.
        addon_prefs.audio_input_device = audio_devices_found[0][0]
        # Log if the user setting got lost.
        if saved_setting_value != "setting not synced yet":
            log.info(
                f"Could not restore audio device user preference: "
                f"'{saved_setting_value}'. This can happen if the preferred audio device "
                f"is not currently connected."
            )

    log.debug("--------Done Registering-----------------------------")


def unregister():
    log.debug("--------Unregistering Push to Talk-------------------")

    if bpy.app.timers.is_registered(SEQUENCER_OT_push_to_talk.update_on_main_thread):
        bpy.app.timers.unregister(SEQUENCER_OT_push_to_talk.update_on_main_thread)

    bpy.types.SEQUENCER_HT_header.remove(draw_push_to_talk_button)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    log.debug("--------Done Unregistering---------------------------")


if __name__ == "__main__":
    register()
