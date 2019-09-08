'''
Copyright (C) 2016 Łukasz Hoffmann
johnniewooker@gmail.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

'''

import bpy
import bgl
import bmesh
import mathutils
import os 
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import bpy.utils.previews
from bpy.props import StringProperty, EnumProperty
from bpy_extras.view3d_utils import (
    region_2d_to_vector_3d,
    region_2d_to_origin_3d
)


bl_info = {
    "name": "Welder",
    "author": "Łukasz Hoffmann",
    "version": (0,0, 3),
    "location": "View 3D > Object Mode > Tool Shelf",
    "blender": (2, 7, 9),
    "description": "Generate weld along the odge of intersection of two objects",
    "warning": "",
    "category": "Object",
	}

preview_collections = {}

cyclic=True

class WelderDrawOperator(bpy.types.Operator):
    bl_idname = "weld.draw"
    bl_label = "Draw"    
    
    def modal(self, context, event):
        context.area.tag_redraw()        
        
        if event.type == 'LEFTMOUSE' and self.phase==0:
            self.lmb = event.value == 'PRESS'
            self.draw_event  = None
            self.initiated=True
        
        elif event.type == 'MOUSEMOVE' and self.phase==0:
            if self.lmb:
                if get_mouse_3d_on_mesh(self,event,context) is not None:
                    self.mouse_path.append(get_mouse_3d_on_mesh(self,event,context))
 
            #print("test")

        elif event.type == 'RIGHTMOUSE' and event.value in {'RELEASE'} and self.phase==0:
            print("test")
            self.unregister_handlers(context)    
            if not self.initiated:
                return {'FINISHED'}
            context = bpy.context
            scene = context.scene
            gp = scene.grease_pencil
            if not gp:
                gp = bpy.data.grease_pencil.new("GP")
                scene.grease_pencil = gp

            # Reference grease pencil layer or create one of none exists
            if gp.layers:
                gpl = gp.layers[0]
            else:
                gpl = gp.layers.new('Welding_Curve', set_active = True )

            # Reference active GP frame or create one of none exists    
            if gpl.active_frame:
                fr = gpl.active_frame
            else:
                fr = gpl.frames.new(0) 

            # Create a new stroke
            str = fr.strokes.new()
            str.draw_mode = '3DSPACE'
            str.line_width = 1 # default 3
            
            str.points.add(len(self.mouse_path))
            for p0, p in zip(self.mouse_path, str.points):
                p.co = p0  
            bpy.ops.gpencil.convert(type='PATH', use_timing_data=False)
            bpy.ops.gpencil.data_unlink()             
              
            #set proper radius
            bpy.context.scene.objects.active = bpy.context.selected_objects[0]
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.radius_set(radius=1)
            if cyclic: bpy.ops.curve.cyclic_toggle()
            bpy.ops.object.mode_set(mode='OBJECT')            
            curve=bpy.context.scene.objects.active
            

            edge_length=CalculateCurveLength(curve)
            matrix=curve.matrix_world  
            MakeWeldFromCurve(curve,edge_length,self.obje,matrix)  
              
            self.phase=1  
            return bpy.ops.weld.translate('INVOKE_DEFAULT')
        

        elif event.type in {'ESC'} and self.phase==0:
            self.unregister_handlers(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.phase=0
        self.obje='' 
        iconname=bpy.context.scene.my_thumbnails
        if iconname=='icon_1.png': self.obje='Weld_1'
        if iconname=='icon_2.png': self.obje='Weld_2'
        if iconname=='icon_3.png': self.obje='Weld_3'
        if iconname=='icon_4.png': self.obje='Weld_4'
        if iconname=='icon_5.png': self.obje='Weld_5'
        if self.obje=='': return {'FINISHED'}
        self.lmb = False
        self.initiated=False
        bpy.ops.object.select_all(action='DESELECT')
        if not context.active_object:
            self.report({'WARNING'}, "no object")
            return {'CANCELLED'}         
        if context.area.type == 'VIEW_3D' and context.active_object.type=='MESH':
            
            self.bvhtree = bvhtree_from_object(self,context, context.active_object)
            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_VIEW')

            self.mouse_path = []

            context.window_manager.modal_handler_add(self)
            self.draw_event = context.window_manager.event_timer_add(0.1, window=context.window)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

    def unregister_handlers(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        #context.window_manager.event_timer_remove(self.draw_event)
        self.draw_event  = None

class WeldTransformModal(bpy.types.Operator):
    bl_idname = "weld.translate"
    bl_label = "Weld modal transform"
    #def execute(self, context):
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if (self.phase==1):
                self.offset = (self._initial_mouse - Vector((event.mouse_x, event.mouse_y, 0.0))) * 0.02
                multiplificator=(self.offset).length
                if(multiplificator<1):multiplificator=1            
                self.OBJ_WELD.scale[0]=multiplificator
                self.OBJ_WELD.scale[1]=multiplificator
                self.OBJ_WELD.scale[2]=multiplificator
                self.array=self.OBJ_WELD.modifiers["array"]
                self.array.count=int(self.old_count/multiplificator)+1
            if (self.phase==2):
                self.offset = (self._initial_mouse - Vector((event.mouse_x, event.mouse_y, 0.0))) * 0.02
                multiplificator=(self.offset).length
                self.OBJ_WELD.rotation_euler[0]=multiplificator
        elif event.type == 'LEFTMOUSE' and event.value in {'RELEASE'}:    
            if (self.phase==2):
                return {'FINISHED'}   
            if (self.phase==1):
                self.phase=2
                self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
                return {'RUNNING_MODAL'} 
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value in {'RELEASE'}:
            if (self.phase==2):
                self.OBJ_WELD.rotation_euler[0]=0    
                return {'CANCELLED'}
            if (self.phase==1):
                self.OBJ_WELD.scale[0]=1
                self.OBJ_WELD.scale[1]=1
                self.OBJ_WELD.scale[2]=1
                self.array=self.OBJ_WELD.modifiers["array"]
                self.array.count=self.old_count
                self.phase=2
                self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
                return {'RUNNING_MODAL'}             
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
        self.OBJ_WELD=bpy.context.selected_objects[0]
        self.array=self.OBJ_WELD.modifiers["array"]
        self.old_count=self.array.count
        self.phase=1
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}        
      
        
class OBJECT_OT_RotateButton(bpy.types.Operator):
    bl_idname = "weld.rotate"
    bl_label = "Rotate weld"
    country = bpy.props.StringProperty()
 
    def execute(self, context):  
        bpy.ops.curve.switch_direction()
        return {'FINISHED'} 
                      
class OBJECT_OT_WeldButton(bpy.types.Operator):
    bl_idname = "weld.weld"    
    #obje = bpy.props.StringProperty()  
    
    
    bl_label = "Weld"
    
    
    def execute(self, context):
        obje='' 
        iconname=bpy.context.scene.my_thumbnails
        if iconname=='icon_1.png': obje='Weld_1'
        if iconname=='icon_2.png': obje='Weld_2'
        if iconname=='icon_3.png': obje='Weld_3'
        if iconname=='icon_4.png': obje='Weld_4'
        if iconname=='icon_5.png': obje='Weld_5'
        if obje=='': return {'FINISHED'}
        def is_inside(p, obj):
            max_dist = 1.84467e+19
            found, point, normal, face = obj.closest_point_on_mesh(p, max_dist)
            p2 = point-p
            v = p2.dot(normal)
            #print(v)
            return not(v < 0.0001)
        objects = bpy.data.objects
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) 
        OBJ1=bpy.context.selected_objects[0]
        matrix=OBJ1.matrix_world
        OBJ2=bpy.context.selected_objects[1]
        bpy.ops.object.duplicate()
        OBJ3=bpy.context.selected_objects[0]
        OBJ4=bpy.context.selected_objects[1]
        bool_two = OBJ1.modifiers.new(type="BOOLEAN", name="bool 2")
        bool_two.object = OBJ2
        bool_two.operation = 'INTERSECT'
        bpy.context.scene.objects.active = OBJ1
        bpy.ops.object.modifier_apply (modifier='bool 2')
        bpy.ops.object.select_all(action = 'DESELECT')
        OBJ2.select = True
        bpy.ops.object.delete()
        bpy.context.scene.objects.active = OBJ1
        OBJ1.select = True
        vertices1 = OBJ1.data.vertices
        #poczatek sprawdzania kolizji z pierwszym obiektem
        list=[]
        for v in vertices1:
            #print (is_inside(mathutils.Vector(v.co), OBJ3))
            #print (v.index)
            if (is_inside(mathutils.Vector(OBJ3.matrix_world*v.co), OBJ3)==True):
                list.append(v.index)
            if (is_inside(mathutils.Vector(OBJ4.matrix_world*v.co), OBJ4)==True):
                list.append(v.index)    
            continue
        #print ("Koniec liczenia")
        
        bpy.ops.object.mode_set(mode = 'EDIT')
        bm1 = bmesh.from_edit_mesh(OBJ1.data)
        vertices2 = bm1.verts

        for vert in vertices2:
            vert.select=False
            continue
         
        bm1.verts.ensure_lookup_table()    
        for vert2 in list:
           vertices2[vert2].select=True   
        #koniec sprawdzania kolizji z pierwszym obiektem   
         
        bpy.ops.mesh.delete(type='VERT') # usuwanie wierzcholkow

        bpy.ops.mesh.select_mode(type="EDGE")
        for f in bm1.faces:
            f.select=False
        #bpy.ops.mesh.delete(type='FACE') # usuwanie wierzcholkow 

        def search(mymesh):
                culprits=[]
                for e in mymesh.edges:
                        e.select = False
                        shared = 0
                        for f in mymesh.faces:
                                for vf1 in f.verts:
                                        if vf1 == e.verts[0]:
                                                for vf2 in f.verts:
                                                        if vf2 == e.verts[1]:
                                                                shared = shared + 1
                        if (shared > 2):
                                #Manifold
                                culprits.append(e)
                                e.select = True
                        if (shared < 2):
                                #Open
                                culprits.append(e)
                                e.select = True
                return culprits

        search(bm1)
        for f in bm1.edges:
            f.select=not f.select

        bpy.ops.mesh.delete(type='EDGE') # usuwanie wielokątow    


        #POPRAWKA DO SKRYPTU MANIFOLD - USUWANIE TROJKATOW PRZY KRAWEDZIACH
        bpy.ops.mesh.select_mode(type="EDGE")

        for e in bm1.edges:
            e.select=False
            shared=0
            for v in e.verts:        
                for ed in v.link_edges:
                    shared=shared+1        
            if (shared==6):
                e.select=True  
        bpy.ops.mesh.delete(type='EDGE') # usuwanie wielokątow 

        for v in bm1.edges:
            v.select=True
        
        bpy.ops.object.mode_set(mode = 'OBJECT')

        _data = bpy.context.active_object.data
            
        edge_length = 0
        for edge in _data.edges:
            vert0 = _data.vertices[edge.vertices[0]].co
            vert1 = _data.vertices[edge.vertices[1]].co
            edge_length += (vert0-vert1).length
        
        edge_length = '{:.6f}'.format(edge_length)
        #print(edge_length)
        #print(OBJ1.matrix_world)
        bpy.ops.object.convert(target="CURVE")
        bpy.ops.object.scale_clear()
        bpy.ops.object.select_all()
        
        MakeWeldFromCurve(OBJ1,edge_length,obje,matrix)
        
        return bpy.ops.weld.translate('INVOKE_DEFAULT')

