﻿'''
Copyright (C) 2016 Łukasz Hoffmann
johnniewooker@gmail.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

'''

import bpy
import bgl
import blf
import bmesh
import mathutils
import os 
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import bpy.utils.previews
from math import (sin,pow,floor,ceil,floor)
from bpy.props import StringProperty, EnumProperty
from bpy_extras.view3d_utils import (
    region_2d_to_vector_3d,
    region_2d_to_origin_3d,
    region_2d_to_location_3d
)


bl_info = {
    "name": "Welder",
    "author": "Łukasz Hoffmann",
    "version": (1,0, 7),
    "location": "View 3D > Object Mode > Tool Shelf",
    "blender": (2, 7, 9),
    "description": "Generate weld along the odge of intersection of two objects",
    "warning": "",
    "category": "Object",
	}
preview_collections = {}
curve_node_mapping = {}
bpy.types.Scene.shapebuttonname=bpy.props.StringProperty(name="Shape button name", default="Modify")
bpy.types.Scene.welddrawing=bpy.props.BoolProperty(
        name="welddrawing", description="welddrawing", default=False)
bpy.types.Scene.shapemodified=bpy.props.BoolProperty(
        name="shapemodified", description="shapemodified", default=False)        
simplify_error=0.001
lattice_error_thresh=0.0001


