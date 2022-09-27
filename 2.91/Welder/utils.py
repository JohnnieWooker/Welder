import bpy
import bgl
import gpu
from gpu_extras.batch import batch_for_shader
import mathutils
import bmesh
import os
from mathutils import Vector
from math import (sin,floor)
from bpy_extras.view3d_utils import (
    region_2d_to_vector_3d,
    region_2d_to_origin_3d,
    region_2d_to_location_3d
)

from . import parameters

debug=False
curve_node_mapping = {}

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

def switchkeymap(state):
    x = bpy.context.window_manager.keyconfigs[2].keymaps['3D View'].keymap_items
    y=bpy.context.window_manager.keyconfigs[2].keymaps['3D View Tool: Select Box'].keymap_items
    z=bpy.context.window_manager.keyconfigs[2].keymaps['Object Mode'].keymap_items
    list = [keymap for keymap in x if keymap.type == 'LEFTMOUSE' or keymap.type == 'RIGHTMOUSE' or keymap.type == 'EVT_TWEAK_L' or keymap.type == 'ACTIONMOUSE' or keymap.type == 'SELECTMOUSE']
    listy=[keymap for keymap in y]
    listz = [keymap for keymap in z if keymap.type == 'LEFTMOUSE' or keymap.type == 'RIGHTMOUSE' or keymap.type == 'EVT_TWEAK_L' or keymap.type == 'ACTIONMOUSE' or keymap.type == 'SELECTMOUSE']
    for km in list: km.active = state
    for km in listy: km.active = state
    for km in listz: km.active = state

def draw_callback_px(self, context):
    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": self.mouse_path})
    shader.bind()
    shader.uniform_float("color", (0.0, 0.0, 0.0, 0.5))
    batch.draw(shader)
  
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
    #following is for 2.91
    depsgraph = context.evaluated_depsgraph_get()
    self.ishit,self.hit,self.normal, *_ =context.scene.ray_cast(depsgraph,origin,direction)
    #following works in 2.8
    #self.ishit,self.hit,self.normal, *_ =context.scene.ray_cast(bpy.context.view_layer,origin,direction)
    return self.ishit,self.hit

def bvhtree_from_object(self, context, object):
    bm = bmesh.new()
    mesh = object.data
    bm.from_mesh(mesh)
    bm.transform(object.matrix_world)
    bvhtree = BVHTree.FromBMesh(bm)
    return bvhtree

def surfaceBlendUpdate(self, context):
    if (context.active_object != None):
        weld=bpy.context.view_layer.objects.active
        if (weld.weld.name != None):
            if weld.weld.blend:
                if debug: print("blending on")
            else:
                if debug: print("blending off")                
            return
    return   

def weldchose(iconname):
        if iconname=='icon_1.png': return 'Weld_1'
        if iconname=='icon_2.png': return 'Weld_2'
        if iconname=='icon_3.png': return 'Weld_3'
        if iconname=='icon_4.png': return 'Weld_4'
        if iconname=='icon_5.png': return 'Weld_5'
        if iconname=='icon_6.png': return 'Weld_6'
        if iconname=='icon_7.png': return 'Weld_7'
        return ''  

def add_driver(OBJ_WELD,array,number):
    fcurve=array.driver_add('count')
    driver = fcurve.driver
    var = driver.variables.new()
    var.type = 'TRANSFORMS'
    var.name = "size"
    target = var.targets[0]
    target.transform_type = "SCALE_X"
    target.id = OBJ_WELD.id_data
    target.data_path = "scale[0]"
    driver.expression = str(number)+"/size+1"

def disablemodifiers(obj):
    disabledatatransfer(obj)

def enablemodifiers(obj):
    if (bpy.context.preferences.addons[parameters.NAME].preferences.performance=='Fast'): replaceProxyWeldWithFinal(obj)
    enabledatatransfer(obj)

def disabledatatransfer(obj):
    for m in obj.modifiers:
        if m.type=='DATA_TRANSFER' or m.type=='SHRINKWRAP' or m.type=='VERTEX_WEIGHT_PROXIMITY' or m.type=='SUBSURF':
            m.show_viewport=False    
    
def enabledatatransfer(obj):
    for m in obj.modifiers:
        if m.type=='DATA_TRANSFER' or m.type=='SHRINKWRAP' or m.type=='VERTEX_WEIGHT_PROXIMITY' or m.type=='SUBSURF':
            m.show_viewport=True
            if m.type=='VERTEX_WEIGHT_PROXIMITY':
                m.max_dist=0.002*obj.scale[1]
        if m.type=='CURVE' and obj.scale[1]<1:
            curve=m.object
            if (not curve==None):
                curve.data.resolution_u=int(1/obj.scale[2]*3)

