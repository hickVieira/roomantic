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


def _update_sector_solidify(self, context):
    update_sector_solidify(context.active_object)


def update_sector_solidify(brush):
    if brush.modifiers:
        mod = brush.modifiers[0]
        mod.thickness = brush.ble_ceiling_height - brush.ble_floor_height
        mod.offset = 1 + brush.ble_floor_height / (mod.thickness / 2)


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


def _get_add_collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    return bpy.data.collections.new(name=name)


def get_add_collection(scene, name):
    col = _get_add_collection(name)
    if name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def get_modifier(obj, type):
    for mod in obj.modifiers:
        if mod.type == type:
            return mod
    return None


def add_modifier(obj, type):
    return obj.modifiers.new(name=type, type=type)


def get_add_modifier(obj, type):
    mod = get_modifier(obj, type)
    if mod is None:
        mod = add_modifier(obj, type)
    return mod


def set_material_slots_size(obj, size):
    while len(obj.material_slots) < size:
        obj.data.materials.append(None)
    while len(obj.material_slots) > size:
        obj.data.materials.pop()


def update_sector(brush):
    # get add update solidify
    solidify = get_add_modifier(brush, 'SOLIDIFY')
    solidify.use_even_offset = True
    solidify.use_quality_normals = True
    solidify.use_even_offset = True
    solidify.material_offset = 1
    solidify.material_offset_rim = 2
    update_sector_solidify(brush)

    # add delete materials
    set_material_slots_size(brush, 3)

    # update update
    if bpy.data.materials.find(brush.ble_ceiling_texture) != -1:
        brush.material_slots[0].material = bpy.data.materials[brush.ble_ceiling_texture]
    if bpy.data.materials.find(brush.ble_floor_texture) != -1:
        brush.material_slots[1].material = bpy.data.materials[brush.ble_floor_texture]
    if bpy.data.materials.find(brush.ble_wall_texture) != -1:
        brush.material_slots[2].material = bpy.data.materials[brush.ble_wall_texture]


def update_brush_precision(brush):
    brush.location.x = round(brush.location.x, bpy.context.scene.ble_precision)
    brush.location.y = round(brush.location.y, bpy.context.scene.ble_precision)
    brush.location.z = round(brush.location.z, bpy.context.scene.ble_precision)

    for v in brush.data.vertices:
        v.co.x = round(v.co.x, bpy.context.scene.ble_precision)
        v.co.y = round(v.co.y, bpy.context.scene.ble_precision)
        v.co.z = round(v.co.z, bpy.context.scene.ble_precision)


def update_brush(brush):
    if brush:
        brush.display_type = 'WIRE'

        update_brush_precision(brush)

        if brush.ble_brush_type == 'SECTOR':
            update_sector(brush)


def get_all_brushes():
    # get everything
    allObjects = bpy.context.scene.collection.all_objects

    # get brushes only
    brushes = []
    for obj in allObjects:
        if obj.ble_brush_type is not 'NONE':
            brushes.append(obj)

    return brushes


def copy_materials(source, target):
    set_material_slots_size(target, max(
        len(target.data.materials), len(source.data.materials)))
    for i in range(0, len(source.data.materials)):
        target.data.materials[i] = source.data.materials[i]


def copy_transforms(source, target):
    target.location = source.location
    target.scale = source.scale
    target.rotation_euler = source.rotation_euler


def eval_brush(brush):
    dg = bpy.context.evaluated_depsgraph_get()
    evalObj = brush.evaluated_get(dg)
    mesh = bpy.data.meshes.new_from_object(evalObj)
    mesh.use_auto_smooth = brush.data.use_auto_smooth
    mesh.auto_smooth_angle = brush.data.auto_smooth_angle

    roomName = "ble_" + brush.name
    room = bpy.data.objects.new(roomName, mesh)
    room.name = roomName

    copy_transforms(brush, room)
    update_brush_precision(room)

    return room


def make_brush_boolean(brush):
    set_material_slots_size(brush, 1)
    brush.data.materials[0] = bpy.data.materials[bpy.context.scene.ble_remove_material]


def apply_brush_csg(target, brushBoolean, operation):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)

    mod0 = target.modifiers.new(name='bool0', type='BOOLEAN')
    mod0.object = brushBoolean
    mod0.operation = 'UNION'
    mod0.solver = 'EXACT'

    mod1 = target.modifiers.new(name='bool1', type='BOOLEAN')
    mod1.object = brushBoolean
    mod1.operation = 'DIFFERENCE'
    mod1.solver = 'EXACT'

    bpy.ops.object.modifier_apply(modifier='bool0')
    bpy.ops.object.modifier_apply(modifier='bool1')