class WelderDrawOperator(bpy.types.Operator):
    bl_idname = "weld.draw"
    bl_label = "Draw"   
    
    def modal(self, context, event):
        if (context.area==None):
            try:
                self.unregister_handlers(context)
            except:
                "Finished"    
            bpy.context.scene.welddrawing=False
            for km in self.list: km.active = True
            return {'CANCELLED'}    
        context.area.tag_redraw()        
        
        if event.type == 'LEFTMOUSE' and self.phase==0:
            self.lmb = event.value == 'PRESS'
            self.draw_event  = None
            self.initiated=True
        
        elif event.type == 'MOUSEMOVE' and self.phase==0:
            if self.lmb:
                if get_mouse_3d_on_mesh(self,event,context) is not None:
                    ishit,hit=get_mouse_3d_on_mesh(self,event,context)
                    if (ishit): self.mouse_path.append(hit)
 
            #print("test")

        elif (event.type == 'RIGHTMOUSE' or event.type == 'RET') and event.value in {'RELEASE'} and self.phase==0:
            cyclic=bpy.context.scene.cyclic
            self.unregister_handlers(context)    
            if not self.initiated:
                for km in self.list: km.active = True
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
            
            SimplifyCurve(curve,simplify_error)
            edge_length=CalculateCurveLength(curve,bpy.context.scene.cyclic)            
            matrix=curve.matrix_world  
            MakeWeldFromCurve(curve,edge_length,self.obje,matrix)  
              
            self.phase=1  
            for km in self.list: km.active = True
            return bpy.ops.weld.translate('INVOKE_DEFAULT')
        

        elif event.type in {'ESC'} and self.phase==0:
            self.unregister_handlers(context)
            bpy.context.scene.welddrawing=False
            for km in self.list: km.active = True
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):   
        self.x = context.window_manager.keyconfigs['Blender'].keymaps['3D View'].keymap_items
        self.list = [keymap for keymap in self.x if keymap.type == 'LEFTMOUSE' or keymap.type == 'RIGHTMOUSE' or keymap.type == 'ACTIONMOUSE' or keymap.type == 'SELECTMOUSE']
        for km in self.list: km.active = False     
        self.phase=0
        self.obje='' 
        iconname=bpy.context.scene.my_thumbnails
        if iconname=='icon_1.png': self.obje='Weld_1'
        if iconname=='icon_2.png': self.obje='Weld_2'
        if iconname=='icon_3.png': self.obje='Weld_3'
        if iconname=='icon_4.png': self.obje='Weld_4'
        if iconname=='icon_5.png': self.obje='Weld_5'
        if self.obje=='': return {'FINISHED'}
        if bpy.context.scene.type=='Decal': self.obje=self.obje+'_decal'
        self.lmb = False
        self.initiated=False
        if (bpy.context.object!=None):
            if (bpy.context.object.mode!='OBJECT'): bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        """
        if not context.active_object:
            self.report({'WARNING'}, "no object")
            return {'CANCELLED'}         
        """
        if context.area.type == 'VIEW_3D':
            bpy.context.scene.welddrawing=True
            #self.bvhtree = bvhtree_from_object(self,context, context.active_object)
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
            for km in self.list: km.active = True
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

    def unregister_handlers(self, context):
        for km in self.list: km.active = True
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
                for i in range(len(self.OBJ_WELD)):
                    if len(self.array)==len(self.OBJ_WELD):    
                        self.OBJ_WELD[i].scale[0]=multiplificator
                        self.OBJ_WELD[i].scale[1]=multiplificator
                        self.OBJ_WELD[i].scale[2]=multiplificator
                        self.array[i]=self.OBJ_WELD[i].modifiers["array"]
                        self.array[i].count=int(self.old_count[i]/multiplificator)+1
            if (self.phase==2):
                self.offset = (self._initial_mouse - Vector((event.mouse_x, event.mouse_y, 0.0))) * 0.02
                multiplificator=(self.offset).length
                for i in range(len(self.OBJ_WELD)):
                    self.OBJ_WELD[i].rotation_euler[0]=multiplificator
        elif event.type == 'LEFTMOUSE' and event.value in {'RELEASE'}:    
            if (self.phase==2):
                bpy.context.scene.welddrawing=False
                return {'FINISHED'}   
            if (self.phase==1):
                self.phase=2
                self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
                return {'RUNNING_MODAL'} 
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value in {'RELEASE'}:
            if (self.phase==2):
                for i in range(len(self.OBJ_WELD)):
                    self.OBJ_WELD[i].rotation_euler[0]=0    
                bpy.context.scene.welddrawing=False
                return {'CANCELLED'}
            if (self.phase==1):
                for i in range(len(self.OBJ_WELD)):
                    if len(self.array)==len(self.OBJ_WELD):   
                        self.OBJ_WELD[i].scale[0]=1
                        self.OBJ_WELD[i].scale[1]=1
                        self.OBJ_WELD[i].scale[2]=1
                        self.array[i]=self.OBJ_WELD[i].modifiers["array"]
                        self.array[i].count=self.old_count[i]
                self.phase=2
                self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
                return {'RUNNING_MODAL'}             
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
        self.OBJ_WELD=bpy.context.selected_objects
        self.array=[m.modifiers["array"] for m in self.OBJ_WELD]
        self.old_count=[a.count for a in self.array]
        self.phase=1
        if context.space_data.type == 'VIEW_3D':
            bpy.context.scene.welddrawing=True
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            bpy.context.scene.welddrawing=False
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
        preserve=True
        edit=False
        objectstodel=bpy.context.selected_objects
        if (bpy.context.object==None):
            self.report({'ERROR'}, 'Invalid context or nothing selected')
            return {'FINISHED'}    
        if (bpy.context.object.mode=='EDIT'):
            edit=True
            if (bpy.context.scene.objects.active.type=='CURVE'):
                bpy.ops.object.mode_set(mode = 'OBJECT')
            else:                    
                if bpy.context.scene.objects.active.type=='MESH':
                    if absoluteselection(bpy.context.scene.objects.active):                         
                        preserve=False
                        objectstodel=bpy.context.selected_objects
                    else:
                        if (not isanythingselected(bpy.context.scene.objects.active)):
                            self.report({'ERROR'}, 'Nothing selected, aborting')
                            return {'FINISHED'}     
                        bpy.ops.mesh.duplicate()
                        bpy.ops.mesh.separate(type='SELECTED')
                        bpy.ops.object.mode_set(mode='OBJECT')
                        originobj=bpy.context.scene.objects.active
                        obj=bpy.context.selected_objects[0]
                        bpy.context.scene.objects.active = obj
                        originobj.select=False  
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.separate(type='LOOSE')
                        bpy.ops.object.mode_set(mode='OBJECT')
                        if (obj.type=='MESH' and (len(obj.data.polygons)>0 or not iscontinuable(obj))):                    
                            bpy.ops.object.delete()
                            bpy.context.scene.objects.active=originobj
                            bpy.ops.object.mode_set(mode='EDIT')
                            self.report({'ERROR'}, 'Detected wrong selection or not an edgeloop, aborting')
                            return {'FINISHED'} 
                              
        if (bpy.context.object.mode!='OBJECT'):
            self.report({'ERROR'}, 'Welding works only in edit or object mode')
            return {'FINISHED'}
        curves=0
        for o in bpy.context.selected_objects:
            if (o.type=='CURVE'): curves=curves+1
        if len(bpy.context.selected_objects)==curves: edit=True
        if (len(bpy.context.selected_objects)>0 and edit):
            obj=bpy.context.selected_objects
            bpy.ops.object.select_all(action = 'DESELECT')
            for o in obj:
                o.select=True
                bpy.context.scene.objects.active = o
                if (o.type=='MESH' and len(o.data.polygons)==0):
                    bpy.ops.object.convert(target='CURVE')
                    bpy.ops.object.select_all(action = 'DESELECT')
            obje='' 
            iconname=bpy.context.scene.my_thumbnails
            if iconname=='icon_1.png': obje='Weld_1'
            if iconname=='icon_2.png': obje='Weld_2'
            if iconname=='icon_3.png': obje='Weld_3'
            if iconname=='icon_4.png': obje='Weld_4'
            if iconname=='icon_5.png': obje='Weld_5'
            if obje=='': return {'FINISHED'}   
            if bpy.context.scene.type=='Decal': obje=obje+'_decal'   
            welds=[]  
            print("test")  
            for o in obj: 
                if (o.type=='CURVE'): 
                    o.select=True                      
                    bpy.context.scene.objects.active = o
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.curve.select_all(action='SELECT')
                    bpy.ops.curve.radius_set(radius=1)
                    bpy.ops.object.mode_set(mode='OBJECT')            
                    edge_length=CalculateCurveLength(o,o.data.splines[0].use_cyclic_u)
                    matrix=o.matrix_world  
                    welds.append(MakeWeldFromCurve(o,edge_length,obje,matrix))
            for o in welds:   
                o.select=True                      
                bpy.context.scene.objects.active = o
            return bpy.ops.weld.translate('INVOKE_DEFAULT')
            return {'FINISHED'}
        if (len(bpy.context.selected_objects)!=2):
            self.report({'ERROR'}, 'Select 2 objects or spline')
            return {'FINISHED'}
        else:    
            obje='' 
            iconname=bpy.context.scene.my_thumbnails
            if iconname=='icon_1.png': obje='Weld_1'
            if iconname=='icon_2.png': obje='Weld_2'
            if iconname=='icon_3.png': obje='Weld_3'
            if iconname=='icon_4.png': obje='Weld_4'
            if iconname=='icon_5.png': obje='Weld_5'
            if obje=='': return {'FINISHED'}
            if bpy.context.scene.type=='Decal': obje=obje+'_decal'
            def is_inside(p, obj):
                max_dist = 1.84467e+19
                found, point, normal, face = obj.closest_point_on_mesh(p, max_dist)
                p2 = point-p
                v = p2.dot(normal)
                #print(v)
                return not(v < 0.0001)
            bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked":False, "mode":'TRANSLATION'}, TRANSFORM_OT_translate={"value":(0, 0, 0), "constraint_axis":(False, False, False), "constraint_orientation":'GLOBAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "texture_space":False, "remove_on_cancel":False, "release_confirm":False, "use_accurate":False})
            selectedobjects=bpy.context.selected_objects
            for o in selectedobjects: applymods(o)
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
            
            guides=separateloose(OBJ1)
            
            for g in guides: g.select=True
            bpy.ops.object.convert(target="CURVE")
            bpy.ops.object.scale_clear()
            bpy.ops.object.select_all()
            
            listofwelds=[]
            
            for g in guides: listofwelds.append(MakeWeldFromCurve(g,edge_length,obje,matrix))
            
            for o in listofwelds: o.select=True
            
            
            removebyobj(OBJ3)
            removebyobj(OBJ4)
            
            
            return bpy.ops.weld.translate('INVOKE_DEFAULT')

