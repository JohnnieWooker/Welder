import bpy
import mathutils
import bmesh
from mathutils import Vector
import sys, os
from math import (floor,ceil)
from bpy.app.handlers import persistent

from . import utils
from . import parameters

simplify_error=0.001
lattice_error_thresh=0.0001

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_SimplifyCurve.bl_idname)

class OBJECT_OT_SimplifyCurve(bpy.types.Operator):
    bl_idname = "weld.simplify"   
    bl_label = "Simplify Curve"
    def execute(self, context):
        selected=bpy.context.selected_objects
        for s in selected: utils.SimplifyCurve(s,simplify_error,False)
        return {'FINISHED'}

class OBJECT_OT_WelderDrawOperator(bpy.types.Operator):
    bl_idname = "weld.draw"
    bl_label = "Draw"
    bl_options = {'REGISTER', "UNDO"}
    
    def modal(self, context, event):
        try:
            if self.drawended:
                return {'FINISHED'}
            if (context.area==None):
                self.unregister_handlers(context)
                bpy.context.scene.welddrawing=False
                return {'CANCELLED'}    
            context.area.tag_redraw()        
            
            if event.type == 'LEFTMOUSE' and self.phase==0:
                self.lmb=True
                if event.value in {'RELEASE'}: self.lmb=False
                self.draw_event  = None
                self.initiated=True            
                #self.lmb = event.value == 'PRESS'
            
            elif event.type == 'MOUSEMOVE' and self.phase==0:                
                if self.lmb:
                    if utils.get_mouse_3d_on_mesh(self,event,context) is not None:
                        ishit,hit=utils.get_mouse_3d_on_mesh(self,event,context)
                        if (ishit): 
                            self.mouse_path.append(hit)
                            
                
                #print("test")

            elif (event.type == 'RIGHTMOUSE' or event.type == 'RET') and event.value in {'RELEASE'} and self.phase==0:
                cyclic=bpy.context.scene.cyclic
                self.unregister_handlers(context)       
                if not self.initiated:
                    bpy.context.scene.welddrawing=False
                    return {'FINISHED'}
                context = bpy.context
                
                utils.create_curve_from_mouse_path(self.mouse_path,cyclic)         
                  
                #set proper radius
                bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.curve.select_all(action='SELECT')
                bpy.ops.curve.radius_set(radius=1)
                if cyclic: bpy.ops.curve.cyclic_toggle()
                bpy.ops.object.mode_set(mode='OBJECT')            
                curve=bpy.context.view_layer.objects.active
                surfaces=utils.ScanForSurfaces(curve)
                utils.SimplifyCurve(curve,simplify_error,bpy.context.scene.cyclic)
                edge_length=utils.CalculateCurveLength(curve,bpy.context.scene.cyclic)
                matrix=curve.matrix_world  
                useproxy = True if context.preferences.addons[__package__].preferences.performance=='Fast' else False
                obj=utils.MakeWeldFromCurve(curve,edge_length,self.obje,matrix,surfaces,useproxy)  
                self.phase=1  
                return bpy.ops.weld.translate('INVOKE_DEFAULT')
            

            elif event.type in {'ESC'} and self.phase==0:
                self.unregister_handlers(context)
                bpy.context.scene.welddrawing=False
                return {'CANCELLED'}
            
        except Exception as e:    
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type,exc_obj, exc_tb.tb_lineno)
            print(e)
            bpy.context.scene.shapemodified=False
            bpy.context.scene.welddrawing=False
            
        return {'PASS_THROUGH'}

    def invoke(self, context, event):  
        self.drawended=False 
        utils.switchkeymap(False)         
        utils.getOverrideMaterial()
        self.phase=0
        self.obje='' 
        iconname=bpy.context.scene.my_thumbnails
        self.obje=utils.weldchose(iconname)
        if self.obje=='': return {'FINISHED'}
        if bpy.context.scene.type=='Decal': self.obje=self.obje+parameters.DECAL_SUFFIX
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
            #self.bvhtree = utils.bvhtree_from_object(self,context, context.active_object)
            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(utils.draw_callback_px, args, 'WINDOW', 'POST_VIEW')

            self.mouse_path = []

            context.window_manager.modal_handler_add(self)
            self.draw_event = context.window_manager.event_timer_add(0.1, window=context.window)
            return {'RUNNING_MODAL'}
        else:
            utils.switchkeymap(True)
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

    def unregister_handlers(self, context):        
        utils.switchkeymap(True)
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        #context.window_manager.event_timer_remove(self.draw_event)
        self.draw_event  = None
        self.drawended=True 