def addprop(object):    
    object["Weld"]="True"

def CalculateCurveLength(curve):
    matrix=curve.matrix_world
    edge_length = 0
    counter=0
    for s in curve.data.splines:
        for point in s.points:
            if counter>0:
                p0=s.points[counter-1].co
                p1=s.points[counter].co
                edge_length += (p0-p1).length
            counter=counter+1
        if cyclic:
            p0=s.points[counter-1].co
            p1=s.points[0].co
            edge_length += (p0-p1).length      
         
    edge_length = '{:.6f}'.format(edge_length)        
    return(edge_length)

def MakeWeldFromCurve(OBJ1,edge_length,obje,matrix):
    current_path = os.path.dirname(os.path.realpath(__file__))
    blendfile = os.path.join(current_path, "weld.blend")  #ustawic wlasna sciezke!        
    section   = "\\Object\\"
    if (obje==''):
        object="Weld_1"
    else:
        object=obje
    filepath  = blendfile + section + object
    directory = blendfile + section
    filename  = object

    bpy.ops.wm.append(
        filepath=filepath, 
        filename=filename,
        directory=directory)
    print(filepath)    
    OBJ_WELD=bpy.context.selected_objects[0]
    OBJ_WELD.matrix_world=matrix
    addprop(OBJ_WELD)
    array = OBJ_WELD.modifiers.new(type="ARRAY", name="array")
    array.use_merge_vertices=True
    array.use_relative_offset=False
    array.use_constant_offset=True
    array.merge_threshold=0.0001
    #count=int(int(float(edge_length))*2)
    count=int(float(edge_length)/0.04331)+1
    array.count=count
    #array.relative_offset_displace[0]=0.83        
    offset=0.04331
    if object=="Weld_3": offset=0.1
    array.constant_offset_displace[0]=offset
    curve=OBJ_WELD.modifiers.new(type="CURVE", name="curve")
    curve.object=OBJ1
    OBJ1.data.resolution_u=int(count/2)
    bpy.data.objects[OBJ_WELD.name].select=True
    bpy.context.scene.objects.active = OBJ1
    bpy.ops.object.modifier_apply(modifier='array')
    #bpy.ops.object.modifier_apply(modifier='curve')
    bpy.ops.object.select_all(action = 'DESELECT')
    OBJ_WELD.select = True
    bpy.context.scene.objects.active=OBJ_WELD    
    #bpy.ops.object.delete()
    #bpy.ops.object.mode_set(mode = 'EDIT')     