def apply_remove_material(brush):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = brush
    brush.select_set(True)

    if bpy.context.scene.ble_remove_material is not "":
        i = 0
        remove = False
        for m in brush.material_slots:
            if bpy.context.scene.ble_remove_material == m.name:
                remove = True
            else:
                if not remove:
                    i += 1

        if remove:
            brush.active_material_index = i
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.material_slot_select()
            bpy.ops.mesh.delete(type='FACE')
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.material_slot_remove()


def flip_normals(brush):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = brush
    brush.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')


def translate(val, t):
    return val + t


def scale(val, s):
    return val * s


def rotate2D(uv, degrees):
    radians = math.radians(degrees)
    newUV = copy(uv)
    newUV.x = uv.x*math.cos(radians) - uv.y*math.sin(radians)
    newUV.y = uv.x*math.sin(radians) + uv.y*math.cos(radians)
    return newUV


def auto_texture(brush):
    mesh = brush.data
    objectLocation = brush.location
    objectScale = brush.scale

    bm = bmesh.new()
    bm.from_mesh(mesh)

    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        nX = f.normal.x
        nY = f.normal.y
        nZ = f.normal.z
        if nX < 0:
            nX = nX * -1
        if nY < 0:
            nY = nY * -1
        if nZ < 0:
            nZ = nZ * -1
        faceNormalLargest = nX
        faceDirection = "x"
        if faceNormalLargest < nY:
            faceNormalLargest = nY
            faceDirection = "y"
        if faceNormalLargest < nZ:
            faceNormalLargest = nZ
            faceDirection = "z"
        if faceDirection == "x":
            if f.normal.x < 0:
                faceDirection = "-x"
        if faceDirection == "y":
            if f.normal.y < 0:
                faceDirection = "-y"
        if faceDirection == "z":
            if f.normal.z < 0:
                faceDirection = "-z"
        for l in f.loops:
            luv = l[uv_layer]
            if faceDirection == "x":
                luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, brush.wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.wall_texture_scale_offset[0]), brush.wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.wall_texture_scale_offset[1]), brush.wall_texture_scale_offset[3])
            if faceDirection == "-x":
                luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, brush.wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.wall_texture_scale_offset[0]), brush.wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.wall_texture_scale_offset[1]), brush.wall_texture_scale_offset[3])
            if faceDirection == "y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, brush.wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.wall_texture_scale_offset[0]), brush.wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.wall_texture_scale_offset[1]), brush.wall_texture_scale_offset[3])
            if faceDirection == "-y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, brush.wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.wall_texture_scale_offset[0]), brush.wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.wall_texture_scale_offset[1]), brush.wall_texture_scale_offset[3])
            if faceDirection == "z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, brush.ceiling_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.ceiling_texture_scale_offset[0]), brush.ceiling_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.ceiling_texture_scale_offset[1]), brush.ceiling_texture_scale_offset[3])
            if faceDirection == "-z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, brush.floor_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, brush.floor_texture_scale_offset[0]), brush.floor_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, brush.floor_texture_scale_offset[1]), brush.floor_texture_scale_offset[3])

    bm.to_mesh(mesh)
    bm.free()

    brush.data = mesh


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
    update=_update_sector_solidify
)
bpy.types.Object.ble_floor_height = bpy.props.FloatProperty(
    name="Floor Height",
    default=0,
    step=10,
    precision=3,
    update=_update_sector_solidify
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
        obj = context.active_object
        scene = bpy.context.scene
        layout = self.layout

        # base
        col = layout.column(align=True)
        col.label(icon="WORLD", text="Map Settings")
        col.prop(scene, "ble_flip_normals")
        col.prop(scene, "ble_precision")
        col.prop_search(scene, "ble_remove_material", bpy.data, "materials")
        col = layout.column(align=True)
        col.operator("scene.ble_build", text="Build", icon="MOD_BUILD")

        # tools
        col = layout.column(align=True)
        col.label(icon="SNAP_PEEL_OBJECT", text="Tools")
        col.operator("scene.ble_open_material",
                     text="Open Material", icon="TEXTURE")
        if bpy.context.mode == 'EDIT_MESH':
            col.operator("object.ble_rip_geometry", text="Rip To",
                         icon="UNLINKED").focus_to_rip = True
            col.operator("object.ble_rip_geometry", text="Rip Stay",
                         icon="UNLINKED").focus_to_rip = False
        else:
            col.operator("scene.ble_new_geometry", text="New Sector",
                         icon="MESH_PLANE").brush_type = 'SECTOR'
            col.operator("scene.ble_new_geometry", text="New Brush",
                         icon="CUBE").brush_type = 'BRUSH'

        # object
        if obj is not None:
            col = layout.column(align=True)
            col.label(icon="MOD_ARRAY", text="Brush Properties")
            col.prop(obj, "ble_brush_type", text="Brush Type")
            col.prop(obj, "ble_csg_operation", text="CSG Op")
            col.prop(obj, "ble_csg_order", text="CSG Order")
            col.prop(obj, "ble_brush_auto_texture", text="Auto Texture")
            if obj.ble_brush_auto_texture:
                col = layout.row(align=True)
                col.prop(obj, "ble_ceiling_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "ble_wall_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "ble_floor_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "ble_ceiling_texture_rotation")
                col = layout.row(align=True)
                col.prop(obj, "ble_wall_texture_rotation")
                col = layout.row(align=True)
                col.prop(obj, "ble_floor_texture_rotation")
            if obj.ble_brush_type == 'SECTOR':
                col = layout.column(align=True)
                col.label(icon="MOD_ARRAY", text="Sector Properties")
                col.prop(obj, "ble_ceiling_height")
                col.prop(obj, "ble_floor_height")
                # layout.separator()
                col = layout.column(align=True)
                col.prop_search(obj, "ble_ceiling_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Ceiling")
                col.prop_search(obj, "ble_wall_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Wall")
                col.prop_search(obj, "ble_floor_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Floor")


class BlenderLevelEditorBuild(bpy.types.Operator):
    bl_idname = "scene.ble_build"
    bl_label = "Build"

    def execute(self, context):
        scene = bpy.context.scene

        # save context
        wasEditMode = False
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            wasEditMode = True

        # The new algo works to achieve this goal: each brush must be its own separate object
        # So we can no longer rely on a global level_geometry object that gets booleaned around by each brush
        # we now need to treat each brush separately

        # get output collection
        levelCollection = get_add_collection(scene, 'LEVEL')
        levelCollection.hide_select = False
        brushCollection = get_add_collection(scene, 'BRUSHES')
        brushCollection.hide_select = False

        # clear output collection
        for obj in levelCollection.all_objects:
            levelCollection.objects.unlink(obj)

        # get brushes only
        brushes = get_all_brushes()

        # update brushes
        for brush in brushes:
            # unlink from everything
            for col in brush.users_collection:
                col.objects.unlink(brush)
            
            # if has no geom then remove
            if len(brush.data.vertices) < 3:
                brushes.remove(brush)
            else:
                brushCollection.objects.link(brush)
                update_brush(brush)

        # cache brush boolean objects (they are just remove_material blobs)
        booleans = {}
        for brush in brushes:
            brushBoolean = eval_brush(brush)
            make_brush_boolean(brushBoolean)
            booleans[brush] = brushBoolean

        # create/duplicate brushes to output
        for currentBrush in brushes:
            currentRoom = eval_brush(currentBrush)
            currentRoom.display_type = 'TEXTURED'
            copy_materials(currentBrush, currentRoom)
            removeMaterialIndex = len(currentRoom.data.materials)
            set_material_slots_size(currentRoom, len(
                currentRoom.data.materials) + 1)
            currentRoom.data.materials[removeMaterialIndex] = bpy.data.materials[bpy.context.scene.ble_remove_material]
            levelCollection.objects.link(currentRoom)
            for otherBrush in brushes:
                if currentBrush == otherBrush:
                    continue
                # if not in_bounds(currentBrush,otherBrush):
                    # continue
                otherBoolean = booleans[otherBrush]
                apply_brush_csg(currentRoom, otherBoolean,
                                csg_operation_to_blender_boolean["SUBTRACT"])
            apply_remove_material(currentRoom)
            if currentBrush.ble_brush_type == 'SECTOR' or (currentBrush.ble_brush_type == 'BRUSH' and currentBrush.ble_brush_auto_texture):
                auto_texture(currentRoom)
            if bpy.context.scene.ble_flip_normals:
                flip_normals(currentRoom)

        # mark unselectable
        levelCollection.hide_select = True

        # restore context
        bpy.ops.object.select_all(action='DESELECT')
        if wasEditMode:
            bpy.ops.object.mode_set(mode='EDIT')

        # remove trash
        for obj in bpy.data.objects:
            if obj.users == 0:
                bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh, do_unlink=True)
        for material in bpy.data.materials:
            if material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)

        return {"FINISHED"}


