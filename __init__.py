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
from bpy.props import BoolProperty


class SEQUENCER_OT_push_to_talk(Operator):
    bl_idname = "sequencer.push_to_talk"
    bl_label = "Start Recording"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    # Runtime state
    was_playing: BoolProperty()


    def restore_playing_state(self, context):
        print("restore_playing_state")
        context.window_manager.push_to_talk_is_active = False
        if (not self.was_playing):
            bpy.ops.screen.animation_play()


    def __init__(self):
        print("Start")

    def __del__(self):
        print("End")

    @classmethod
    def poll(cls, context):
        return (context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'})
        #return (context.sequences)


    def invoke(self, context, event):
        print("TALK - invoke")

        context.window_manager.push_to_talk_is_active = True

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

        self.was_playing = context.screen.is_animation_playing
        if (not self.was_playing):
            bpy.ops.screen.animation_play()

        print("TALK - running modal")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


    def modal(self, context, event):

        #print(event.type)

        # Cancel. Delete the current recording.
        if event.type in {'ESC'}:
            print("modal - cancel")
            self.restore_playing_state(context)
            return {'CANCELLED'}

        # Confirm. Delete the current recording.
        if event.type in {'RET'}:
            print("modal - confirm")
            self.restore_playing_state(context)
            return {'FINISHED'}

        # Periodic update
        if event.type == 'TIMER':
            if (context.window_manager.push_to_talk_is_active == False):
                self.restore_playing_state(context)
                return {'FINISHED'}

            new_strip = context.scene.sequence_editor.sequences_all["Recording..."]
            new_strip.frame_final_end = context.scene.frame_current

        return {'PASS_THROUGH'}


    def execute(self, context):
        print("TALK - execute")
        return {'FINISHED'}

    def cancel(self, context):
        print("TALK - cancel")
        wm = context.window_manager
        wm.event_timer_remove(self._timer)



class SEQUENCER_OT_finish_push_to_talk(Operator):
    bl_idname = "sequencer.finish_push_to_talk"
    bl_label = "Stop Recording"
    bl_description = "XXX"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        print("stop the other operator")
        context.window_manager.push_to_talk_is_active = False
        return {'FINISHED'}


def draw_push_to_talk_button(self, context):
    layout = self.layout
    if (context.window_manager.push_to_talk_is_active):
        layout.operator("sequencer.finish_push_to_talk", text="Stop Recording", icon='SNAP_FACE') #PAUSE
    else:
        layout.operator("sequencer.push_to_talk", text="Start Recording", icon='REC') #PLAY_SOUND



# Add-on Registration #########################################################

classes = (
    SEQUENCER_OT_push_to_talk,
    SEQUENCER_OT_finish_push_to_talk,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add properties
    bpy.types.WindowManager.push_to_talk_is_active = BoolProperty(
        name="XXX",
        description="XXX",
        default=False
    )

    bpy.types.SEQUENCER_HT_header.append(draw_push_to_talk_button)


def unregister():
    # Clear properties
    del bpy.types.WindowManager.push_to_talk_is_active

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