def draw_callback_px(self, context):

    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glColor4f(0.0, 0.0, 0.0, 0.8)    
    bgl.glShadeModel(bgl.GL_SMOOTH)
    bgl.glLineWidth(3)
    bgl.glBegin(bgl.GL_LINE_STRIP)

    for x,y,z in self.mouse_path:        
        bgl.glVertex3f(x, y,z)
    bgl.glEnd()

    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
  
def get_origin_and_direction(self,event,context):
    region=context.region
    region_3d=context.space_data.region_3d
    mouse_coord=(event.mouse_region_x,event.mouse_region_y)
    origin=region_2d_to_origin_3d(region,region_3d,mouse_coord)
    direction=region_2d_to_vector_3d(region,region_3d,mouse_coord)
    return origin,direction

def get_mouse_3d_on_mesh(self,event,context):
    origin,direction=get_origin_and_direction(self,event,context)
    self.hit,self.normal, *_ =self.bvhtree.ray_cast(origin,direction)
    return self.hit

def bvhtree_from_object(self, context, object):
        bm = bmesh.new()
        mesh = object.data
        bm.from_mesh(mesh)
        bm.transform(object.matrix_world)
        bvhtree = BVHTree.FromBMesh(bm)
        return bvhtree

def generate_previews():
    # We are accessing all of the information that we generated in the register function below
    pcoll = preview_collections["thumbnail_previews"]
    image_location = pcoll.images_location
    VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg')
    
    enum_items = []
    
    # Generate the thumbnails
    for i, image in enumerate(os.listdir(image_location)):
        if image.endswith(VALID_EXTENSIONS):
            filepath = os.path.join(image_location, image)
            thumb = pcoll.load(filepath, filepath, 'IMAGE')
            enum_items.append((image, image, "", thumb.icon_id, i))
            
    return enum_items
   