class OBJECT_OT_WeldTransformModal(bpy.types.Operator):
    bl_idname = "weld.translate"
    bl_label = "Weld modal transform"
    #def execute(self, context):
    def modal(self, context, event):
        try:
            if event.type == 'MOUSEMOVE':
                if (self.phase==1):   
                    self.offset=((self._initial_mouse.x-event.mouse_x)+(self._initial_mouse.y-event.mouse_y))* 0.02             
                    multiplificator=1+self.offset
                    if(multiplificator<0.05):multiplificator=0.05
                    for i in range(len(self.OBJ_WELD)):
                        if len(self.array)==len(self.OBJ_WELD):           
                            self.OBJ_WELD[i].scale[0]=multiplificator
                            self.OBJ_WELD[i].scale[1]=multiplificator
                            self.OBJ_WELD[i].scale[2]=multiplificator
                            #self.array[i]=self.OBJ_WELD[i].modifiers["array"]                
                            #self.array[i].count=int(self.old_count[i]/multiplificator)+1
                if (self.phase==2):
                    self.offset = (self._initial_mouse - Vector((event.mouse_x, event.mouse_y, 0.0))) * 0.02
                    multiplificator=(self.offset).length
                    for i in range(len(self.OBJ_WELD)):
                        self.OBJ_WELD[i].rotation_euler[0]=multiplificator
            elif event.type == 'LEFTMOUSE' and event.value in {'RELEASE'}:    
                if (self.phase==2):
                    bpy.context.scene.welddrawing=False
                    for i in range(len(self.OBJ_WELD)): utils.enablemodifiers(self.OBJ_WELD[i])
                    bpy.ops.ed.undo_push()
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
                    for i in range(len(self.OBJ_WELD)): utils.enablemodifiers(self.OBJ_WELD[i])
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
                    bpy.ops.ed.undo_push()
                    return {'RUNNING_MODAL'} 
        except Exception as e:
            print(e)
            bpy.context.scene.shapemodified=False
            bpy.context.scene.welddrawing=False                    
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):        
        self._initial_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
        self.OBJ_WELD=bpy.context.selected_objects
        for i in range(len(self.OBJ_WELD)): utils.disablemodifiers(self.OBJ_WELD[i])
        self.array=[m.modifiers["array"] for m in self.OBJ_WELD]
        self.old_count=[a.count for a in self.array]
        self.phase=1
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            bpy.context.scene.welddrawing=True
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            bpy.context.scene.welddrawing=False
            return {'CANCELLED'}       
        
class OBJECT_OT_RotateButton(bpy.types.Operator):
    bl_idname = "rotate.rotate"
    bl_label = "Rotate weld"
    country : bpy.props.StringProperty()
 
    def execute(self, context):  
        bpy.ops.curve.switch_direction()
        return {'FINISHED'} 
              