def cleanupWeld(obj):
    if (obj.data.shape_keys!=None):
        if (len(obj.data.shape_keys.key_blocks.keys())>1):
            obj.active_shape_key_index = 1
            bpy.ops.object.shape_key_remove()

def destroyLattice(self):
    bpy.ops.object.mode_set(mode='OBJECT')
    for m in self.obj.modifiers:
        if m.type=="LATTICE" and m.object==self.obj_lattice:
            #bpy.ops.object.modifier_apply(modifier=m.name)
            bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=False, modifier=m.name)
            me = self.obj.data
            #bpy.context.object.active_shape_key_index = 1
            me.shape_keys.key_blocks["Lattice"].value = 1
            
    remove_obj(self.obj_lattice.name)        
    #print(self.obj_lattice)

def applymods(obj):
    oldselected=bpy.context.selected_objects
    oldactive=bpy.context.view_layer.objects.active
    for m in obj.modifiers:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.context.view_layer.objects.active=oldactive
    for o in oldselected: o.select_set(True)

def separateloose(obj):    
    selected=bpy.context.selected_objects
    active=bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action = 'DESELECT')
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    separated=bpy.context.selected_objects
    bpy.ops.object.select_all(action = 'DESELECT')
    for s in selected: s.select_set(True)
    bpy.context.view_layer.objects.active
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

def translatepoints(self,points,error):    
    lattice=self.obj_lattice
    for i in range(len(points)):
        points[i][1]=points[i][1]-0.5
        points[i][1]=points[i][1]*-1
        #points[i][1]=points[i][1]*-(0.72393)   
        points[i][0]=points[i][0]-0.5
    lattice.data.points_w=len(points)        
    for i in range(lattice.data.points_w):
        if (abs(abs(lattice.data.points[i].co_deform.y)-abs(points[i][1]))>error): lattice.data.points[i].co_deform.y=points[i][1]*10/self.obj.scale[1]
        if (abs(abs(lattice.data.points[i].co_deform.z)-abs(points[i][0]))>error):lattice.data.points[i].co_deform.z=points[i][0]*10/self.obj.scale[2]

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
        sumx=sumx+(matrix@v.co)[0]
        sumy=sumy+(matrix@v.co)[1]
        sumz=sumz+(matrix@v.co)[2]
    centerpoint=(sumx/len(obj.data.vertices),sumy/len(obj.data.vertices),sumz/len(obj.data.vertices))    
    return centerpoint

def makemodfirst(modifier):
    modname=modifier.name
    obj=bpy.context.view_layer.objects.active
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

def remove_obj(obj):
    selected=bpy.context.selected_objects
    active=bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects[obj].select_set(True)
    bpy.ops.object.delete()
    for o in selected:
        try:
            o.select_set(True)
        except:
            continue

def is_point_inside(point,ob):
    axes = [ mathutils.Vector((1,0,0)) ]
    outside = False
    for axis in axes:
        mat = ob.matrix_world
        mat.invert()
        #mat = mathutils.Matrix(ob.matrix_world).invert()
        orig = mat @ point
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
            break
    return intersection

def absoluteselection(obj):
    bpy.ops.object.mode_set(mode = 'OBJECT')
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode='EDIT')
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
            if o!=bpy.context.view_layer.objects.active:
                obj_new=o
        bpy.ops.object.select_all(action = 'DESELECT')            
        bpy.context.view_layer.objects.active=obj_new
        obj_new.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active.select_set(True)
        bpy.ops.object.mode_set(mode='OBJECT')
        if len(bpy.context.selected_objects)>1:
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if mesh_intersecting(bpy.context.selected_objects[0],bpy.context.selected_objects[1]):
                return True, None, None
        bpy.context.view_layer.objects.active.select_set(True)
        obj_new.select_set(False)
        bpy.ops.object.delete()
        obj_new.select_set(True)
        bpy.context.view_layer.objects.active=obj_new
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

def SimplifyCurve(obj,error,cyclic):
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
    scene.collection.objects.link(newCurve)
    newCurve.matrix_world = obj.matrix_world   
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    newCurve.select_set(True)
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.curve.delete(type='VERT')
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.radius_set(radius=1)
    if cyclic: bpy.ops.curve.cyclic_toggle()
    bpy.ops.object.mode_set(mode = 'OBJECT')    

def addprop(object, value):    
    object["Weld"]=value

def CalculateCurveLength(curve,cyclic):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = curve
    curve.select_set(True)
    bpy.ops.object.duplicate()
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.convert(target='CURVE')
    curve=bpy.context.view_layer.objects.active
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