class BlenderLevelEditorNewGeometry(bpy.types.Operator):
    bl_idname = "scene.ble_new_geometry"
    bl_label = "New Geometry"

    brush_type: bpy.props.StringProperty(name="brush_type", default='NONE')

    def execute(self, context):
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
            newMaterialName = fileName
            newMaterial = bpy.data.materials.get(newMaterialName)

            if newMaterial == None:
                newMaterial = bpy.data.materials.new(newMaterialName)

            newMaterial.use_nodes = True
            newMaterial.preview_render_type = 'FLAT'

            # We clear it as we'll define it completely
            newMaterial.node_tree.links.clear()
            newMaterial.node_tree.nodes.clear()

            # create nodes
            bsdfNode = newMaterial.node_tree.nodes.new(
                'ShaderNodeBsdfPrincipled')
            outputNode = newMaterial.node_tree.nodes.new(
                'ShaderNodeOutputMaterial')
            texImageNode = newMaterial.node_tree.nodes.new(
                'ShaderNodeTexImage')
            texImageNode.name = fileName
            texImageNode.image = bpy.data.images.load(
                directory + "\\" + fileName + fileExtension, check_existing=True)

            # create node links
            newMaterial.node_tree.links.new(
                bsdfNode.outputs['BSDF'], outputNode.inputs['Surface'])
            newMaterial.node_tree.links.new(
                bsdfNode.inputs['Base Color'], texImageNode.outputs['Color'])

            # some params
            bsdfNode.inputs['Roughness'].default_value = 0
            bsdfNode.inputs['Specular'].default_value = 0

        return {"FINISHED"}


