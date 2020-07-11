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
    "version": (0, 2, 0),
    "blender": (2, 83, 0),
    "location": "Video Sequence Editor",
    "description": "Convenient recording of scratch dialog for an edit",
    "doc_url": "https://github.com/britalmeida/blender_addon_push_to_talk",
    "category": "Sequencer",
}


import datetime
import logging
import os
import platform
import shlex
import time

from string import whitespace
from subprocess import Popen, PIPE

import bpy
from bpy.types import Operator, Panel, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty


log = logging.getLogger(__name__)
os_platform = platform.system()  # 'Linux', 'Darwin', 'Java', 'Windows'
supported_platforms = {'Linux'}


# Audio Device Configuration #######################################################################


def populate_enum_items_for_sound_devices(self, context):
    """Query the system for available audio devices and populate enum items."""

    if os_platform not in supported_platforms:
        return []

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
    sound_cards = ['default']
    with Popen(args=["arecord", "-L"], stdout=PIPE) as proc:
        arecord_output = proc.stdout.read()
        for line in arecord_output.splitlines():
            line = line.decode('utf-8')
            # Skip indented lines, search only for PCM names
            # TODO: show only names which are likely to be an input device
            if line.startswith(tuple(w for w in whitespace)) == False:
                sound_cards.append(line)

    # Generate items to show in the enum dropdown
    enum_items = []
    for idx, sound_card in enumerate(sound_cards):
        enum_items.append((sound_card, sound_card, sound_card))

    # Update the cached enum items and the generation timestamp
    populate_enum_items_for_sound_devices.enum_items = enum_items
    populate_enum_items_for_sound_devices.last_executed = time.time()

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


# Operator #########################################################################################


class SEQUENCER_OT_push_to_talk(Operator):
    bl_idname = "sequencer.push_to_talk"
    bl_label = "Start Recording"
    bl_description = "Add a sound strip with audio recorded from the microphone"
    bl_options = {'UNDO', 'REGISTER'}

    # Runtime state shared between instances of this operator
    should_stop = False
    is_running = False

    def __init__(self):
        self.recording_process = None
        self._timer = None
        self.was_playing = None
        self.frame_start = None
        self.visual_feedback_strip = None

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

        self.visual_feedback_strip = strip

    @classmethod
    def poll(cls, context):
        # This operator is available only in the sequencer area of the
        # sequence editor.
        return (
            context.space_data.type == 'SEQUENCE_EDITOR'
            and context.space_data.view_type == 'SEQUENCER'
        )

    def generate_filename(self, context) -> bool:
        """Check filename availability for the sound file."""

        addon_prefs = context.preferences.addons[__name__].preferences
        sounds_dir = bpy.path.abspath(addon_prefs.sounds_dir)
        filename = addon_prefs.prefix

        if not os.path.isdir(sounds_dir):
            if addon_prefs.sounds_dir == "//":
                reason = (
                    ".blend file was not saved. Can't define relative "
                    "directory to save the sound clips"
                )
            else:
                reason = "directory to save the sound clips does not exist"
            self.report({'ERROR'}, f"Could not record audio: {reason}")
            return False

        if not os.access(sounds_dir, os.W_OK):
            self.report(
                {'ERROR'},
                "Could not record audio: the directory to save the sound clips is not writable",
            )
            return False

        timestamp = datetime.datetime.now().strftime("_%Y-%m-%d_%H-%M-%S")

        self.filepath = f"{sounds_dir}{filename}{timestamp}.wav"

        if os.path.exists(self.filepath):
            self.report(
                {'ERROR'},
                "Could not record audio: a file already exists where the sound clip would be saved",
            )
            return False

        return True

    def start_recording(self, context) -> bool:
        """Start a process to record audio."""

        addon_prefs = context.preferences.addons[__name__].preferences

        framerate = context.scene.render.fps
        if os_platform == 'Linux':
            audio_input_device = addon_prefs.audio_device_linux
        elif os_platform == 'Darwin':
            audio_input_device = addon_prefs.audio_device_darwin

        ffmpeg_command = (
            f"ffmpeg -fflags nobuffer -f alsa "
            f"-i {audio_input_device} "
            f"-t {framerate} {self.filepath}"
        )
        args = shlex.split(ffmpeg_command)
        self.recording_process = Popen(args)

        log.debug("PushToTalk: Started audio recording process")
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

            # Draw
            color_strip = self.visual_feedback_strip
            color_strip.frame_final_end = context.scene.frame_current

        # Don't consume the input, otherwise it is impossible to click the
        # stop button.
        return {'PASS_THROUGH'}

    def on_cancel_or_finish(self, context):
        """Called when this operator is finishing (confirm) or got canceled."""

        # Finish the sound recording process.
        if self.recording_process:
            self.recording_process.terminate()

        # Unregister from the periodic modal calls.
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)

        # Update this operator's state.
        SEQUENCER_OT_push_to_talk.is_running = False
        SEQUENCER_OT_push_to_talk.should_stop = False

        # Restore the play state (stop it if it wasn't running).
        if not self.was_playing:
            bpy.ops.screen.animation_play()

    def execute(self, context):
        """Called to finish this operator's action.

        Create the sound strip with the finished audio recording.
        """

        log.debug("PushToTalk: execute")

        # Cleanup execution state
        self.on_cancel_or_finish(context)

        sequence_ed = context.scene.sequence_editor
        addon_prefs = context.preferences.addons[__name__].preferences

        # Gather the position information from the dummy strip and delete it.
        color_strip = self.visual_feedback_strip
        if color_strip:
            channel = color_strip.channel
            frame_start = color_strip.frame_final_start
            sequence_ed.sequences.remove(color_strip)

        # Create a new sound strip in the place of the dummy strip.
        name = addon_prefs.prefix
        sound_strip = sequence_ed.sequences.new_sound(name, self.filepath, channel, frame_start)

        return {'FINISHED'}

    def cancel(self, context):
        """Cleanup temporary state if canceling during modal execution."""

        log.debug("PushToTalk: cancel")

        # Cleanup execution state
        self.on_cancel_or_finish(context)

        # Remove the temporary visual feedback strip.
        color_strip = self.visual_feedback_strip
        if color_strip:
            sequence_ed = context.scene.sequence_editor
            sequence_ed.sequences.remove(color_strip)