class OBJECT_OT_ShapeModifyButton(bpy.types.Operator):
    bl_idname = "weld.shape"   
    bl_label = "Modify"
    def execute(self, context):
        bpy.context.scene.shapebuttonname
        bpy.context.scene.shapemodified=not bpy.context.scene.shapemodified
        if bpy.context.scene.shapemodified:             
            bpy.context.scene.shapebuttonname="Apply"
            WeldNodeTree()
            WeldCurveData('WeldCurve',self)
            bpy.ops.weld.shapemodal()            
        else: 
            
            bpy.context.scene.shapebuttonname="Modify"
            removenode()
        return{'FINISHED'}

class OBJECT_OT_OptimizeButton(bpy.types.Operator):
    bl_idname = "weld.optimize"   
    bl_label = "Add plane for baking"
    def execute(self, context):
        OBJ_Source=bpy.context.scene.objects.active
        location=OBJ_Source.location
        rotation=OBJ_Source.rotation_euler
        scale=OBJ_Source.scale
        current_path = os.path.dirname(os.path.realpath(__file__))
        blendfile = os.path.join(current_path, "weld.blend")  #ustawic wlasna sciezke!        
        section   = "\\Object\\"
        object="Weld_plain"
        filepath  = blendfile + section + object
        directory = blendfile + section
        filename  = object
        bpy.ops.wm.append(
            filepath=filepath, 
            filename=filename,
            directory=directory)
        OBJ_Weld_plain=bpy.context.selected_objects[0]    
        OBJ_Weld_plain.location=location
        OBJ_Weld_plain.rotation_euler=rotation
        OBJ_Weld_plain.scale=scale
        source_array=OBJ_Source.modifiers["array"]
        source_curve=OBJ_Source.modifiers["curve"]        
        array = OBJ_Weld_plain.modifiers.new(type="ARRAY", name="array")
        array.use_merge_vertices=True
        array.use_relative_offset=True
        array.merge_threshold=0.0001
        curve=source_curve.object
        edge_length=CalculateCurveLength(curve,curve.data.splines[0].use_cyclic_u)
        segment_length=0.015*OBJ_Weld_plain.scale[0]
        count=ceil(float(edge_length)/segment_length)
        array.count=count  
        curvemod=OBJ_Weld_plain.modifiers.new(type="CURVE", name="curve")
        curvemod.object=curve
        return{'FINISHED'}

