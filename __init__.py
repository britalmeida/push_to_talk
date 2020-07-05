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
    "description": "To Do",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/sequencer/XXX.html",
    "category": "Sequencer",
}


import datetime
import os
import platform
import shlex
from string import whitespace
from subprocess import Popen, PIPE

import bpy
from bpy.types import Operator, Panel, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty


os_platform = platform.system()  # 'Linux', 'Darwin', 'Java', 'Windows'
supported_platforms = {'Linux'}



def generate_enum_items_for_sound_devices(self, context):

    # Detect existing sound cards and devices
    sound_cards = ['default']
    with Popen(args=["arecord","-L"], stdout=PIPE) as proc:
        arecord_output = proc.stdout.read()
        for line in arecord_output.splitlines():
            line = line.decode('utf-8')
            # Skip indented lines, search only for PCM names
            # TODO: show only names which are likely to be an input device
            if line.startswith(tuple(w for w in whitespace)) == False:
                sound_cards.append(line)

    enum_items = []
    for idx, sound_card in enumerate(sound_cards):
        enum_items.append((sound_card, sound_card, sound_card))

    print("generate")
    return enum_items


def save_sound_card_preference(self, context):

    addon_prefs = context.preferences.addons[__name__].preferences
    audio_device = addon_prefs.audio_input_device

    print(f"Set audio input preference to '{audio_device}' for {os_platform}")

    if os_platform == 'Linux':
        addon_prefs.audio_device_linux = audio_device
    elif os_platform == 'Darwin':
        addon_prefs.audio_device_darwin = audio_device




class SEQUENCER_OT_push_to_talk(Operator):
    bl_idname = "sequencer.push_to_talk"
    bl_label = "Start Recording"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    # Runtime state shared between instances of this operator
    should_stop = False
    is_running = False

    def __init__(self):
        self.recording_process = None
        self._timer = None
        self.was_playing = None
        self.frame_start = None


    def add_visual_feedback_strip(self, context):
        self.frame_start = context.scene.frame_current
        bpy.ops.sequencer.effect_strip_add(
            type='COLOR',
            frame_start=self.frame_start,
            frame_end=80,
            channel=1,
            replace_sel=True,
            overlap=False,
            color=(0.5607842206954956, 0.21560697257518768, 0.1903851181268692)
        )
        new_strip = context.scene.sequence_editor.sequences_all['Color']
        new_strip.name = "Recording..."

    @classmethod
    def poll(cls, context):
        return (context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'})
        #return (context.sequences)


    def generate_filename(self, context):
        addon_prefs = context.preferences.addons[__name__].preferences
        sounds_dir = bpy.path.abspath(addon_prefs.sounds_dir)
        filename = addon_prefs.prefix

        if os.path.isdir(sounds_dir) == False:
            if addon_prefs.sounds_dir == "//":
                reason = ".blend file was not saved. Can't define relative " \
                         "directory to save the sound clips"
            else:
                reason = "directory to save the sound clips does not exist"
            self.report({'ERROR'}, f"Could not record audio: {reason}")
            return False

        if os.access(sounds_dir, os.W_OK) == False:
            self.report({'ERROR'}, "Could not record audio: "
                "the directory to save the sound clips is not writable")
            return False

        timestamp = datetime.datetime.now().strftime("_%Y-%m-%d_%H-%M-%S")

        self.filepath = f"{sounds_dir}{filename}{timestamp}.wav"

        if os.path.exists(self.filepath):
            self.report({'ERROR'}, "Could not record audio: "
                "a file already exists where the sound clip would be saved")
            return False


    def start_recording(self, context):

        addon_prefs = context.preferences.addons[__name__].preferences

        framerate = context.scene.render.fps
        if os_platform == 'Linux':
            audio_input_device = addon_prefs.audio_device_linux
        elif os_platform == 'Darwin':
            audio_input_device = addon_prefs.audio_device_darwin

        ffmpeg_command = f"ffmpeg -fflags nobuffer -f alsa " \
                         f"-i {audio_input_device} " \
                         f"-t {framerate} {self.filepath}"
        args = shlex.split(ffmpeg_command)
        self.recording_process = Popen(args)
        print("recording started")


    def invoke(self, context, event):
        print("TALK - invoke")

        # If this operator is already running modal, this second invocation is
        # the toggle to stop it. Set a variable that the first modal operator
        # instance will listen to in order to terminate.
        if SEQUENCER_OT_push_to_talk.is_running:
            SEQUENCER_OT_push_to_talk.should_stop = True
            return {'FINISHED'}

        SEQUENCER_OT_push_to_talk.is_running = True

        # Generate the name to save the audio file.
        if(self.generate_filename(context) == False):
            #self.cancel(context)
            SEQUENCER_OT_push_to_talk.is_running = False
            return {'CANCELLED'}

        self.start_recording(context)

        self.add_visual_feedback_strip(context)

        # Ensure that the timeline is playing
        self.was_playing = context.screen.is_animation_playing
        if self.was_playing == False:
            bpy.ops.screen.animation_play()

        # Start this operator as modal
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


    def modal(self, context, event):

        # Cancel. Delete the current recording.
        if event.type in {'ESC'}:
            print("modal - cancel")
            self.cancel(context)
            return {'CANCELLED'}

        # Confirm. Delete the current recording.
        if event.type in {'RET'}:
            print("modal - confirm")
            return self.execute(context)

        # Periodic update
        if event.type == 'TIMER':

            # Listen for signal to stop
            if SEQUENCER_OT_push_to_talk.should_stop:
                return self.execute(context)
            # Stop if the timeline was paused
            if context.screen.is_animation_playing == False:
                self.was_playing = True
                return self.execute(context)
            # Stop if the timeline looped around
            if context.scene.frame_current < self.frame_start:
                return self.execute(context)

            # Draw
            sequence_ed = context.scene.sequence_editor
            color_strip = sequence_ed.sequences_all["Recording..."]
            color_strip.frame_final_end = context.scene.frame_current

        return {'PASS_THROUGH'}


    def on_cancel_or_finish(self, context):
        print("restore_playing_state")

        if self.recording_process:
            self.recording_process.terminate()

        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)

        SEQUENCER_OT_push_to_talk.is_running = False
        SEQUENCER_OT_push_to_talk.should_stop = False

        if not self.was_playing:
            bpy.ops.screen.animation_play()


    def execute(self, context):
        print("TALK - execute")

        self.on_cancel_or_finish(context)

        sequence_ed = context.scene.sequence_editor
        addon_prefs = context.preferences.addons[__name__].preferences

        # Gather the position information from the dummy strip and delete it.
        color_strip = sequence_ed.sequences_all["Recording..."]
        channel = color_strip.channel
        frame_start = color_strip.frame_final_start
        bpy.ops.sequencer.delete()

        # Create a new sound strip in the place of the dummy strip
        name = addon_prefs.prefix
        sound_strip = sequence_ed.sequences.new_sound(
            name, self.filepath, channel, frame_start
        )

        return {'FINISHED'}


    def cancel(self, context):
        print("TALK - cancel")

        self.on_cancel_or_finish(context)
        bpy.ops.sequencer.delete()


