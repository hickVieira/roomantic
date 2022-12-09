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
import bmesh
import bpy
import math
import os
from copy import copy


bl_info = {
    "name": "ROOMantic",
    "author": "hickv",
    "version": (1, 2),
    "blender": (3, 3, 0),
    "location": "View3D > Tools > ROOMantic",
    "description": "Toolbox for doom-style sector-based game level creation",
    "warning": "WIP",
    "wiki_url": "",
    "category": "Object",
}


# FUNCS


class Point:
    def __init__(self, x, y, z) -> None:
        self.x = x
        self.y = y
        self.z = z


class Bounds:
    def __init__(self) -> None:
        self.min = None
        self.max = None

    def encapsulate(self, p: Point):
        # min
        if self.min == None:
            self.min = Point(p.x, p.y, p.z)
        else:
            if p.x < self.min.x:
                self.min.x = p.x
            if p.y < self.min.y:
                self.min.y = p.y
            if p.z < self.min.z:
                self.min.z = p.z

        # max
        if self.max == None:
            self.max = Point(p.x, p.y, p.z)
        else:
            if p.x > self.max.x:
                self.max.x = p.x
            if p.y > self.max.y:
                self.max.y = p.y
            if p.z > self.max.z:
                self.max.z = p.z

    def expand(self, f):
        self.min.x -= f
        self.min.y -= f
        self.min.z -= f
        self.max.x += f
        self.max.y += f
        self.max.z += f

    def intersect(self, other):
        return (
            self.min.x <= other.max.x and
            self.max.x >= other.min.x and
            self.min.y <= other.max.y and
            self.max.y >= other.min.y and
            self.min.z <= other.max.z and
            self.max.z >= other.min.z)


def calculate_bounds_ws(mat, mesh, expand):
    bounds = Bounds()
    for v in mesh.vertices:
        pointWS = mat @ v.co
        bounds.encapsulate(Point(pointWS.x, pointWS.y, pointWS.z))
    bounds.expand(expand)
    return bounds


def _update_sector_solidify(self, context):
    update_sector2d_solidify(context.active_object)


def update_sector2d_solidify(shape):
    if shape.modifiers:
        mod = shape.modifiers[0]
        mod.thickness = shape.rmtc_ceiling_height - shape.rmtc_floor_height
        mod.offset = 1 + shape.rmtc_floor_height / (mod.thickness / 2)


def is_shape(obj):
    return obj.rmtc_shape_type != 'NONE'


def initialize_shape(shape):
    if is_shape(shape):
        shape.display_type = 'WIRE'

        shape.rmtc_ceiling_height = 4
        shape.rmtc_floor_height = 0
        shape.rmtc_split_faces = False
        shape.rmtc_shape_auto_texture = True
        shape.rmtc_floor_texture = ''
        shape.rmtc_wall_texture = ''
        shape.rmtc_ceiling_texture = ''
        shape.rmtc_ceiling_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.rmtc_wall_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.rmtc_floor_texture_scale_offset = (1.0, 1.0, 0.0, 0.0)
        shape.rmtc_ceiling_texture_rotation = 0
        shape.rmtc_wall_texture_rotation = 0
        shape.rmtc_floor_texture_rotation = 0


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
    # for material in bpy.data.materials:
    #     if material.users == 0:
    #         bpy.data.materials.remove(material, do_unlink=True)


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
    if bpy.data.materials.find(shape.rmtc_ceiling_texture) != -1:
        shape.material_slots[0].material = bpy.data.materials[shape.rmtc_ceiling_texture]
    if bpy.data.materials.find(shape.rmtc_floor_texture) != -1:
        shape.material_slots[1].material = bpy.data.materials[shape.rmtc_floor_texture]
    if bpy.data.materials.find(shape.rmtc_wall_texture) != -1:
        shape.material_slots[2].material = bpy.data.materials[shape.rmtc_wall_texture]