class ShapeModifyModal(bpy.types.Operator):
    bl_idname = "weld.shapemodal"
    bl_label = "Weld shape modify modal"
    _timer = None
    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} or not bpy.context.scene.shapemodified:
            self.cancel(context)
            return {'CANCELLED'}
        if event.type == 'TIMER':
            #storing data inside custom property
            counter=0
            list=[]
            for i in range(len(bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points)):
                list.append(bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i].location[0])
                list.append(bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i].location[1])
                counter=counter+2
            self.obj["shape_points"]=list
            #translating curve position into world position
            translatepoints(self.obj_lattice,matrixtolist(list),lattice_error_thresh)
                        
        return {'PASS_THROUGH'}
    def cancel(self, context):
        removenode()
        bpy.context.scene.shapemodified=False
        bpy.context.scene.shapebuttonname="Modify"
        wm = context.window_manager
        wm.event_timer_remove(self._timer)    
    def execute(self, context):
        obj=bpy.context.scene.objects.active
        lattice_presence=False
        lattice=None 
        dimensions=obj.dimensions       
        if ("Dimensions" in obj):
            dimensions=obj["Dimensions"]
        if ("shape_points" not in obj):
            obj["shape_points"]=[0,0.5,1,0.5]         
        #lattice modifier check       
        for m in obj.modifiers:
            if (m.type=='LATTICE'):
                lattice_presence=True
                lattice=m
        if not lattice_presence:
            lattice=obj.modifiers.new(name="Lattice", type='LATTICE') 
        #lattice object addition
        if lattice.object==None:  
            bpy.ops.object.add(type='LATTICE', view_align=False, enter_editmode=False, location=obj.location, layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
            obj_lattice=bpy.context.scene.objects.active
            hidemods(obj,False)  
            print(dimensions)
            obj_lattice.rotation_euler=obj.rotation_euler
            obj_lattice.rotation_euler[0]=obj_lattice.rotation_euler[0]+0.785398163
            obj_lattice.dimensions=(dimensions[0]*obj.scale[0],dimensions[1]*obj.scale[1],dimensions[2]*obj.scale[2])
            obj_lattice.location=getcenterofmass(obj)
            hidemods(obj,True)  
            lattice.object=obj_lattice    
        obj_lattice=lattice.object          
        self.obj=obj
        self.obj_lattice=obj_lattice   
        bpy.context.scene.objects.active=obj   
        makemodfirst(lattice)
        #change lattice matrix 
        obj_lattice.data.points_u=1
        obj_lattice.data.points_v=1
        obj_lattice.data.points_w=2     
        #define starting curve        
        '''
        for p in c.points:
            p.location=(p.location[0],0.5)
            '''  
        bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[0].location=(0,0.5)
        bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[-1].location=(1,0.5)
        bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.update()
        if (len(obj["shape_points"])>3):
            bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[0].location=(obj["shape_points"][0],obj["shape_points"][1])
            bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[-1].location=(obj["shape_points"][-2],obj["shape_points"][-1])
            if (len(obj["shape_points"])>5 and len(obj["shape_points"])%2==0):
                counter=2
                for i in range(floor((len(obj["shape_points"])-4)/2)): 
                    comparision_tuple=(bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i+1].location[0],bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i+1].location[1])
                    if (comparision_tuple!=(obj["shape_points"][counter],obj["shape_points"][counter+1])):
                        bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points.new(obj["shape_points"][counter],obj["shape_points"][counter+1])
                    counter=counter+2
            bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.update() 
        #starting curve defined according to custom property of weld object   
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}    