class OBJECT_OT_WeldButton(bpy.types.Operator):
    bl_idname = "weld.weld"    
    #obje : bpy.props.StringProperty()   
    bl_label = "Weld"   
    bl_options = {'REGISTER', "UNDO"}
 
    def execute(self, context):
        preserve=True
        edit=False
        objectstodel=bpy.context.selected_objects
        utils.getOverrideMaterial()
        if (bpy.context.object==None):
            self.report({'ERROR'}, 'Invalid context or nothing selected')
            return {'FINISHED'}       
        if (bpy.context.object.mode=='EDIT'):
            edit=True
            if (bpy.context.view_layer.objects.active.type=='CURVE'):
                bpy.ops.object.mode_set(mode = 'OBJECT')
            else:
                if bpy.context.view_layer.objects.active.type=='MESH':
                    try:                        
                        if utils.absoluteselection(bpy.context.view_layer.objects.active):                         
                            preserve=False
                            objectstodel=bpy.context.selected_objects
                        else: 
                            if (not utils.isanythingselected(bpy.context.view_layer.objects.active)):
                                self.report({'ERROR'}, 'Nothing selected, aborting')
                                return {'FINISHED'}    
                            bpy.ops.mesh.duplicate()
                            bpy.ops.mesh.separate(type='SELECTED')
                            bpy.ops.object.mode_set(mode='OBJECT')
                            originobj=bpy.context.view_layer.objects.active
                            obj=bpy.context.selected_objects[0]
                            for o in bpy.context.selected_objects:
                                if o!=originobj: obj=o
                            bpy.context.view_layer.objects.active = obj
                            originobj.select_set(False)
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.separate(type='LOOSE')
                            bpy.ops.object.mode_set(mode='OBJECT')
                            if (obj.type=='MESH' and (len(obj.data.polygons)>0 or not utils.iscontinuable(obj))):
                                bpy.ops.object.delete()
                                bpy.context.view_layer.objects.active=originobj
                                bpy.ops.object.mode_set(mode='EDIT')
                                self.report({'ERROR'}, 'Detected incorrect selection or not an edgeloop, aborting')
                                return {'FINISHED'}  
                    except:
                        self.report({'ERROR'}, 'Detected incorrect selection or not an edgeloop, aborting')
                        return {'FINISHED'}           
        try:
            if (bpy.context.object.mode!='OBJECT'):
                self.report({'ERROR'}, 'Welding works only in edit or object mode')
                return {'FINISHED'}
        except:
            self.report({'ERROR'}, 'Incorrect selection')
            return {'FINISHED'}        
        curves=0
        for o in bpy.context.selected_objects:
            if (o.type=='CURVE'): curves=curves+1
        """if (curves==0):  
            #bpy.ops.ed.undo()         
            self.report({'ERROR'}, 'Incorrect selection')    
            return {'FINISHED'}       """ 
        if len(bpy.context.selected_objects)==curves: edit=True
        if (len(bpy.context.selected_objects)>0 and edit):
            obj=bpy.context.selected_objects
            bpy.ops.object.select_all(action = 'DESELECT')
            for o in obj:
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                if (o.type=='MESH' and len(o.data.polygons)==0):
                    bpy.ops.object.convert(target='CURVE')
                    bpy.ops.object.select_all(action = 'DESELECT')
            obje='' 
            iconname=bpy.context.scene.my_thumbnails
            obje=utils.weldchose(iconname)
            if obje=='': return {'FINISHED'}   
            if bpy.context.scene.type=='Decal': obje=obje+parameters.DECAL_SUFFIX
            welds=[] 
            obj=utils.SplitCurves(obj)
            for o in obj:   
                if (o.type=='CURVE'):                    
                    bpy.context.view_layer.objects.active = o
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.curve.select_all(action='SELECT')
                    bpy.ops.curve.radius_set(radius=1)
                    bpy.ops.object.mode_set(mode='OBJECT')            

                    edge_length=utils.CalculateCurveLength(o,o.data.splines[0].use_cyclic_u)
                    matrix=o.matrix_world  
                    surfaces=utils.ScanForSurfaces(o)
                    useproxy = True if context.preferences.addons[__package__].preferences.performance=='Fast' else False
                    objweld=utils.MakeWeldFromCurve(o,edge_length,obje,matrix,surfaces,useproxy)
                    welds.append(objweld)
            for o in welds:   
                o.select_set(True)                    
                bpy.context.view_layer.objects.active = o        
            return bpy.ops.weld.translate('INVOKE_DEFAULT')
            return {'FINISHED'}
        
        if (len(bpy.context.selected_objects)!=2):
            self.report({'ERROR'}, 'Select 2 objects or spline')
            return {'FINISHED'}
        else:
            surfaces=bpy.context.selected_objects
            obje='' 
            iconname=bpy.context.scene.my_thumbnails
            obje=utils.weldchose(iconname)
            if obje=='': return {'FINISHED'}
            if bpy.context.scene.type=='Decal': obje=obje+parameters.DECAL_SUFFIX
            def is_inside(p, obj):
                max_dist = 1.84467e+19
                found, point, normal, face = obj.closest_point_on_mesh(p, distance=max_dist)
                p2 = point-p
                v = p2.dot(normal)
                #print(v)
                return not(v < 0.0001)
            bpy.ops.object.duplicate()
            selectedobjects=bpy.context.selected_objects
            for o in selectedobjects: utils.applymods(o)
            objects = bpy.data.objects
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) 
            OBJ1=bpy.context.selected_objects[0]
            matrix=OBJ1.matrix_world
            OBJ2=bpy.context.selected_objects[1]
            bpy.ops.object.duplicate()
            OBJ3=bpy.context.selected_objects[0]
            OBJ4=bpy.context.selected_objects[1]
            bool_two = OBJ1.modifiers.new(type="BOOLEAN", name="bool 2")
            if hasattr(bool_two, "use_self"): bool_two.use_self=True
            bool_two.object = OBJ2
            bool_two.operation = 'INTERSECT'
            if hasattr(bool_two, "solver"): bool_two.solver=context.preferences.addons[__package__].preferences.solver
            bpy.context.view_layer.objects.active = OBJ1
            bpy.ops.object.modifier_apply (modifier='bool 2')
            bpy.ops.object.select_all(action = 'DESELECT')
            OBJ2.select_set(True)
            bpy.ops.object.delete()
            bpy.context.view_layer.objects.active = OBJ1
            OBJ1.select_set(True)
            vertices1 = OBJ1.data.vertices
            #poczatek sprawdzania kolizji z pierwszym obiektem
            list=[]
            for v in vertices1:
                #print (is_inside(mathutils.Vector(v.co), OBJ3))
                #print (v.index)
                if (is_inside(mathutils.Vector(OBJ3.matrix_world @ v.co), OBJ3)==True):
                    list.append(v.index)
                if (is_inside(mathutils.Vector(OBJ4.matrix_world @ v.co), OBJ4)==True):
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
            
            guides=utils.separateloose(OBJ1)
            
            for g in guides: g.select_set(True)
            
            bpy.ops.object.convert(target="CURVE")
            bpy.ops.object.scale_clear()
            bpy.ops.object.select_all()
            
            listofwelds=[]
            edge_lengths=[]
            for g in guides:
                if (g.type!='CURVE'):
                    if (len(guides)<=1): 
                        self.report({'ERROR'}, 'Cant find intersection or proper edges selection')
                        return {'FINISHED'}
                    else:
                        guides.remove(g)
            c=0

            for g in guides:
                edge_length=utils.CalculateCurveLength(g,g.data.splines[0].use_cyclic_u)
                edge_lengths.append(edge_length)

            for g in guides: 
                useproxy = True if context.preferences.addons[__package__].preferences.performance=='Fast' else False
                listofwelds.append(utils.MakeWeldFromCurve(g,edge_lengths[c],obje,matrix,surfaces,useproxy))
                c=c+1
            
            for o in listofwelds: o.select_set(True)
        
            
            utils.remove_obj(OBJ3.name)
            utils.remove_obj(OBJ4.name)
            
            return bpy.ops.weld.translate('INVOKE_DEFAULT')
            #return {'FINISHED'}