def ScanForSurfaces(curve):
    surfaces=[]
    for p in curve.data.splines[0].points:
        #tu rob raycast i sprawdz meshe w poblizu
        direction=(0, 0, 1)
        origin=(p.co.x,p.co.y,p.co.z)
        hit=None
        try:
            for i in range(0,5):
                if i==0: direction=(0, 0, 1)
                if i==1: direction=(0, 0, -1)
                if i==2: direction=(0, 1, 0)
                if i==3: direction=(0, -1, 0)
                if i==4: direction=(1, 0, 0)
                if i==5: direction=(-1, 0, 0)
                depsgraph = bpy.context.evaluated_depsgraph_get()
                hit=bpy.context.scene.ray_cast(depsgraph, origin, direction, distance=0.00001)
                if hit[0]:
                    break
            if not hit[4] in surfaces and not hit[4]==None:
                if debug: 
                    print("Surface is:")
                    print(hit[4])
                surfaces.append(hit[4])    
        except Exception as e:
            print(e)
            pass    
    return surfaces

def AddBlending(obj,surfaces):
    if bpy.context.scene.surfaceblend:
        if not bpy.context.scene.type=='Decal':        
            if debug: print(obj.name)
            vgs=[]
            counter=0
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = 3.14159
            for s in surfaces:
                vg=obj.vertex_groups.new(name=s.name)
                verts = []
                for vert in obj.data.vertices:
                    verts.append(vert.index)
                vg.add(verts,1.0,'ADD')
                vgs.append(vg)
                vwp=obj.modifiers.new(name='VWP_'+s.name,type='VERTEX_WEIGHT_PROXIMITY')
                vwp.vertex_group=vg.name
                vwp.target=s
                vwp.falloff_type='SHARP'            
                vwp.proximity_mode='GEOMETRY'            
                vwp.proximity_geometry={'FACE'}
                vwp.invert_falloff=True
                vwp.min_dist=0
                vwp.max_dist=0.002*obj.scale[1]
            for s in surfaces:
                swm=obj.modifiers.new(name='SW_'+s.name,type='SHRINKWRAP')    
                swm.target=s
                swm.offset=0.000001  
                swm.vertex_group=vgs[counter].name
                counter=counter+1
            counter=0    
            for s in surfaces:
                dtm=obj.modifiers.new(name='DT_'+s.name,type='DATA_TRANSFER')    
                dtm.object=s
                dtm.use_loop_data = True
                dtm.loop_mapping = 'POLYINTERP_NEAREST'
                dtm.vertex_group=vgs[counter].name
                dtm.data_types_loops = {'CUSTOM_NORMAL'}
                counter=counter+1

def replaceProxyWeldWithFinal(obj):
    current_path = os.path.dirname(os.path.realpath(__file__))
    blendfile = os.path.join(current_path, parameters.WELD_FILE)  #refactor!
    section   = "\\Object\\"
    object=obj['Weld']
    if (parameters.PROXY_SUFFIX in object): object=object.replace(parameters.PROXY_SUFFIX,"")
    filepath  = blendfile + section + object
    directory = blendfile + section
    filename  = object
    bpy.ops.wm.append(
        filepath=filepath, 
        filename=filename,
        directory=directory)  
    vg_names=[]
    for v in obj.vertex_groups:
        vg_names.append(v.name)
    OBJ_WELD=bpy.context.selected_objects[0]
    obj.data=OBJ_WELD.data.copy()
    mod_props = []
    bpy.ops.object.select_all(action = 'DESELECT')
    obj.select_set(True)  
    bpy.context.view_layer.objects.active = obj
    for mod in OBJ_WELD.modifiers:
        obj.modifiers.new(name=mod.name,type=mod.type)
        properties = []
        for prop in mod.bl_rna.properties:
            if not prop.is_readonly:
                properties.append(prop.identifier)
        mod_props.append([mod, properties])
    for stuff in mod_props:
        for m in obj.modifiers:
            bpy.ops.object.modifier_move_up(modifier=stuff[0].name)
        for prop in stuff[1]:
            setattr(obj.modifiers[stuff[0].name], prop, getattr(stuff[0], prop))

    remove_obj(OBJ_WELD.name)
    obj.name=object
    for v in vg_names:
        vg=obj.vertex_groups.new(name=v)
        verts = []
        for vert in obj.data.vertices:
            verts.append(vert.index)
        vg.add(verts,1.0,'ADD')    
    return