def applymods(obj):
    oldselected=bpy.context.selected_objects
    oldactive=bpy.context.scene.objects.active
    for m in obj.modifiers:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select = True
        bpy.context.scene.objects.active = obj
        bpy.ops.object.modifier_apply(apply_as='DATA',modifier=m.name)
    bpy.context.scene.objects.active=oldactive
    for o in oldselected: o.select=True
    
def separateloose(obj):    
    selected=bpy.context.selected_objects
    active=bpy.context.scene.objects.active
    bpy.ops.object.select_all(action = 'DESELECT')
    bpy.context.scene.objects.active=obj
    obj.select=True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    separated=bpy.context.selected_objects
    bpy.ops.object.select_all(action = 'DESELECT')
    for s in selected: s.select=True
    bpy.context.scene.objects.active=active
    return separated

def hidemods(obj,hide):
    for m in obj.modifiers:
        m.show_viewport=hide

def matrixtolist(matrix):
    list=[]
    x=0
    y=0 
    for i in range(len(matrix)):
        if (i%2==0): 
            x=matrix[i]
        if (i%2==1): 
            y=matrix[i]
        if (i%2==1):list.append(Vector((x,y)))    
    return list

def translatepoints(lattice,points,error):    
    for i in range(len(points)):
        points[i][1]=points[i][1]-0.5
        points[i][1]=points[i][1]*-1
        #points[i][1]=points[i][1]*-(0.72393)   
        points[i][0]=points[i][0]-0.5
    lattice.data.points_w=len(points)        
    for i in range(lattice.data.points_w):
        if (abs(abs(lattice.data.points[i].co_deform.y)-abs(points[i][1]))>error): lattice.data.points[i].co_deform.y=points[i][1]
        if (abs(abs(lattice.data.points[i].co_deform.z)-abs(points[i][0]))>error):lattice.data.points[i].co_deform.z=points[i][0]

def removenode():
    curve_node_mapping.clear()
    for group in bpy.data.node_groups:
        if group.name=="WeldCurveData":
            bpy.data.node_groups.remove(group)

def getcenterofmass(obj):
    centerpoint=(0,0,0)
    sumx=0
    sumy=0
    sumz=0
    matrix=obj.matrix_world
    for v in obj.data.vertices:
        sumx=sumx+(matrix*v.co)[0]
        sumy=sumy+(matrix*v.co)[1]
        sumz=sumz+(matrix*v.co)[2]
    centerpoint=(sumx/len(obj.data.vertices),sumy/len(obj.data.vertices),sumz/len(obj.data.vertices))    
    return centerpoint

def makemodfirst(modifier):
    modname=modifier.name
    obj=bpy.context.scene.objects.active
    for m in obj.modifiers:
        if obj.modifiers[0]==modifier: break
        else: bpy.ops.object.modifier_move_up(modifier=modname)  
        
