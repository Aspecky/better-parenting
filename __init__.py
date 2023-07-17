# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Better Parenting",
    "author": "Aspecky",
    "description": "Ctrl X to delete an object with its descendants. Shift A > Mesh > Parent to Empty for an improved parent to empty operator",
    "blender": (2, 80, 0),
    "version": (1, 0, 0),
    "category": "Object",
}

import bpy
from mathutils import Vector
from bpy import types, ops, props

OPERATOR_NAMESPACE = "better_parenting."


class DeleteRecursive(types.Operator):
    bl_idname = OPERATOR_NAMESPACE + "delete_recursive"
    bl_label = "Delete Recursive"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = set()
        for parent in context.selected_objects:
            objs.add(parent)
            for child in parent.children_recursive:
                objs.add(child)

        for obj in objs:
            bpy.data.objects.remove(obj)

        return {"FINISHED"}

    def menu_func(self, context):
        self.layout.operator(DeleteRecursive.bl_idname)


def parent_with_transform(child: types.Object, parent: types.Object):
    ops.object.select_all(action="DESELECT")
    child.select_set(True)
    parent.select_set(True)
    bpy.context.view_layer.objects.active = parent
    ops.object.parent_set(keep_transform=True)


def get_bounding_box(objs):
    min_point = Vector((float("inf"), float("inf"), float("inf")))
    max_point = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in objs:
        for vertex in obj.data.vertices:
            world_pos = obj.matrix_world @ vertex.co
            min_point.x = min(min_point.x, world_pos.x)
            min_point.y = min(min_point.y, world_pos.y)
            min_point.z = min(min_point.z, world_pos.z)
            max_point.x = max(max_point.x, world_pos.x)
            max_point.y = max(max_point.y, world_pos.y)
            max_point.z = max(max_point.z, world_pos.z)

    return (min_point + max_point) / 2, max_point - min_point


def apply_location_to_matrix(location, matrix):
    matrix[0][3] = location.x
    matrix[1][3] = location.y
    matrix[2][3] = location.z


class ParentToEmpty(types.Operator):
    bl_idname = OPERATOR_NAMESPACE + "parent_to_empty"
    bl_label = "Parent to Empty"
    bl_options = {"REGISTER", "UNDO"}

    location: props.EnumProperty(
        name="Location",
        description="Location of the empty",
        items=[
            ("TOP", "Top", "Bounding box top"),
            ("CENTER", "Center", "Bounding box center"),
            ("BOTTOM", "Bottom", "Bounding box bottom"),
        ],
        default="CENTER",
    )

    show_name: props.BoolProperty(name="Name", default=True)
    show_axis: props.BoolProperty(name="Axes", default=False)
    show_in_front: props.BoolProperty(name="In Front", default=True)

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) != 0

    def execute(self, context):
        objs = set(context.selected_objects)

        empty = bpy.data.objects.new("Empty", None)
        empty.empty_display_type = "PLAIN_AXES"
        context.scene.collection.objects.link(empty)
        location = sum((obj.matrix_world.translation for obj in objs), Vector()) / len(
            objs
        )
        apply_location_to_matrix(location, empty.matrix_world)

        location = empty.location
        meshes = []
        for obj in objs:
            if obj.type == "MESH":
                meshes.append(obj)
        if len(meshes) != 0:
            center, size = get_bounding_box(meshes)
            if self.location == "TOP":
                location = center + Vector((0, 0, size.z / 2))
            elif self.location == "CENTER":
                location = center
            elif self.location == "BOTTOM":
                location = center - Vector((0, 0, size.z / 2))

        apply_location_to_matrix(location, empty.matrix_world)
        empty.show_name = self.show_name
        empty.show_axis = self.show_axis
        empty.show_in_front = self.show_in_front

        parent = None
        for obj in objs:
            if obj.parent in objs:
                continue
            if parent is None:
                parent = obj.parent

            matrix = obj.matrix_world.copy()
            obj.parent = empty
            obj.matrix_world = matrix

        if parent:
            matrix = empty.matrix_world.copy()
            empty.parent = parent
            empty.matrix_world = matrix


        ops.object.select_all(action="DESELECT")
        empty.select_set(True)
        bpy.context.view_layer.objects.active = empty

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "location")
        split = layout.split()

        col = split.column(align=True)
        col.label(text="Show:")

        col = split.column()
        col.prop(self, "show_name")
        col.prop(self, "show_axis")
        col.prop(self, "show_in_front")

        split.column()

    def menu_func(self, context):
        self.layout.operator(ParentToEmpty.bl_idname, icon="OUTLINER_OB_EMPTY")


class SelectDescendants(types.Operator):
    bl_idname = OPERATOR_NAMESPACE + "select_descendants"
    bl_label = "Select Descendants"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) != 0
    
    def execute(self, context):
        for obj in context.selected_objects:
            for obj in obj.children_recursive:
                obj.select_set(True)
        return {"FINISHED"}
    
register_classes, unregister_classes = bpy.utils.register_classes_factory(
    [
        SelectDescendants,
        DeleteRecursive,
        ParentToEmpty,
    ]
)


def register():
    register_classes()
    types.VIEW3D_MT_object.append(DeleteRecursive.menu_func)
    types.VIEW3D_MT_mesh_add.append(ParentToEmpty.menu_func)

    km = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name="Window")
    km.keymap_items.new(DeleteRecursive.bl_idname, "X", "PRESS", ctrl=True)
    km.keymap_items.new(SelectDescendants.bl_idname, "Q", "PRESS", shift=True)


def unregister():
    unregister_classes()
    types.VIEW3D_MT_object.remove(DeleteRecursive.menu_func)
    types.VIEW3D_MT_mesh_add.remove(ParentToEmpty.menu_func)

    km = bpy.context.window_manager.keyconfigs.addon.keymaps["Window"]
    km.keymap_items.remove(km.keymap_items.get(DeleteRecursive.bl_idname))
    km.keymap_items.remove(km.keymap_items.get(SelectDescendants.bl_idname))


if __name__ == "__main__":
    register()