def MakeWeldFromCurve(OBJ1,edge_length,obje,matrix,surfaces,proxy):
    current_path = os.path.dirname(os.path.realpath(__file__))
    blendfile = os.path.join(current_path, parameters.WELD_FILE)  #ustawic wlasna sciezke!
    section   = "\\Object\\"
    if (obje==''):
        object="Weld_1"
        if bpy.context.scene.type=='Decal': object=object+parameters.DECAL_SUFFIX
    else:
        object=obje
        if proxy and not bpy.context.scene.type=='Decal': object=object+parameters.PROXY_SUFFIX

    filepath  = blendfile + section + object
    directory = blendfile + section
    filename  = object

    bpy.ops.wm.append(
        filepath=filepath, 
        filename=filename,
        directory=directory)
    #print(filepath)    
    OBJ_WELD=bpy.context.selected_objects[0]
    OBJ_WELD.matrix_world=matrix
    #adding properties to weldobject
    OBJ_WELD.weld.name=object
    OBJ_WELD.weld.blend=bpy.context.scene.surfaceblend
    #print(bpy.context.scene.my_thumbnails)
    OBJ_WELD["Dimensions"]=OBJ_WELD.dimensions    
    addprop(OBJ_WELD,object)
    
    array = OBJ_WELD.modifiers.new(type="ARRAY", name="array")
    array.use_merge_vertices=True
    array.use_relative_offset=False
    array.use_constant_offset=True
    array.merge_threshold=0.0001
    offset=OBJ_WELD["beadLength"]
    count=int(float(edge_length)/offset)+1
    add_driver(OBJ_WELD,array,count)
    if object=="Weld_3": 
        offset=0.1
        array.count=floor(count/2.3)-1
    if object=="Weld_3"+parameters.DECAL_SUFFIX: 
        offset=0.1
        array.count=floor(count/2.3)-1
    array.constant_offset_displace[0]=offset
    curve=OBJ_WELD.modifiers.new(type="CURVE", name="curve")
    curve.object=OBJ1
    #OBJ1.data.resolution_u=int(count/2)
    bpy.data.objects[OBJ_WELD.name].select_set(True)
    bpy.context.view_layer.objects.active = OBJ1
    #bpy.ops.object.modifier_apply(modifier='array')
    #bpy.ops.object.modifier_apply(modifier='curve')
    bpy.ops.object.select_all(action = 'DESELECT')
    OBJ_WELD.select_set(True)  
    bpy.context.view_layer.objects.active = OBJ_WELD
    AddBlending(OBJ_WELD,surfaces)
    return(OBJ_WELD)  

def collapse():
    selected=bpy.context.selected_objects
    oldactive=bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    for o in selected:        
        try:
            intersectors=getIntersectors(o)        
            oldcollections=getCollections(intersectors)
            col=addToTemporaryCollection(parameters.INTERSECTION_COLLECTION_NAME,intersectors)
            collapseCurveAndArray(o,bpy.context.scene.collapsesubsurf)
            deselectVerts(o)   
            booleanIntersectors(o,col)
            removeSelectedFaces(o)
            bpy.data.collections.remove(col)
            o['Weld']=None
        except Exception as e:
            if (debug): print(e)
            pass
    bpy.context.view_layer.objects.active=oldactive
    for o in selected: o.select_set(True)    
    return {'FINISHED'}

def removeSelectedFaces(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.delete(type='FACE')
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    return

def booleanIntersectors(obj,col):
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    boolMod = obj.modifiers.new(type="BOOLEAN", name="bool_intersection")
    boolMod.operand_type = 'COLLECTION'
    boolMod.collection=col
    boolMod.use_hole_tolerant=True
    bpy.ops.object.modifier_apply(modifier=boolMod.name)    
    bpy.ops.object.select_all(action='DESELECT')  
    return

def deselectVerts(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    return

def collapseCurveAndArray(obj,subAlso):
    try:
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True)
        mods=[]
        for m in obj.modifiers:
            if m.type=='CURVE' or m.type=='ARRAY':
                mods.append(m.name)
            if subAlso and m.type=='SUBSURF':  
                mods.append(m.name)  
        for m in mods: bpy.ops.object.modifier_apply(modifier=m)            
        bpy.ops.object.select_all(action='DESELECT')
    except:
        pass   
    return

def addToTemporaryCollection(collectionName,objects):
    collection = bpy.data.collections.new(collectionName)     
    bpy.context.scene.collection.children.link(collection) 
    for o in objects:
        collection.objects.link(o)
    return collection

def getCollections(objects):
    collections=[]
    for o in objects:
        collections.append(o.users_collection)
    return collections    

def getIntersectors(obj):
    intersectors=[]
    for m in obj.modifiers:
        if m.type=='DATA_TRANSFER':
            if (m.object not in intersectors): intersectors.append(m.object)
        if m.type=='SHRINKWRAP':
            if (m.target not in intersectors): intersectors.append(m.target)
        if m.type=='VERTEX_WEIGHT_PROXIMITY':
            if (m.target not in intersectors): intersectors.append(m.target)
    if len(intersectors)<=0:
        curve=getCurve(obj)
        if not curve==None: 
            surfaces=ScanForSurfaces(curve)
            for s in surfaces: intersectors.append(s)     
    return intersectors

def getCurve(obj):
    for m in obj.modifiers:
        if m.type=="CURVE":
            return m.object
    return None        

def getSpline():
    curve=getCurve(bpy.context.view_layer.objects.active)
    if not curve==None:
        return curve.data.splines[0]
    return None           