def register():
    pcoll = bpy.utils.previews.new()
    images_path = pcoll.images_location = os.path.join(os.path.dirname(__file__), "welder_images")
    pcoll.images_location = bpy.path.abspath(images_path)
    preview_collections["thumbnail_previews"] = pcoll
    bpy.types.Scene.my_thumbnails = EnumProperty(
    items=generate_previews(),
    )
    bpy.utils.register_class(WeldTransformModal)
    bpy.utils.register_class(OBJECT_OT_WeldButton)
    bpy.utils.register_class(WelderDrawOperator)

def unregister():
    bpy.utils.unregister_class(WeldTransformModal)
    bpy.utils.unregister_class(OBJECT_OT_WeldButton)
    bpy.utils.unregister_class(WelderDrawOperator)

register()

class WelderToolsPanel(bpy.types.Panel):
    bl_label = "Welder"
    bl_idname = "OBJECT_Welder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Welder"
 
    def draw(self, context):
        row=self.layout.row()
        row.template_icon_view(context.scene, "my_thumbnails")
        self.layout.operator("weld.weld")
        self.layout.operator("weld.draw")
    
def register():
	bpy.utils.register_class(WelderToolsPanel)	

def unregister():
    bpy.utils.unregister_class(WelderToolsPanel)              

if __name__ == "__main__":
    register()