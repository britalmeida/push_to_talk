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
    "version": (0, 1, 0),
    "blender": (2, 83, 0),
    "location": "Video Sequence Editor",
    "description": "To Do",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/sequencer/XXX.html",
    "category": "Sequencer",
}


import bpy
from bpy.types import Operator


# Runtime state
was_playing = False
is_recording = False


def start_recording(context):
    print("start_recording")

    global is_recording
    global was_playing

    is_recording = True
    was_playing = context.screen.is_animation_playing

    if (not was_playing):
        bpy.ops.screen.animation_play()

    bpy.app.timers.register(update_animation)



def stop_recording():
    print("stop_recording")
    global was_playing
    if (not was_playing):
        bpy.ops.screen.animation_play()
    global is_recording
    is_recording = False



def update_animation():
    print("update_animation")
    global is_recording
    if (is_recording):
        bpy.ops.sequencer.push_to_test()
        return 0.02
    else:
        return None


class SEQUENCER_OT_push_to_talk(Operator):
    bl_idname = "sequencer.push_to_talk"
    bl_label = "Push to Talk"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'})
        #return (context.sequences)

    def execute(self, context):
        print("TALK")
        bpy.ops.sequencer.effect_strip_add(
            type='COLOR',
            frame_start=context.scene.frame_current,
            frame_end=80,
            channel=1,
            replace_sel=True,
            overlap=False,
            color=(0.5607842206954956, 0.21560697257518768, 0.1903851181268692)
        )
        new_strip = context.scene.sequence_editor.sequences_all['Color']
        new_strip.name = "Recording..."

        start_recording(context)

        return {'FINISHED'}

class SEQUENCER_OT_push_to_test(Operator):
    bl_idname = "sequencer.push_to_test"
    bl_label = "Push to Test"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        new_strip = context.scene.sequence_editor.sequences_all["Recording..."]
        new_strip.frame_final_end = context.scene.frame_current

        return {'FINISHED'}


class SEQUENCER_OT_finish_recording(Operator):
    bl_idname = "sequencer.finish_recording"
    bl_label = "Stop recording"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'})
        #return (context.sequences)

    def execute(self, context):
        stop_recording()

        return {'FINISHED'}



def draw_push_to_talk_button(self, context):
    layout = self.layout
    global is_recording
    print(is_recording)
    if (is_recording):
        layout.operator("sequencer.finish_recording", text="Stop recording", icon='PAUSE') #SNAP_FACE
    else:
        layout.operator("sequencer.push_to_talk", text="Push to Talk", icon='REC') #PLAY_SOUND



# Add-on Registration #########################################################

classes = (
    SEQUENCER_OT_push_to_talk,
    SEQUENCER_OT_push_to_test,
    SEQUENCER_OT_finish_recording,
)

addon_keymaps = []


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add shortcuts to the keymap.
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(
            name='Sequencer',
            space_type='SEQUENCE_EDITOR')
    kmi = km.keymap_items.new('SEQUENCER_OT_push_to_test', 'U', 'PRESS')
    addon_keymaps.append((km, kmi))

    bpy.types.SEQUENCER_HT_header.append(draw_push_to_talk_button)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Clear shortcuts from the keymap.
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
