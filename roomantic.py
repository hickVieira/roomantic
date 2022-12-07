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
    "description": "Toolbox for sector based game level creation",
    "warning": "WIP",
    "wiki_url": "",
    "category": "Object",
}


# FUNCS


def _update_sector_solidify(self, context):
    update_sector2d_solidify(context.active_object)


def update_sector2d_solidify(shape):
    if shape.modifiers:
        mod = shape.modifiers[0]
        mod.thickness = shape.ble_ceiling_height - shape.ble_floor_height
        mod.offset = 1 + shape.ble_floor_height / (mod.thickness / 2)


def is_shape(obj):
    return obj.ble_shape_type != 'NONE'


def initialize_shape(shape):
    if is_shape(shape):
        shape.display_type = 'WIRE'

        shape.ble_ceiling_height = 4
        shape.ble_floor_height = 0
        shape.ble_shape_auto_texture = True
        shape.ble_floor_texture = ''
        shape.ble_wall_texture = ''
        shape.ble_ceiling_texture = ''
        shape.ble_ceiling_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.ble_wall_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.ble_floor_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.ble_ceiling_texture_rotation = 0
        shape.ble_wall_texture_rotation = 0
        shape.ble_floor_texture_rotation = 0


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


def remove_not_used():
    for obj in bpy.data.objects:
        if obj.users == 0:
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh, do_unlink=True)
    for material in bpy.data.materials:
        if material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)


def update_sector2d(shape):
    # get add update solidify
    solidify = get_add_modifier(shape, 'SOLIDIFY')
    solidify.use_even_offset = True
    solidify.use_quality_normals = True
    solidify.use_even_offset = True
    solidify.material_offset = 1
    solidify.material_offset_rim = 2
    update_sector2d_solidify(shape)

    # add delete materials
    set_material_slots_size(shape, 3)

    # update update
    if bpy.data.materials.find(shape.ble_ceiling_texture) != -1:
        shape.material_slots[0].material = bpy.data.materials[shape.ble_ceiling_texture]
    if bpy.data.materials.find(shape.ble_floor_texture) != -1:
        shape.material_slots[1].material = bpy.data.materials[shape.ble_floor_texture]
    if bpy.data.materials.find(shape.ble_wall_texture) != -1:
        shape.material_slots[2].material = bpy.data.materials[shape.ble_wall_texture]


def update_shape_precision(shape):
    shape.location.x = round(shape.location.x, bpy.context.scene.ble_precision)
    shape.location.y = round(shape.location.y, bpy.context.scene.ble_precision)
    shape.location.z = round(shape.location.z, bpy.context.scene.ble_precision)

    for v in shape.data.vertices:
        v.co.x = round(v.co.x, bpy.context.scene.ble_precision)
        v.co.y = round(v.co.y, bpy.context.scene.ble_precision)
        v.co.z = round(v.co.z, bpy.context.scene.ble_precision)


def update_shape(shape):
    if shape:
        shape.display_type = 'WIRE'

        update_shape_precision(shape)

        if shape.ble_shape_type == 'SECTOR2D':
            update_sector2d(shape)


def get_shapes(collections):
    shapes = []
    for col in collections:
        for obj in col.all_objects:
            if obj.ble_shape_type is not None:
                if obj.ble_shape_type != 'NONE':
                    if obj not in shapes:
                        shapes.append(obj)
    return shapes


def copy_materials(source, target):
    set_material_slots_size(target, max(
        len(target.data.materials), len(source.data.materials)))
    for i in range(0, len(source.data.materials)):
        target.data.materials[i] = source.data.materials[i]


def copy_transforms(source, target):
    target.location = source.location
    target.scale = source.scale
    target.rotation_euler = source.rotation_euler


def eval_shape(shape):
    dg = bpy.context.evaluated_depsgraph_get()
    evalObj = shape.evaluated_get(dg)
    mesh = bpy.data.meshes.new_from_object(evalObj)
    mesh.use_auto_smooth = shape.data.use_auto_smooth
    mesh.auto_smooth_angle = shape.data.auto_smooth_angle

    roomName = "ble_" + shape.name
    room = bpy.data.objects.new(roomName, mesh)
    room.name = roomName

    copy_transforms(shape, room)
    update_shape_precision(room)

    return room