class OBJECT_OT_ShapeModifyButton(bpy.types.Operator):
    bl_idname = "weld.shape"   
    bl_label = "Modify"
    def execute(self, context):
        bpy.context.scene.shapebuttonname
        bpy.context.scene.shapemodified=not bpy.context.scene.shapemodified
        if bpy.context.scene.shapemodified:             
            bpy.context.scene.shapebuttonname="Apply"
            utils.WeldNodeTree()
            utils.WeldCurveData('WeldCurve',self)
            bpy.ops.weld.shapemodal()                       
        else:             
            bpy.context.scene.shapebuttonname="Modify"
            utils.removenode()
        return{'FINISHED'}

class OBJECT_OT_OptimizeButton(bpy.types.Operator):
    bl_idname = "weld.optimize"   
    bl_label = "Add plane for baking"
    def execute(self, context):
        OBJ_Source=bpy.context.view_layer.objects.active
        location=OBJ_Source.location
        rotation=OBJ_Source.rotation_euler
        scale=OBJ_Source.scale
        current_path = os.path.dirname(os.path.realpath(__file__))
        blendfile = os.path.join(current_path, parameters.WELD_FILE)  #ustawic wlasna sciezke!        
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
        edge_length=utils.CalculateCurveLength(curve,curve.data.splines[0].use_cyclic_u)
        segment_length=0.015*OBJ_Weld_plain.scale[0]
        count=ceil(float(edge_length)/segment_length)
        array.count=count  
        curvemod=OBJ_Weld_plain.modifiers.new(type="CURVE", name="curve")
        curvemod.object=curve
        return{'FINISHED'}