def isanythingselected(obj):
    bm=bmesh.from_edit_mesh(obj.data)
    vertices=[v.index for v in bm.verts if v.select]
    faces=[f.index for f in bm.faces if f.select]
    edges=[e.index for e in bm.edges if e.select]
    selection=len(vertices)+len(faces)+len(edges)
    if selection==0: return False
    else: return True

def removebyobj(obj):
    oldselection=bpy.context.selected_objects
    oldactive=bpy.context.scene.objects.active
    bpy.ops.object.select_all(action = 'DESELECT')
    obj.select=True
    bpy.context.scene.objects.active=obj
    bpy.ops.object.delete()
    bpy.context.scene.objects.active=oldactive
    for o in oldselection:
        o.select=True
    
def is_point_inside(point,ob):
    axes = [ mathutils.Vector((1,0,0)) ]
    outside = False
    for axis in axes:
        mat = ob.matrix_world
        mat.invert()
        #mat = mathutils.Matrix(ob.matrix_world).invert()
        orig = mat*point
        mat.invert()
        count = 0
        while True:
            hit,location,normal,index = ob.ray_cast(orig,orig+axis*10000.0)
            if index == -1: break
            count += 1
            orig = location + axis*0.00001
        if count%2 == 0:
            outside = True
            break
    return not outside

def mesh_intersecting(obj1,obj2):
    intersection=False
    for v in obj1.data.vertices:
        if is_point_inside(v.co,obj2):
            intersection=True
            break;
    return intersection

def absoluteselection(obj):
    bm=bmesh.from_edit_mesh(obj.data)
    selected_old_indices=[v.index for v in bm.verts if v.select]
    selected_old_faces=[f.index for f in bm.faces if f.select]
    selected_old_edges=[e.index for e in bm.edges if e.select]
    selected_old=len(selected_old_indices)
    if selected_old==0: return False
    bpy.ops.mesh.select_more()
    selected_new=len([v.index for v in bm.verts if v.select])
    if selected_new==selected_old:
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')        
        bpy.ops.object.mode_set(mode='OBJECT')        
        obj_new=bpy.context.selected_objects[0]
        for o in bpy.context.selected_objects:
            if o!=bpy.context.scene.objects.active:
                obj_new=o
        bpy.ops.object.select_all(action = 'DESELECT')            
        bpy.context.scene.objects.active=obj_new
        obj_new.select=True
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.scene.objects.active.select
        bpy.ops.object.mode_set(mode='OBJECT')
        if len(bpy.context.selected_objects)>1:
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if mesh_intersecting(bpy.context.selected_objects[0],bpy.context.selected_objects[1]):
                return True, None, None
        bpy.context.scene.objects.active.select
        bpy.ops.object.delete()
        obj_new.select
        bpy.context.scene.objects.active=obj_new
        bpy.ops.object.delete()
    for f in bm.faces:
        if f.index in selected_old_faces: f.select=True
        else: f.select=False
    for f in bm.edges:
        if f.index in selected_old_edges: f.select=True
        else: f.select=False
    for v in bm.verts:
        if v.index in selected_old_indices: 
            v.select=True
        else: v.select=False           
    return False    

def iscontinuable(obj):
    continuable=True
    bm = bmesh.new() 
    bm.from_mesh( obj.data )
    counter=0
    for v in bm.verts:
        if len(v.link_edges)>=3 or len(v.link_edges)==0: continuable=False
        if len(v.link_edges)==1: counter=counter+1
    #if counter>2: continuable=False
    return continuable

def altitude(point1, point2, pointn):
    edge1 = point2 - point1
    edge2 = pointn - point1
    if edge2.length == 0:
        altitude = 0
        return altitude
    if edge1.length == 0:
        altitude = edge2.length
        return altitude
    alpha = edge1.angle(edge2)
    altitude = sin(alpha) * edge2.length
    return altitude

def iterate(points, newVerts, error):
    new = []
    for newIndex in range(len(newVerts) - 1):
        bigVert = 0
        alti_store = 0
        for i, point in enumerate(points[newVerts[newIndex] + 1: newVerts[newIndex + 1]]):
            alti = altitude(points[newVerts[newIndex]], points[newVerts[newIndex + 1]], point)
            if alti > alti_store:
                alti_store = alti
                if alti_store >= error:
                    bigVert = i + 1 + newVerts[newIndex]
        if bigVert:
            new.append(bigVert)
    if new == []:
        return False
    return new