def update_shape_precision(shape):
    shape.location.x = round(
        shape.location.x, bpy.context.scene.rmtc_precision)
    shape.location.y = round(
        shape.location.y, bpy.context.scene.rmtc_precision)
    shape.location.z = round(
        shape.location.z, bpy.context.scene.rmtc_precision)

    for v in shape.data.vertices:
        v.co.x = round(v.co.x, bpy.context.scene.rmtc_precision)
        v.co.y = round(v.co.y, bpy.context.scene.rmtc_precision)
        v.co.z = round(v.co.z, bpy.context.scene.rmtc_precision)


def update_shape(shape):
    if shape:
        shape.display_type = 'WIRE'

        update_shape_precision(shape)

        if shape.rmtc_shape_type == 'SECTOR2D':
            update_sector2d(shape)


def get_shapes(collections):
    shapes = []
    for col in collections:
        for obj in col.all_objects:
            if obj.rmtc_shape_type != None:
                if obj.rmtc_shape_type != 'NONE':
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


def create_remove_material():
    newMat = bpy.data.materials.new('REMOVE')
    newMat.name = 'REMOVE'
    newMat.diffuse_color = [1, 0, 1, 1]
    newMat.use_fake_user = True
    return newMat


def eval_shape(shape):
    dg = bpy.context.evaluated_depsgraph_get()
    evalObj = shape.evaluated_get(dg)
    mesh = bpy.data.meshes.new_from_object(evalObj)
    mesh.use_auto_smooth = shape.data.use_auto_smooth
    mesh.auto_smooth_angle = shape.data.auto_smooth_angle

    roomName = "rmtc_" + shape.name
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
    shape.data.materials[0] = bpy.data.materials[bpy.context.scene.rmtc_remove_material]


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

    if bpy.context.scene.rmtc_remove_material != "":
        i = 0
        remove = False
        for m in shape.material_slots:
            if bpy.context.scene.rmtc_remove_material == m.name:
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


def apply_auto_texture(shape, eval):
    mesh = eval.data
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
                luv.uv = rotate2D(luv.uv, shape.rmtc_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_wall_texture_scale_offset[0]), shape.rmtc_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_wall_texture_scale_offset[1]), shape.rmtc_wall_texture_scale_offset[3])
            if faceDirection == "-x":
                luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.rmtc_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_wall_texture_scale_offset[0]), shape.rmtc_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_wall_texture_scale_offset[1]), shape.rmtc_wall_texture_scale_offset[3])
            if faceDirection == "y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.rmtc_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_wall_texture_scale_offset[0]), shape.rmtc_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_wall_texture_scale_offset[1]), shape.rmtc_wall_texture_scale_offset[3])
            if faceDirection == "-y":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                luv.uv = rotate2D(luv.uv, shape.rmtc_wall_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_wall_texture_scale_offset[0]), shape.rmtc_wall_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_wall_texture_scale_offset[1]), shape.rmtc_wall_texture_scale_offset[3])
            if faceDirection == "z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, shape.rmtc_ceiling_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_floor_texture_scale_offset[0]), shape.rmtc_floor_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_floor_texture_scale_offset[1]), shape.rmtc_floor_texture_scale_offset[3])
            if faceDirection == "-z":
                luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                luv.uv = rotate2D(luv.uv, shape.rmtc_floor_texture_rotation)
                luv.uv.x = translate(scale(
                    luv.uv.x, shape.rmtc_ceiling_texture_scale_offset[0]), shape.rmtc_ceiling_texture_scale_offset[2])
                luv.uv.y = translate(scale(
                    luv.uv.y, shape.rmtc_ceiling_texture_scale_offset[1]), shape.rmtc_ceiling_texture_scale_offset[3])

    bm.to_mesh(mesh)
    bm.free()

    eval.data = mesh