def create_mesh_obj(name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    return obj


def make_shape_boolean(shape):
    set_material_slots_size(shape, 1)
    shape.data.materials[0] = bpy.data.materials[bpy.context.scene.ble_remove_material]


def apply_csg(target, boolean, operation):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)

    mod = target.modifiers.new(name='boolean', type='BOOLEAN')
    mod.object = boolean
    mod.solver = 'EXACT'
    mod.operation = operation
    bpy.ops.object.modifier_apply(modifier='boolean')


def apply_remove_material(shape):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = shape
    shape.select_set(True)

    if bpy.context.scene.ble_remove_material is not "":
        i = 0
        remove = False
        for m in shape.material_slots:
            if bpy.context.scene.ble_remove_material == m.name:
                remove = True
            else:
                if not remove:
                    i += 1

        if remove:
            shape.active_material_index = i
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.material_slot_select()
            bpy.ops.mesh.delete(type='FACE')
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.material_slot_remove()



def flip_normals(shape):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = shape
    shape.select_set(True)
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


def apply_auto_texture(shape):
    mesh = shape.data
    objectLocation = shape.location
    objectScale = shape.scale

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
                luv.uv = rotate2D(luv.uv, shape.ble_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_wall_texture_scale_offset[0]), shape.ble_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_wall_texture_scale_offset[1]), shape.ble_wall_texture_scale_offset[3])
            if faceDirection == "-x":
                luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.ble_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_wall_texture_scale_offset[0]), shape.ble_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_wall_texture_scale_offset[1]), shape.ble_wall_texture_scale_offset[3])
            if faceDirection == "y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.ble_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_wall_texture_scale_offset[0]), shape.ble_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_wall_texture_scale_offset[1]), shape.ble_wall_texture_scale_offset[3])
            if faceDirection == "-y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.ble_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_wall_texture_scale_offset[0]), shape.ble_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_wall_texture_scale_offset[1]), shape.ble_wall_texture_scale_offset[3])
            if faceDirection == "z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, shape.ble_ceiling_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_ceiling_texture_scale_offset[0]), shape.ble_ceiling_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_ceiling_texture_scale_offset[1]), shape.ble_ceiling_texture_scale_offset[3])
            if faceDirection == "-z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, shape.ble_floor_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.ble_floor_texture_scale_offset[0]), shape.ble_floor_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.ble_floor_texture_scale_offset[1]), shape.ble_floor_texture_scale_offset[3])

    bm.to_mesh(mesh)
    bm.free()

    shape.data = mesh