def simplify_RDP(splineVerts,error):
    newVerts = [0, len(splineVerts) - 1]
    new = 1
    while new is not False:
        new = iterate(splineVerts, newVerts, error)
        if new:
            newVerts += new
            newVerts.sort()
    return newVerts

def vertsToPoints(newVerts, splineVerts):
    newPoints = []
    for v in newVerts:
        newPoints += (splineVerts[v].to_tuple())
        newPoints.append(1)
    return newPoints

def SimplifyCurve(obj,error):
    bpy.ops.object.select_all(action='DESELECT')
    scene=bpy.context.scene
    splines = obj.data.splines.values()
    curve = bpy.data.curves.new("Simple_" + obj.name, type='CURVE')
    curve.dimensions='3D'
    for spline_i, spline in enumerate(splines):
        splineType = spline.type
        splineVerts = [splineVert.co.to_3d() for splineVert in spline.points.values()]
        newVerts = simplify_RDP(splineVerts,error)
        newPoints = vertsToPoints(newVerts, splineVerts)
        newSpline = curve.splines.new(type=splineType)
        newSpline.points.add(int(len(newPoints) * 0.25 - 1))
        newSpline.points.foreach_set('co', newPoints)
        newSpline.use_endpoint_u = spline.use_endpoint_u   
    newCurve = bpy.data.objects.new("Simple_" + obj.name, curve)
    scene.objects.link(newCurve)
    newCurve.matrix_world = obj.matrix_world    
    scene.objects.active = obj
    obj.select=True
    newCurve.select = True
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.curve.delete(type='VERT')
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.radius_set(radius=1)    
    if bpy.context.scene.cyclic: bpy.ops.curve.cyclic_toggle()
    bpy.ops.object.mode_set(mode = 'OBJECT')    

def addprop(object):   
    object["Weld"]="True"

def addlenprop(object,length):
    object["CurveLen"]=length

def CalculateCurveLength(curve,cyclic):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.scene.objects.active = curve
    curve.select=True
    bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked":False, "mode":'TRANSLATION'}, TRANSFORM_OT_translate={"value":(0, 0, 0), "constraint_axis":(False, False, False), "constraint_orientation":'GLOBAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "texture_space":False, "remove_on_cancel":False, "release_confirm":False, "use_accurate":False})
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.convert(target='CURVE')
    curve=bpy.context.scene.objects.active
    matrix=curve.matrix_world
    edge_length = 0
    counter=0
    for s in curve.data.splines:
        pointcount=len(s.points)
        for point in s.points:
            if counter>0:
                p0=s.points[counter-1].co
                p1=s.points[counter].co
                edge_length += (p0-p1).length
            counter=counter+1
        if cyclic:
            p0=s.points[pointcount-1].co
            p1=s.points[0].co
            edge_length += (p0-p1).length      
         
    edge_length = '{:.6f}'.format(edge_length)    
    bpy.ops.object.delete()    
    return(edge_length)

def MakeWeldFromCurve(OBJ1,edge_length,obje,matrix):
    current_path = os.path.dirname(os.path.realpath(__file__))
    blendfile = os.path.join(current_path, "weld.blend")  #ustawic wlasna sciezke!        
    section   = "\\Object\\"
    if (obje==''):
        object="Weld_1"
        if bpy.context.scene.type=='Decal': object=object+'_decal'    
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
    OBJ_WELD["Dimensions"]=OBJ_WELD.dimensions
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
    if object=="Weld_3": 
        offset=0.1
        array.count=floor(count/2.3)-1
    if object=="Weld_3_decal": 
        offset=0.1
        array.count=floor(count/2.3)-1
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
    addlenprop(OBJ1,edge_length) 
    return(OBJ_WELD)

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
    #vector = region_2d_to_vector_3d(region, region_3d, mouse_coord)
    origin=region_2d_to_origin_3d(region,region_3d,mouse_coord)
    #direction=region_2d_to_location_3d(region, region_3d, mouse_coord, vector)    
    direction=region_2d_to_vector_3d(region, region_3d, mouse_coord)  
    return origin,direction