def apply_triangulate(shape):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = shape
    shape.select_set(True)

    mod = shape.modifiers.new(name='triangulate', type='TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier='triangulate')


def apply_split_faces(shape):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = shape
    shape.select_set(True)

# FUNCS


# DATA

bpy.types.Scene.rmtc_precision = bpy.props.IntProperty(
    name="Precision",
    default=3,
    min=0,
    max=6,
    description='Controls the rounding level of vertex precisions. A level of 1 would round 1.234 to 1.2 and a level of 2 would round to 1.23'
)
bpy.types.Scene.rmtc_remove_material = bpy.props.StringProperty(
    name="Remove Material",
    description="Material used as flag for removing geometry"
)
bpy.types.Object.rmtc_shape_type = bpy.props.EnumProperty(
    items=[
        ("SECTOR2D", "Sector2D", "is a 2D sector"),
        ("SECTOR3D", "Sector3D", "is a 3D sector"),
        ("BRUSH", "Brush", "is a shape"),
        ("NONE", "None", "none"),
    ],
    name="Shape Type",
    default='NONE'
)
bpy.types.Object.rmtc_split_faces = bpy.props.BoolProperty(
    name="Shape Split Faces",
    default=False,
    description='Splitting faces can be handy in some cases.'
)
bpy.types.Object.rmtc_ceiling_height = bpy.props.FloatProperty(
    name="Ceiling Height",
    default=4,
    step=10,
    precision=3,
    update=_update_sector_solidify
)
bpy.types.Object.rmtc_floor_height = bpy.props.FloatProperty(
    name="Floor Height",
    default=0,
    step=10,
    precision=3,
    update=_update_sector_solidify
)
bpy.types.Object.rmtc_shape_auto_texture = bpy.props.BoolProperty(
    name="Shape Auto Texture",
    default=True,
    description='Auto Texture on or off'
)
bpy.types.Object.rmtc_floor_texture = bpy.props.StringProperty(
    name="Floor Texture",
)
bpy.types.Object.rmtc_wall_texture = bpy.props.StringProperty(
    name="Wall Texture",
)
bpy.types.Object.rmtc_ceiling_texture = bpy.props.StringProperty(
    name="Ceiling Texture",
)
bpy.types.Object.rmtc_ceiling_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Ceiling Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.rmtc_wall_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Wall Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.rmtc_floor_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Floor Texture Scale Offset",
    default=(1, 1, 0, 0),
    min=0,
    step=10,
    precision=3,
    size=4
)
bpy.types.Object.rmtc_ceiling_texture_rotation = bpy.props.FloatProperty(
    name="Ceiling Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.rmtc_wall_texture_rotation = bpy.props.FloatProperty(
    name="Wall Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.rmtc_floor_texture_rotation = bpy.props.FloatProperty(
    name="Floor Texture Rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)


# DATA


# CLASSES


class ROOManticPanel(bpy.types.Panel):
    bl_label = "ROOMantic"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'ROOMantic'

    def draw(self, context):
        obj = context.active_object
        scene = bpy.context.scene
        layout = self.layout

        # base
        col = layout.column(align=True)
        col.label(icon="WORLD", text="Map Settings")
        col.prop(scene, "rmtc_precision")
        col.prop_search(scene, "rmtc_remove_material", bpy.data, "materials")
        col = layout.column(align=True)
        col.operator("scene.rmtc_build", text="Build All", icon="MOD_BUILD").selected_only = False
        col.operator("scene.rmtc_build", text="Build Selected", icon="MOD_BUILD").selected_only = True

        # tools
        col = layout.column(align=True)
        col.label(icon="SNAP_PEEL_OBJECT", text="Tools")
        col.operator("scene.rmtc_open_material",
                     text="Open Material", icon="TEXTURE")
        if bpy.context.mode == 'EDIT_MESH':
            col.operator("object.rmtc_rip_geometry", text="Rip To",
                         icon="UNLINKED").focus_to_rip = True
            col.operator("object.rmtc_rip_geometry", text="Rip Stay",
                         icon="UNLINKED").focus_to_rip = False
        else:
            col.operator("scene.rmtc_new_geometry", text="New Sector2D",
                         icon="MESH_PLANE").shape_type = 'SECTOR2D'
            col.operator("scene.rmtc_new_geometry", text="New Sector3D",
                         icon="CUBE").shape_type = 'SECTOR3D'
            col.operator("scene.rmtc_new_geometry", text="New Brush",
                         icon="MESH_CUBE").shape_type = 'BRUSH'

        # object
        if obj != None:
            col = layout.column(align=True)
            col.label(icon="MOD_ARRAY", text="Shape Properties")
            col.prop(obj, "rmtc_shape_type", text="Shape Type")
            col.prop(obj, "rmtc_split_faces", text="Split Faces")
            col.prop(obj, "rmtc_shape_auto_texture", text="Auto Texture")
            if obj.rmtc_shape_auto_texture:
                col = layout.row(align=True)
                col.prop(obj, "rmtc_ceiling_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "rmtc_wall_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "rmtc_floor_texture_scale_offset")
                col = layout.row(align=True)
                col.prop(obj, "rmtc_ceiling_texture_rotation")
                col = layout.row(align=True)
                col.prop(obj, "rmtc_wall_texture_rotation")
                col = layout.row(align=True)
                col.prop(obj, "rmtc_floor_texture_rotation")
            if obj.rmtc_shape_type == 'SECTOR2D':
                col = layout.column(align=True)
                col.label(icon="MOD_ARRAY", text="Sector Properties")
                col.prop(obj, "rmtc_ceiling_height")
                col.prop(obj, "rmtc_floor_height")
                # layout.separator()
                col = layout.column(align=True)
                col.prop_search(obj, "rmtc_ceiling_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Ceiling")
                col.prop_search(obj, "rmtc_wall_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Wall")
                col.prop_search(obj, "rmtc_floor_texture", bpy.data,
                                "materials", icon="MATERIAL", text="Floor")


class ROOManticBuild(bpy.types.Operator):
    bl_idname = "scene.rmtc_build"
    bl_label = "Build"

    selected_only: bpy.props.BoolProperty(name="selected_only", default=False)

    def execute(self, context):
        # cache selected
        activeObj = context.active_object
        selectedObjs = []
        for obj in context.selected_objects:
            selectedObjs.append(obj)

        # save context
        wasEditMode = False
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            wasEditMode = True

        # The new algo works to achieve this goal: each shape must be its own separate object
        # So we can no longer rely on a global level_geometry object that gets booleaned around by each shape
        # we now need to treat each shape separately

         # make sure remove_materials is present
        if context.scene.rmtc_remove_material == '' or context.scene.rmtc_remove_material is None or context.scene.rmtc_remove_material not in bpy.data.materials:
            context.scene.rmtc_remove_material = create_remove_material().name

        # get output collection
        levelCollection = get_add_collection(context.scene, 'ROOMantic_LEVEL')
        levelCollection.hide_select = False
        shapeCollection = get_add_collection(context.scene, 'ROOMantic_SHAPES')
        shapeCollection.hide_select = False

        # clear output collections
        for obj in levelCollection.objects:
            levelCollection.objects.unlink(obj)
            if obj.rmtc_shape_type != 'NONE':
                context.scene.collection.objects.link(obj)

        # cleanup
        remove_not_used()

        # look for shapes
        shapes = get_shapes(
            [context.scene.collection, levelCollection, shapeCollection])

        # optimizations
        hasBrushes = False

        # loop on shapes
        for shape in shapes:
            # unlink shapes from old collection
            for col in shape.users_collection:
                col.objects.unlink(shape)

            # if has no geom then remove
            if len(shape.data.vertices) < 3:
                shapes.remove(shape)
                continue

            # mark hasbrushes for
            if shape.rmtc_shape_type == 'BRUSH':
                hasBrushes = True

            # update + link shapes
            update_shape(shape)
            shapeCollection.objects.link(shape)

        # cache data: shape-boolean + brush-boolean + bounds (they are just remove_material blobs)
        shapeIntersections = {}
        shapeBooleans = {}
        shapeBounds = {}
        sectorBoolean = create_mesh_obj(
            'sectorBoolean') if hasBrushes else None
        if hasBrushes:
            context.scene.collection.objects.link(sectorBoolean)

        for shape in shapes:
            # init intersections
            shapeIntersections[shape] = []

            # shapeBool
            shapeBoolean = eval_shape(shape)
            make_shape_boolean(shapeBoolean)
            shapeBooleans[shape] = shapeBoolean

            # bounds
            shapeBounds[shape] = calculate_bounds_ws(
                shape.matrix_world, shapeBoolean.data, 0.1)

            # brushBool
            if hasBrushes:
                if shape.rmtc_shape_type != 'BRUSH':
                    apply_csg(sectorBoolean, shapeBoolean, 'UNION')

        # shape intersect map
        for shape0 in shapes:
            if self.selected_only and shape0 not in selectedObjs:
                continue
            for shape1 in shapes:
                if shape0 == shape1:
                    continue

                if shape1 in shapeIntersections[shape0]:
                    continue
                elif shapeBounds[shape0].intersect(shapeBounds[shape1]):
                    shapeIntersections[shape0].append(shape1)

                    if shape0 not in shapeIntersections[shape1]:
                        shapeIntersections[shape1].append(shape0)

        # create/duplicate shapes to output
        for shape0 in shapes:
            if self.selected_only and shape0 not in selectedObjs:
                continue
            # eval shape
            evaluatedShape = eval_shape(shape0)
            evaluatedShape.display_type = 'TEXTURED'
            copy_materials(shape0, evaluatedShape)

            # add remove_material
            removeMaterialIndex = len(evaluatedShape.data.materials)
            set_material_slots_size(evaluatedShape, len(
                evaluatedShape.data.materials) + 1)
            evaluatedShape.data.materials[removeMaterialIndex] = bpy.data.materials[context.scene.rmtc_remove_material]

            # link
            levelCollection.objects.link(evaluatedShape)

            # apply csg
            if shape0.rmtc_shape_type == 'BRUSH':
                for shape1 in shapeIntersections[shape0]:
                    if shape1.rmtc_shape_type == 'BRUSH':
                        apply_csg(evaluatedShape,
                                  shapeBooleans[shape1], 'UNION')
                    else:
                        apply_csg(evaluatedShape, sectorBoolean, 'INTERSECT')
            else:
                for shape1 in shapeIntersections[shape0]:
                    apply_csg(evaluatedShape, shapeBooleans[shape1], 'UNION')
                flip_normals(evaluatedShape)

            apply_remove_material(evaluatedShape)

            apply_triangulate(evaluatedShape)

            if shape0.rmtc_shape_type == 'SECTOR2D' or shape0.rmtc_shape_auto_texture:
                apply_auto_texture(shape0, evaluatedShape)

        # mark unselectable
        levelCollection.hide_select = True

        # restore context
        bpy.ops.object.select_all(action='DESELECT')
        if activeObj != None:
            activeObj.select_set(True)
            bpy.context.view_layer.objects.active = activeObj
        for obj in selectedObjs:
            if obj != None:
                obj.select_set(True)
        if wasEditMode:
            bpy.ops.object.mode_set(mode='EDIT')
        
        # unlink sectorBoolean
        if hasBrushes:
            context.scene.collection.objects.unlink(sectorBoolean)

        return {"FINISHED"}


class ROOManticNewGeometry(bpy.types.Operator):
    bl_idname = "scene.rmtc_new_geometry"
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
        shape.rmtc_shape_type = self.shape_type

        initialize_shape(shape)
        update_shape(shape)

        return {"FINISHED"}


class ROOManticOpenMaterial(bpy.types.Operator, ImportHelper):
    bl_idname = "scene.rmtc_open_material"
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
                newMaterial.use_fake_user = True

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


class ROOManticRipGeometry(bpy.types.Operator):
    bl_idname = "object.rmtc_rip_geometry"
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
        if activeObj.rmtc_shape_type == 'SECTOR2D' and len(selectedFaces) > 0:
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
    bpy.utils.register_class(ROOManticPanel)
    bpy.utils.register_class(ROOManticBuild)
    bpy.utils.register_class(ROOManticNewGeometry)
    bpy.utils.register_class(ROOManticOpenMaterial)
    bpy.utils.register_class(ROOManticRipGeometry)


def unregister():
    bpy.utils.unregister_class(ROOManticPanel)
    bpy.utils.unregister_class(ROOManticBuild)
    bpy.utils.unregister_class(ROOManticNewGeometry)
    bpy.utils.unregister_class(ROOManticOpenMaterial)
    bpy.utils.unregister_class(ROOManticRipGeometry)


if __name__ == "__main__":
    register()
