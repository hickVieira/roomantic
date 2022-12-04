#  ***** BEGIN GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#  ***** END GPL LICENSE BLOCK *****

from bpy_extras.io_utils import ImportHelper
import addon_utils
import bmesh
import bpy
import math
import os
from copy import copy


bl_info = {
    "name": "Blender Level Editor",
    "author": "HickVieira",
    "version": (0, 1),
    "blender": (3, 3, 0),
    "location": "View3D > Tools > BLE",
    "description": "Toolbox for sector/brush based game level creation",
    "warning": "WIP",
    "wiki_url": "",
    "category": "Object",
}


# FUNCS


def update_sector_solidify(self, context):
    ob = context.active_object
    if ob.modifiers:
        mod = ob.modifiers[0]
        mod.thickness = ob.ceiling_height - ob.floor_height
        mod.offset = 1 + ob.floor_height / (mod.thickness / 2)


def initialize_brush(brush):
    if brush.ble_brush_type is not 'NONE':
        brush.display_type = 'WIRE'

        brush.ble_csg_operation = 'ADD'
        brush.ble_csg_order = 0
        brush.ble_ceiling_height = 3
        brush.ble_floor_height = 0
        brush.ble_brush_auto_texture = True
        brush.ble_floor_texture = ''
        brush.ble_wall_texture = ''
        brush.ble_ceiling_texture = ''
        brush.ble_ceiling_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        brush.ble_wall_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        brush.ble_floor_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        brush.ble_ceiling_texture_rotation = 0
        brush.ble_wall_texture_rotation = 0
        brush.ble_floor_texture_rotation = 0


def get_modifier(ob, type):
    for mod in ob.modifiers:
        if mod.type == type:
            return mod
    return None


def add_modifier(ob, type):
    return ob.modifiers.new(name=type, type=type)


def get_add_modifier(ob, type):
    mod = get_modifier(ob, type)
    if mod is None:
        mod = add_modifier(ob, type)
    return mod


def update_sector(brush):
    # update solidify
    # get add solidify
    solidify = get_add_modifier(brush, 'SOLIDIFY')
    solidify.use_even_offset = True
    solidify.use_quality_normals = True
    solidify.use_even_offset = True
    solidify.thickness = brush.ceiling_height - brush.floor_height
    solidify.offset = 1 + brush.floor_height / (solidify.thickness / 2)
    solidify.material_offset = 1
    solidify.material_offset_rim = 2

    # update materials
    # delete all the way to 3
    while len(brush.material_slots) < 3:
        bpy.ops.object.material_slot_add()
    # add all the way to 3
    while len(brush.material_slots) > 3:
        bpy.ops.object.material_slot_remove()

    if bpy.data.materials.find(brush.ceiling_texture) != -1:
        brush.material_slots[0].material = bpy.data.materials[brush.ceiling_texture]
    if bpy.data.materials.find(brush.floor_texture) != -1:
        brush.material_slots[1].material = bpy.data.materials[brush.floor_texture]
    if bpy.data.materials.find(brush.wall_texture) != -1:
        brush.material_slots[2].material = bpy.data.materials[brush.wall_texture]


def update_brush_precision(brush):
    brush.location.x = round(brush.location.x, bpy.context.scene.map_precision)
    brush.location.y = round(brush.location.y, bpy.context.scene.map_precision)
    brush.location.z = round(brush.location.z, bpy.context.scene.map_precision)

    for v in brush.data.vertices:
        v.co.x = round(v.co.x, bpy.context.scene.map_precision)
        v.co.y = round(v.co.y, bpy.context.scene.map_precision)
        v.co.z = round(v.co.z, bpy.context.scene.map_precision)


def update_brush(brush):
    if brush:
        brush.display_type = 'WIRE'

        update_brush_precision(brush)

        if brush.ble_brush_type == 'SECTOR':
            update_sector(brush)


# FUNCS


# DATA