def apply_triangulate(shape):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = shape
    shape.select_set(True)

    mod = shape.modifiers.new(name='triangulate', type='TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier='triangulate')


# FUNCS


# DATA

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
bpy.types.Object.ble_shape_type = bpy.props.EnumProperty(
    items=[
        ("SECTOR2D", "Sector2D", "is a 2D sector"),
        ("SECTOR3D", "Sector3D", "is a 3D sector"),
        ("BRUSH", "Brush", "is a shape"),
        ("NONE", "None", "none"),
    ],
    name="Shape Type",
    default='NONE'
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
bpy.types.Object.ble_shape_auto_texture = bpy.props.BoolProperty(
    name="Shape Auto Texture",
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
            col.operator("scene.ble_new_geometry", text="New Sector2D",
                         icon="MESH_PLANE").shape_type = 'SECTOR2D'
            col.operator("scene.ble_new_geometry", text="New Sector3D",
                         icon="CUBE").shape_type = 'SECTOR3D'
            col.operator("scene.ble_new_geometry", text="New Brush",
                         icon="CUBE").shape_type = 'BRUSH'

        # object
        if obj is not None:
            col = layout.column(align=True)
            col.label(icon="MOD_ARRAY", text="Shape Properties")
            col.prop(obj, "ble_shape_type", text="Shape Type")
            col.prop(obj, "ble_shape_auto_texture", text="Auto Texture")
            if obj.ble_shape_auto_texture:
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
            if obj.ble_shape_type == 'SECTOR2D':
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

        # The new algo works to achieve this goal: each shape must be its own separate object
        # So we can no longer rely on a global level_geometry object that gets booleaned around by each shape
        # we now need to treat each shape separately

        # get output collection
        levelCollection = get_add_collection(scene, 'BLE_LEVEL')
        levelCollection.hide_select = False
        shapeCollection = get_add_collection(scene, 'BLE_SHAPES')
        shapeCollection.hide_select = False

        # clear output collections
        for obj in levelCollection.objects:
            levelCollection.objects.unlink(obj)

        # cleanup
        remove_not_used()

        # look for shapes
        shapes = get_shapes(
            [scene.collection, levelCollection, shapeCollection])

        # optimization
        hasBrushes = False

        # unlink shapes from old collection
        for shape in shapes:
            for col in shape.users_collection:
                col.objects.unlink(shape)
            if shape.ble_shape_type == 'BRUSH':
                hasBrushes = True

        # if has no geom then remove
        for shape in shapes:
            if len(shape.data.vertices) < 3:
                shapes.remove(shape)
                continue

        # update + link shapes
        for shape in shapes:
            update_shape(shape)
            shapeCollection.objects.link(shape)

        # cache shape boolean objects (they are just remove_material blobs)
        shapeBooleans = {}
        brushBoolean = create_mesh_obj('brushBoolean') if hasBrushes else None
        bpy.context.scene.collection.objects.link(brushBoolean)
        for shape in shapes:
            shapeBoolean = eval_shape(shape)
            make_shape_boolean(shapeBoolean)
            shapeBooleans[shape] = shapeBoolean
            if hasBrushes:
                if shape.ble_shape_type != 'BRUSH':
                    apply_csg(brushBoolean, shapeBoolean, 'UNION')

        # create/duplicate shapes to output
        for currentShape in shapes:
            evaluatedShape = eval_shape(currentShape)
            evaluatedShape.display_type = 'TEXTURED'
            copy_materials(currentShape, evaluatedShape)
            removeMaterialIndex = len(evaluatedShape.data.materials)
            set_material_slots_size(evaluatedShape, len(
                evaluatedShape.data.materials) + 1)
            evaluatedShape.data.materials[removeMaterialIndex] = bpy.data.materials[bpy.context.scene.ble_remove_material]
            levelCollection.objects.link(evaluatedShape)

            if currentShape.ble_shape_type == 'SECTOR2D' or currentShape.ble_shape_type == 'SECTOR3D':
                for otherShape in shapes:
                    if currentShape == otherShape:
                        continue
                    # if not in_bounds(currentShape,otherShape):
                        # continue
                    otherBoolean = shapeBooleans[otherShape]
                    apply_csg(evaluatedShape, otherBoolean, 'UNION')

                    if bpy.context.scene.ble_flip_normals:
                        flip_normals(evaluatedShape)
            else:
                apply_csg(evaluatedShape, brushBoolean, 'INTERSECT')

            apply_remove_material(evaluatedShape)

            apply_triangulate(evaluatedShape)

            if currentShape.ble_shape_type == 'SECTOR2D' or currentShape.ble_shape_auto_texture:
                apply_auto_texture(evaluatedShape)

        # mark unselectable
        levelCollection.hide_select = True

        # restore context
        bpy.ops.object.select_all(action='DESELECT')
        if wasEditMode:
            bpy.ops.object.mode_set(mode='EDIT')

        # unlink brushBoolean
        if hasBrushes:
            bpy.context.scene.collection.objects.unlink(brushBoolean)

        # cleanup
        remove_not_used()

        return {"FINISHED"}


class BlenderLevelEditorNewGeometry(bpy.types.Operator):
    bl_idname = "scene.ble_new_geometry"
    bl_label = "New Geometry"

    shape_type: bpy.props.StringProperty(name="shape_type", default='NONE')

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')

        if self.shape_type == 'SECTOR2D':
            bpy.ops.mesh.primitive_plane_add(size=2)
        else:
            bpy.ops.mesh.primitive_cube_add(size=2)

        shape = bpy.context.active_object
        shape.name = self.shape_type
        shape.data.name = self.shape_type
        shape.ble_shape_type = self.shape_type

        initialize_shape(shape)
        update_shape(shape)

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
        if activeObj.ble_shape_type == 'SECTOR2D' and len(selectedFaces) > 0:
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
        copy_materials(activeObj, ripedObj)

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