# UI ##########################################################################

def draw_push_to_talk_button(self, context):
    layout = self.layout
    layout.enabled = os_platform in supported_platforms

    if SEQUENCER_OT_push_to_talk.is_running:
        # 'SNAP_FACE' is used because it looks like 'STOP', which was removed.
        layout.operator("sequencer.push_to_talk",
                        text="Stop Recording", icon='SNAP_FACE')
    else:
        layout.operator("sequencer.push_to_talk",
                        text="Start Recording", icon='REC')


class SEQUENCER_PT_push_to_talk(Panel):
    bl_label = "Configuration"
    bl_category = "Push To Talk"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @staticmethod
    def has_sequencer(context):
        return (context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'})

    @classmethod
    def poll(cls, context):
        return cls.has_sequencer(context) and context.scene.sequence_editor

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        if os_platform not in supported_platforms:
            layout.label(
                text=f"Recording on {os_platform} is not supported",
                icon='ERROR'
            )
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
        if prefs.use_preferences_save == False:
            col.separator()
            col.operator(
                "wm.save_userpref",
                text=f"Save Preferences{' *' if prefs.is_dirty else ''}",
            )


# Settings ####################################################################


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
        description="If automatic detection of the sound card fails, " \
                    "manually insert a value given by 'arecord -L'",
        default="sysdefault"
    )
    audio_device_darwin: StringProperty(
        name="Audio Input Device (macOS)",
        description="Hardware slot of the audio input device given " \
                    "by \"arecord -l\"",
        default="sysdefault"
    )
    audio_input_device: EnumProperty(
        items=generate_enum_items_for_sound_devices,
        name="Sound Card",
        description="Sound card to be used, from the ones found on this computer",
        #default="",
        options={'SKIP_SAVE'},
        update=save_sound_card_preference,
    )


# Add-on Registration #########################################################

classes = (
    SEQUENCER_OT_push_to_talk,
    SEQUENCER_PT_push_to_talk,
    SEQUENCER_PushToTalk_Preferences,
)


def register():
    print("-----------------Registering Push to Talk-------------------------")

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_HT_header.append(draw_push_to_talk_button)

    print("-----------------Done Registering----------------------------------")


def unregister():

    print("-----------------Unregistering Push to Talk------------------------")

    bpy.types.SEQUENCER_HT_header.remove(draw_push_to_talk_button)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    print("-----------------Done Unregistering--------------------------------")


if __name__ == "__main__":
    register()