csg_operation_to_blender_boolean = {
    "ADD": "UNION",
    "SUBTRACT": "DIFFERENCE"
}
bpy.types.Scene.ble_precision = bpy.props.IntProperty(
    name="Precision",
    default=3,
    min=0,
    max=6,
    description='Controls the rounding level of vertex precisions. A level of 1 would round 1.234 to 1.2 and a level of 2 would round to 1.23'
)
bpy.types.Scene.ble_flip_normals = bpy.props.BoolProperty(
    name="Flip Normals",
    description='Flip output normals',
    default=True,
)
bpy.types.Scene.ble_remove_material = bpy.props.StringProperty(
    name="Remove Material",
    description="Material used as flag for removing geometry"
)
bpy.types.Object.ble_brush_type = bpy.props.EnumProperty(
    items=[
        ("BRUSH", "Brush", "is a brush"),
        ("SECTOR", "Sector", "is a sector"),
        ("NONE", "None", "none"),
    ],
    name="Brush Type",
    default='NONE'
)
bpy.types.Object.ble_csg_operation = bpy.props.EnumProperty(
    items=[
        ("ADD", "Add", "add/union geometry to output"),
        ("SUBTRACT", "Subtract", "subtract/remove geometry from output"),
    ],
    name="CSG Operation",
    default='ADD'
)
bpy.types.Object.ble_csg_order = bpy.props.IntProperty(
    name="CSG Order",
    default=0,
    description='Controls the order of CSG operation of the object'
)
bpy.types.Object.ble_ceiling_height = bpy.props.FloatProperty(
    name="Ceiling Height",
    default=4,
    step=10,
    precision=3,
    update=update_sector_solidify
)
bpy.types.Object.ble_floor_height = bpy.props.FloatProperty(
    name="Floor Height",
    default=0,
    step=10,
    precision=3,
    update=update_sector_solidify
)
bpy.types.Object.ble_brush_auto_texture = bpy.props.BoolProperty(
    name="Brush Auto Texture",
    default=True,
    description='Auto Texture on or off'
)
bpy.types.Object.ble_floor_texture = bpy.props.StringProperty(
    name="Floor Texture",
)
bpy.types.Object.ble_wall_texture = bpy.props.StringProperty(
    name="Wall Texture",
)
bpy.types.Object.ble_ceiling_texture = bpy.props.StringProperty(
    name="Ceiling Texture",
)
bpy.types.Object.ble_ceiling_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Ceiling Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.ble_wall_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Wall Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.ble_floor_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Floor Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.ble_ceiling_texture_rotation = bpy.props.FloatProperty(
    name="Ceiling Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.ble_wall_texture_rotation = bpy.props.FloatProperty(
    name="Wall Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.ble_floor_texture_rotation = bpy.props.FloatProperty(
    name="Floor Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)


# DATA


# CLASSES


class BlenderLevelEditorPanel(bpy.types.Panel):
    bl_label = "Blender Level Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'Blender Level Editor'

    def draw(self, context):
        ob = context.active_object
        scn = bpy.context.scene
        layout = self.layout

        # base
        col = layout.column(align=True)
        col.label(icon="WORLD", text="Map Settings")
        col.prop(scn, "ble_flip_normals")
        col.prop(scn, "ble_precision")
        col.prop_search(scn, "ble_remove_material", bpy.data, "materials")
        col = layout.column(align=True)
        col.operator("scene.ble_build", text="Build", icon="MOD_BUILD")

        # tools
        col = layout.column(align=True)
        col.label(icon="SNAP_PEEL_OBJECT", text="Tools")
        col.operator("scene.ble_open_material",
                     text="Open Material", icon="TEXTURE")
        # if bpy.context.mode == 'EDIT_MESH':
        #     col.operator("object.ble_rip_geometry", text="Rip", icon="UNLINKED").remove_geometry = True
        # else:
        col.operator("scene.ble_new_geometry", text="New Sector",
                     icon="MESH_PLANE").brush_type = 'SECTOR'
        col.operator("scene.ble_new_geometry", text="New Brush",
                     icon="CUBE").brush_type = 'BRUSH'

        # object
        if ob is not None:
            col = layout.column(align=True)
            col.label(icon="MOD_ARRAY", text="Brush Properties")
            col.prop(ob, "ble_brush_type", text="Brush Type")
            col.prop(ob, "ble_csg_operation", text="CSG Op")
            col.prop(ob, "ble_csg_order", text="CSG Order")
            col.prop(ob, "ble_brush_auto_texture", text="Auto Texture")
            if ob.ble_brush_auto_texture:
                col = layout.row(align=True)
                col.prop(ob, "ble_ceiling_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(ob, "ble_wall_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(ob, "ble_floor_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(ob, "ble_ceiling_texture_rotation")
                col = layout.row(align=True)
                col.prop(ob, "ble_wall_texture_rotation")
                col = layout.row(align=True)
                col.prop(ob, "ble_floor_texture_rotation")
            if ob.ble_brush_type == 'SECTOR':
                col = layout.column(align=True)
                col.label(icon="MOD_ARRAY", text="Sector Properties")
                col.prop(ob, "ble_ceiling_height")
                col.prop(ob, "ble_floor_height")
                # layout.separator()
                col = layout.column(align=True)
                col.prop_search(ob, "ble_ceiling_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Ceiling")
                col.prop_search(ob, "ble_wall_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Wall")
                col.prop_search(ob, "ble_floor_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Floor")


class BlenderLevelEditorBuild(bpy.types.Operator):
    bl_idname = "scene.ble_build"
    bl_label = "Build"

    def execute(self, context):
        scn = bpy.context.scene

        # save context
        was_edit_mode = False
        old_active = bpy.context.active_object
        old_selected = bpy.context.selected_objects.copy()
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            was_edit_mode = True

        # The new algo works to achieve this goal: each brush must be its own separate object
        # So we can no longer rely on a global level_geometry object that gets booleaned around by each brush
        # we now need to treat each brush separately

        # get everything
        all_objects = bpy.context.scene.collection.all_objects

        # get brushes only
        brushes = []
        for obj in all_objects:
            if obj.ble_brush_type is not 'NONE':
                brushes.append(obj)
        
        # restore context
        bpy.ops.object.select_all(action='DESELECT')
        if old_active:
            old_active.select_set(True)
            bpy.context.view_layer.objects.active = old_active
        if was_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')
        for obj in old_selected:
            if obj:
                obj.select_set(True)

        # remove trash
        for o in bpy.data.objects:
            if o.users == 0:
                bpy.data.objects.remove(o)
        for m in bpy.data.meshes:
            if m.users == 0:
                bpy.data.meshes.remove(m)
        # for m in bpy.data.materials:
        #     if m.users == 0:
        #         bpy.data.materials.remove(m)

        return {"FINISHED"}


class BlenderLevelEditorNewGeometry(bpy.types.Operator):
    bl_idname = "scene.ble_new_geometry"
    bl_label = "New Geometry"

    brush_type: bpy.props.StringProperty(name="brush_type", default='NONE')

    def execute(self, context):
        scn = bpy.context.scene
        bpy.ops.object.select_all(action='DESELECT')

        if self.brush_type == 'SECTOR':
            bpy.ops.mesh.primitive_plane_add(size=2)
        else:
            bpy.ops.mesh.primitive_cube_add(size=2)

        brush = bpy.context.active_object
        brush.name = self.brush_type
        brush.data.name = self.brush_type
        brush.ble_brush_type = self.brush_type

        initialize_brush(brush)
        update_brush(brush)

        return {"FINISHED"}


class BlenderLevelEditorOpenMaterial(bpy.types.Operator, ImportHelper):
    bl_idname = "scene.ble_open_material"
    bl_label = "Open Material"

    filter_glob: bpy.props.StringProperty(
        default='*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp',
        options={'HIDDEN'}
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def execute(self, context):
        directory, fileNameExtension = os.path.split(self.filepath)

        # do it for all selected files/images
        for f in self.files:
            fileName, fileExtension = os.path.splitext(f.name)

            # new material or find it
            new_material_name = fileName
            new_material = bpy.data.materials.get(new_material_name)

            if new_material == None:
                new_material = bpy.data.materials.new(new_material_name)

            new_material.use_nodes = True
            new_material.preview_render_type = 'FLAT'

            # We clear it as we'll define it completely
            new_material.node_tree.links.clear()
            new_material.node_tree.nodes.clear()

            # create nodes
            bsdfNode = new_material.node_tree.nodes.new(
                'ShaderNodeBsdfPrincipled')
            outputNode = new_material.node_tree.nodes.new(
                'ShaderNodeOutputMaterial')
            texImageNode = new_material.node_tree.nodes.new(
                'ShaderNodeTexImage')
            texImageNode.name = fileName
            texImageNode.image = bpy.data.images.load(
                directory + "\\" + fileName + fileExtension, check_existing=True)

            # create node links
            new_material.node_tree.links.new(
                bsdfNode.outputs['BSDF'], outputNode.inputs['Surface'])
            new_material.node_tree.links.new(
                bsdfNode.inputs['Base Color'], texImageNode.outputs['Color'])

            # some params
            bsdfNode.inputs['Roughness'].default_value = 0
            bsdfNode.inputs['Specular'].default_value = 0

        return {"FINISHED"}


# CLASSES


def register():
    bpy.utils.register_class(BlenderLevelEditorPanel)
    bpy.utils.register_class(BlenderLevelEditorBuild)
    bpy.utils.register_class(BlenderLevelEditorNewGeometry)
    bpy.utils.register_class(BlenderLevelEditorOpenMaterial)


def unregister():
    bpy.utils.unregister_class(BlenderLevelEditorPanel)
    bpy.utils.unregister_class(BlenderLevelEditorBuild)
    bpy.utils.unregister_class(BlenderLevelEditorNewGeometry)
    bpy.utils.unregister_class(BlenderLevelEditorOpenMaterial)


if __name__ == "__main__":
    register()