class BlenderLevelEditorRipGeometry(bpy.types.Operator):
    bl_idname = "object.ble_rip_geometry"
    bl_label = "Rip Geometry"

    focus_to_rip: bpy.props.BoolProperty(
        name="active_to_riped", default=False)

    def execute(self, context):
        activeObj = context.active_object

        activeObjBM = bmesh.from_edit_mesh(activeObj.data)

        # https://blender.stackexchange.com/questions/179667/split-off-bmesh-selected-faces
        activeObjBM.verts.ensure_lookup_table()
        activeObjBM.edges.ensure_lookup_table()
        activeObjBM.faces.ensure_lookup_table()

        selectedFaces = [x for x in activeObjBM.faces if x.select]

        # early out
        if len(selectedFaces) == 0:
            activeObjBM.free()
            return {"CANCELLED"}

        ripedObjBM = bmesh.new()
        pyVerts = []
        pyFaces = []

        # rip-copy faces
        for f in selectedFaces:
            currentFaceIndices = []
            for v in f.verts:
                if v not in pyVerts:
                    pyVerts.append(v)
                currentFaceIndices.append(pyVerts.index(v))

            pyFaces.append(currentFaceIndices)

        # create mesh
        ripedMesh = bpy.data.meshes.new(name='riped_mesh')
        if len(pyFaces) > 0:
            ripedMesh.from_pydata([x.co for x in pyVerts], [], pyFaces)

        # remove from riped
        if activeObj.brush_type != 'BRUSH' and len(selectedFaces) > 0:
            edgesToRemove = []
            for f in selectedFaces:
                for e in f.edges:
                    if e not in edgesToRemove:
                        edgesToRemove.append(e)

            for f in selectedFaces:
                activeObjBM.faces.remove(f)

            for e in edgesToRemove:
                if e.is_wire:
                    activeObjBM.edges.remove(e)

            for v in activeObjBM.verts:
                if len(v.link_edges) == 0 or len(v.link_faces) == 0:
                    activeObjBM.verts.remove(v)

        activeObjBM.verts.ensure_lookup_table()
        activeObjBM.edges.ensure_lookup_table()
        activeObjBM.faces.ensure_lookup_table()

        # create object
        ripedObj = activeObj.copy()
        for col in activeObj.users_collection:
            col.objects.link(ripedObj)
        ripedObj.data = ripedMesh
        copy_materials(ripedObj, activeObj)

        activeObjBM.free()
        ripedObjBM.free()

        # deselect eveything
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        if self.focus_to_rip:
            ripedObj.select_set(True)
            bpy.context.view_layer.objects.active = ripedObj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
        else:
            activeObj.select_set(True)
            bpy.context.view_layer.objects.active = activeObj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')

        return {"FINISHED"}


# CLASSES


def register():
    bpy.utils.register_class(BlenderLevelEditorPanel)
    bpy.utils.register_class(BlenderLevelEditorBuild)
    bpy.utils.register_class(BlenderLevelEditorNewGeometry)
    bpy.utils.register_class(BlenderLevelEditorOpenMaterial)
    bpy.utils.register_class(BlenderLevelEditorRipGeometry)


def unregister():
    bpy.utils.unregister_class(BlenderLevelEditorPanel)
    bpy.utils.unregister_class(BlenderLevelEditorBuild)
    bpy.utils.unregister_class(BlenderLevelEditorNewGeometry)
    bpy.utils.unregister_class(BlenderLevelEditorOpenMaterial)
    bpy.utils.unregister_class(BlenderLevelEditorRipGeometry)


if __name__ == "__main__":
    register()