# UI ###############################################################################################


def draw_push_to_talk_button(self, context):
    layout = self.layout
    layout.enabled = os_platform in supported_platforms

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
        return (
            context.space_data.type == 'SEQUENCE_EDITOR'
            and context.space_data.view_type == 'SEQUENCER'
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        if os_platform not in supported_platforms:
            layout.label(text=f"Recording on {os_platform} is not supported", icon='ERROR')
            return

        addon_prefs = context.preferences.addons[__name__].preferences

        col = layout.column()
        col.prop(addon_prefs, "prefix")
        col.prop(addon_prefs, "sounds_dir")

        col.separator()
        col.prop(addon_prefs, "audio_input_device")
        # DEBUG
        if os_platform == 'Linux':
            col.prop(addon_prefs, "audio_device_linux", text="(Debug)")

        # Show a save button for the user preferences if they aren't
        # automatically saved.
        prefs = context.preferences
        if not prefs.use_preferences_save:
            col.separator()
            col.operator(
                "wm.save_userpref", text=f"Save Preferences{' *' if prefs.is_dirty else ''}",
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
        default="",
        subtype="FILE_PATH",
    )
    audio_device_linux: StringProperty(
        name="Audio Input Device (Linux)",
        description="If automatic detection of the sound card fails, "
        "manually insert a value given by 'arecord -L'",
        default="default",
    )
    audio_device_darwin: StringProperty(
        name="Audio Input Device (macOS)",
        description="Hardware slot of the audio input device given by 'arecord -l'",
        default="default",
    )
    audio_input_device: EnumProperty(
        items=populate_enum_items_for_sound_devices,
        name="Sound Card",
        description="Sound card to be used, from the ones found on this computer",
        options={'SKIP_SAVE'},
        update=save_sound_card_preference,
    )


# Add-on Registration ##############################################################################

classes = (
    SEQUENCER_OT_push_to_talk,
    SEQUENCER_PT_push_to_talk,
    SEQUENCER_PushToTalk_Preferences,
)


def register():
    log.debug("-----------------Registering Push to Talk-------------------------")

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_HT_header.append(draw_push_to_talk_button)

    # Sync system detected audio devices with the saved preferences
    addon_prefs = bpy.context.preferences.addons[__name__].preferences
    audio_input_devices = {
        'Linux': addon_prefs.audio_device_linux,
        'Darwin': addon_prefs.audio_device_darwin,
    }
    if audio_input_devices[os_platform] not in addon_prefs.audio_input_device:
        audio_input_devices[os_platform] = "default"
    else:
        addon_prefs.audio_input_device = audio_input_devices[os_platform]

    log.debug("-----------------Done Registering---------------------------------")


def unregister():

    log.debug("-----------------Unregistering Push to Talk-----------------------")

    bpy.types.SEQUENCER_HT_header.remove(draw_push_to_talk_button)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    log.debug("-----------------Done Unregistering--------------------------------")


if __name__ == "__main__":
    register()