class OBJECT_OT_ShapeModifyModal(bpy.types.Operator):
    bl_idname = "weld.shapemodal"
    bl_label = "Weld shape modify modal"
    _timer = None
    def modal(self, context, event):
        try:
            if event.type in {'RIGHTMOUSE', 'ESC'} or not bpy.context.scene.shapemodified or bpy.context.view_layer.objects.active!=self.obj:
                self.cancel(context)
                return {'CANCELLED'}
            if event.type == 'TIMER':
                #storing data inside custom property
                counter=0
                list=[]
                for i in range(len(bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points)):
                    list.append(bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i].location[0])
                    list.append(bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i].location[1])
                    counter=counter+2
                self.obj["shape_points"]=list
                #translating curve position into world position
                utils.translatepoints(self,utils.matrixtolist(list),lattice_error_thresh)     
        except:
                self.cancel(context)
                return {'CANCELLED'}                               
        return {'PASS_THROUGH'}
    def cancel(self, context):
        utils.enabledatatransfer(self.obj)
        bpy.context.view_layer.objects.active=self.obj
        utils.destroyLattice(self)
        utils.removenode()
        bpy.context.scene.shapemodified=False
        bpy.context.scene.shapebuttonname="Modify"
        wm = context.window_manager
        wm.event_timer_remove(self._timer)    
    def execute(self, context):       
        obj=bpy.context.view_layer.objects.active 
        matrix=obj.matrix_world
        utils.cleanupWeld(obj)
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
            if utils.debug: print(obj["shape_points"])
            bpy.ops.object.add(type='LATTICE', align='VIEW', enter_editmode=False, location=obj.location,)
            obj_lattice=bpy.context.view_layer.objects.active
            utils.hidemods(obj,False)  
            obj_lattice.rotation_euler=obj.rotation_euler
            obj_lattice.rotation_euler[0]=obj_lattice.rotation_euler[0]+0.785398163
            scalecorrected=obj.scale
            #obj_lattice.dimensions=(dimensions[0]*scalecorrected[0],dimensions[1]*scalecorrected[1],dimensions[2]*scalecorrected[2])
            obj_lattice.scale=(dimensions[0]*scalecorrected[0],dimensions[1]*scalecorrected[1],dimensions[2]*scalecorrected[2])
            obj_lattice.location=utils.getcenterofmass(obj)
            utils.hidemods(obj,True)  
            lattice.object=obj_lattice    
        obj_lattice=lattice.object          
        self.obj=obj
        self.obj_lattice=obj_lattice   
        bpy.context.view_layer.objects.active=obj   
        utils.makemodfirst(lattice)
        #change lattice matrix         
        obj_lattice.data.points_u=1
        obj_lattice.data.points_v=1
        obj_lattice.data.points_w=2   
        #define starting curve        
        '''
        for p in c.points:
            p.location=(p.location[0],0.5)
            '''  
        bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[0].location=(0,0.5)
        bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[-1].location=(1,0.5)
        bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.update()
        if (len(obj["shape_points"])>3):
            bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[0].location=(obj["shape_points"][0],obj["shape_points"][1])
            bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[-1].location=(obj["shape_points"][-2],obj["shape_points"][-1])
            if (len(obj["shape_points"])>5 and len(obj["shape_points"])%2==0):
                counter=2
                for i in range(floor((len(obj["shape_points"])-4)/2)): 
                    comparision_tuple=(bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i+1].location[0],bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points[i+1].location[1])
                    if (comparision_tuple!=(obj["shape_points"][counter],obj["shape_points"][counter+1])):
                        bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.curves[3].points.new(obj["shape_points"][counter],obj["shape_points"][counter+1])
                    counter=counter+2
            bpy.data.node_groups['WeldCurveData'].nodes[utils.curve_node_mapping["WeldCurve"]].mapping.update() 
        #starting curve defined according to custom property of weld object
        utils.disabledatatransfer(self.obj)   
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}    

class OBJECT_OT_OnLoadCleanup(bpy.types.Operator):
    bl_idname = "weld.onloadcleanup"
    bl_label = "Welder on load cleanup"
    def invoke(self, context,event):
        bpy.context.scene.welddrawing=False
        return {'FINISHED'}   
    def execute(self, context):    
        bpy.context.scene.welddrawing=False
        return {'FINISHED'}   

class OBJECT_OT_CollapseButton(bpy.types.Operator):
    bl_idname = "weld.collapse"   
    bl_label = "Collapse"
    def execute(self, context):        
        utils.collapse()
        return{'FINISHED'}

@persistent
def load_handler(dummy):
    for obj in bpy.data.objects: utils.update_driver(obj)    
    bpy.context.view_layer.update()
    bpy.ops.weld.onloadcleanup('INVOKE_DEFAULT')

bpy.app.handlers.load_post.append(load_handler)     