def get_mouse_3d_on_mesh(self,event,context):
    origin,direction=get_origin_and_direction(self,event,context)
    self.ishit,self.hit,self.normal, *_ =context.scene.ray_cast(origin,direction)
    #print(self.ishit,self.hit)
    return self.ishit,self.hit

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

def WeldNodeTree():
    if 'WeldCurveData' not in bpy.data.node_groups:
        ng = bpy.data.node_groups.new('WeldCurveData', 'ShaderNodeTree')
        #ng.fake_user = True
    return bpy.data.node_groups['WeldCurveData'].nodes

def WeldCurveData(curve_name,self):
    if curve_name not in curve_node_mapping:    
        cn = WeldNodeTree().new('ShaderNodeRGBCurve')     
        curve_node_mapping[curve_name] = cn.name 
   # bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points[0].location
   # bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points.new(1,0.5)   
   # bpy.data.node_groups['WeldCurveData'].nodes[curve_node_mapping["WeldCurve"]].mapping.curves[3].points.new(0,0.5)   
    return WeldNodeTree()[curve_node_mapping[curve_name]]
   
def register():
    pcoll = bpy.utils.previews.new()
    images_path = pcoll.images_location = os.path.join(os.path.dirname(__file__), "welder_images")
    pcoll.images_location = bpy.path.abspath(images_path)
    preview_collections["thumbnail_previews"] = pcoll
    bpy.types.Scene.my_thumbnails = EnumProperty(
    items=generate_previews(),
    )
    bpy.utils.register_class(WeldTransformModal)
    bpy.utils.register_class(ShapeModifyModal)
    bpy.utils.register_class(OBJECT_OT_WeldButton)
    bpy.utils.register_class(OBJECT_OT_ShapeModifyButton)
    bpy.utils.register_class(WelderDrawOperator)
    bpy.utils.register_class(OBJECT_OT_OptimizeButton)

def unregister():
    bpy.utils.unregister_class(WeldTransformModal)
    bpy.utils.unregister_class(ShapeModifyModal)
    bpy.utils.unregister_class(OBJECT_OT_WeldButton)
    bpy.utils.unregister_class(OBJECT_OT_ShapeModifyButton)
    bpy.utils.unregister_class(WelderDrawOperator)
    bpy.utils.unregister_class(OBJECT_OT_OptimizeButton)

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
        row.enabled=not bpy.context.scene.welddrawing
        row=self.layout.row()
        row.operator("weld.weld")
        row.enabled=not bpy.context.scene.welddrawing
        row=self.layout.row()
        row.operator("weld.draw")
        row.enabled=not bpy.context.scene.welddrawing
        row=self.layout.row()
        row.prop(context.scene, "cyclic")
        row=self.layout.row()
        row.prop(context.scene, 'type', expand=True)
    
class WelderSubPanelDynamic(bpy.types.Panel):
    bl_label = "Options"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Welder"
    @classmethod
    def poll(cls, context):
        if (context.active_object != None):
            return bpy.context.scene.objects.active.get('Weld') is not None
        else: return False
    def draw(self, context):  
        row=self.layout.row()
        row.operator("weld.shape", text=bpy.context.scene.shapebuttonname)
        box = self.layout.box() 
        box.enabled= bpy.context.scene.shapemodified 
        box.row()
        if bpy.context.scene.shapemodified: box.template_curve_mapping(WeldCurveData('WeldCurve',self), "mapping")   
        else: removenode()
        row=self.layout.row()
        row.operator("weld.optimize")
    
def register():
    bpy.types.Scene.cyclic=bpy.props.BoolProperty(name="cyclic", description="cyclic", default=True)
    bpy.types.Scene.type=bpy.props.EnumProperty(items=[
     ("Geometry", "Geometry", "Geometry", 0),
    ("Decal", "Decal", "Decal", 1),
    ])
    bpy.utils.register_class(WelderToolsPanel)
    bpy.utils.register_class(WelderSubPanelDynamic)

def unregister():
    bpy.utils.unregister_class(WelderToolsPanel)    
    bpy.utils.unregister_class(WelderSubPanelDynamic)         

if __name__ == "__main__":
    register()