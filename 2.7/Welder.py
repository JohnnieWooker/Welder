'''
Copyright (C) 2016 Łukasz Hoffmann
johnniewooker@gmail.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

'''




import bpy
import bmesh
import mathutils
import os 
from mathutils import Vector

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
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
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
    obje = bpy.props.StringProperty()   
    bl_label = "Weld"
    def execute(self, context):
        
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
	
        current_path = os.path.dirname(os.path.realpath(__file__))
        blendfile = os.path.join(current_path, "weld.blend")  #ustawic wlasna sciezke!        
        section   = "\\Object\\"
        if (self.obje==''):
            object="Plane"
        else:
            object=self.obje

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
        array = OBJ_WELD.modifiers.new(type="ARRAY", name="array")
        array.use_merge_vertices=True
        array.use_relative_offset=False
        array.use_constant_offset=True
        array.merge_threshold=0.0001
        #count=int(int(float(edge_length))*2)
        count=int(float(edge_length)/0.04331)+1
        array.count=count
        #array.relative_offset_displace[0]=0.83        
        array.constant_offset_displace[0]=0.04331
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
        
        return bpy.ops.weld.translate('INVOKE_DEFAULT')
   
def register():
    bpy.utils.register_class(WeldTransformModal)
    bpy.utils.register_class(OBJECT_OT_WeldButton)
    bpy.utils.register_class(OBJECT_OT_RotateButton)

def unregister():
    bpy.utils.unregister_class(WeldTransformModal)
    bpy.utils.unregister_class(OBJECT_OT_WeldButton)
    bpy.utils.unregister_class(OBJECT_OT_RotateButton)

register()

class WelderToolsPanel(bpy.types.Panel):
    bl_label = "Welder"
    bl_idname = "OBJECT_Welder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Welder"
 
    def draw(self, context):
        self.layout.operator("weld.weld").obje = "Plane"
        self.layout.operator("weld.weld").obje = "Plane.001"
        self.layout.operator("weld.rotate")

def register():
	bpy.utils.register_class(WelderToolsPanel)	

def unregister():
    bpy.utils.unregister_class(WelderToolsPanel)              

if __name__ == "__main__":
    register()