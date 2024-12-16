import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy.types import AddonPreferences
from bpy.app.handlers import persistent

from . import parameters
from . import utils

welder_material_names = []

@persistent
def material_update_handler(scene, depsgraph):
    update_material_names()

def generate_material_enum(self, context):
    enum_items = []      
    for idx, mat_name in enumerate(welder_material_names, 1):  # Start enumerating from 1
        enum_items.append((mat_name, mat_name, "", "MATERIAL", idx))
    return enum_items     

def update_material_names():
    global welder_material_names
    try:
        welder_material_names = [m.name for m in bpy.data.materials]
    except Exception as e:            
        print("Error: "+str(e))   

def update_welder_category(self, context):
    try:
        bpy.utils.unregister_class(PANEL_PT_WelderToolsPanel)
        bpy.utils.unregister_class(PANEL_PT_WelderSubPanelDynamic)
    except:
        pass
    PANEL_PT_WelderToolsPanel.bl_category = context.preferences.addons[__package__].preferences.category
    PANEL_PT_WelderSubPanelDynamic.bl_category = context.preferences.addons[__package__].preferences.category
    bpy.utils.register_class(PANEL_PT_WelderToolsPanel)
    bpy.utils.register_class(PANEL_PT_WelderSubPanelDynamic)

class PANEL_PT_WelderToolsPanel(bpy.types.Panel):
    bl_label = parameters.NAME
    bl_idname = "OBJECT_PT_Welder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = parameters.NAME
 
    active=False 
    weld=None
    info=""
 
    @classmethod
    def poll(self, context):
        if (context.active_object != None):
            self.info=""
            if bpy.context.view_layer.objects.active.get('Weld') is not None:         
                self.weld=bpy.context.view_layer.objects.active           
                self.active= True
            else:
                self.active= False
        else:
            if (bpy.context.mode=='OBJECT'):
                self.info="Select an object"
                return True
            if (bpy.context.mode=='EDIT_MESH'): 
                self.info="Select edges to weld"   
                return True
            if (bpy.context.mode=='EDIT_CURVE'): 
                self.info="Select spline to weld" 
                return True         
        return True        
 
    def draw(self, context):
        if (self.info!=""):
            row=self.layout.row()  
            self.layout.label(text=self.info)
        else:
            if (self.active):
                try:
                    #row=self.layout.row()
                    #row.template_icon_view(self.weld.weld, "thumbnails") #add interactive and updatemethod
                    row=self.layout.row()
                    #row.prop(self.weld.weld,"name")
                    row=self.layout.row()
                    row.prop(utils.getSpline(),"use_cyclic_u",text="cyclic")
                    #row=self.layout.row()
                    #row.prop(self.weld, "welder_weldType",text="Type")
                    collapsebox = self.layout.box()   
                    row = collapsebox.row(align=True)
                    row.label(text="Collapse")
                    row = collapsebox.row()
                    row.prop(context.scene, "collapsesubsurf")
                    row.enabled=not bpy.context.scene.weldCollapseJoin
                    row = collapsebox.row()
                    row.prop(context.scene, "collapseBool")
                    row = collapsebox.row()
                    row.prop(context.scene, "weldCollapseJoin")
                    row = collapsebox.row()
                    row.operator("weld.collapse")
                    #row.prop(self.weld.weld, "blend")
                except:
                    pass    
            else:
                row=self.layout.row()
                row.template_icon_view(context.scene, "my_thumbnails")
                row.enabled=not bpy.context.scene.welddrawing
                row=self.layout.row()
                row.operator("weld.weld")
                row.enabled=not bpy.context.scene.welddrawing
                row=self.layout.row()
                row.operator("weld.draw")
                row.enabled=not bpy.context.scene.welddrawing
                if (bpy.context.scene.materialOverride != None):
                    if (bpy.context.scene.materialOverride==True):
                        rowO=self.layout.row()
                        rowO.prop(context.scene, "overridenMaterial", text="Material")   
                row=self.layout.row()
                row.prop(context.scene, "cyclic")
                row.prop(context.scene, "surfaceblend")
                row=self.layout.row()
                row.prop(context.scene, 'type', expand=True)          
        
class PANEL_PT_WelderSubPanelDynamic(bpy.types.Panel):        
    bl_label = "Shape"
    bl_idname = "OBJECT_PT_Welder_dynamic"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = parameters.NAME
    
    @classmethod
    def poll(self, context):
        if (context.active_object != None):
            if bpy.context.view_layer.objects.active.get('Weld') is not None:                
                return True
            else: return False
        else:
            return False
    
    def draw(self, context):  
        #bpy.context.scene.cyclic=cehckIfCyclic()        
        row=self.layout.row()
        row.operator("weld.shape", text=bpy.context.scene.shapebuttonname)
        box = self.layout.box() 
        box.enabled= bpy.context.scene.shapemodified 
        box.row()
        if bpy.context.scene.shapemodified: box.template_curve_mapping(utils.WeldCurveData('WeldCurve',self), "mapping")   
        else: utils.removenode()
        row=self.layout.row()
        row.operator("weld.optimize")     

class WelderPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    prefs_tabs: EnumProperty(
    items=(('info', "Info", "Welder Info"),
           ('options', "Options", "Welder Options")),
    default='info')
    
    category : StringProperty(description="Choose a name for the category of the panel",default=parameters.NAME, update=update_welder_category)
    performance : EnumProperty(
    items=(('Fast', "Fast", "Fast"),
           ('High quality', "High quality", "High quality")),
    default='Fast')
    solver: EnumProperty(
    items=(('FAST', "FAST", "FAST"),
           ('EXACT', "EXACT", "EXACT")),
    default='FAST')

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout

        row= layout.row(align=True)
        row.prop(self, "prefs_tabs", expand=True)
        if self.prefs_tabs == 'info':
            layout.label(text="1. Welding along intersection")
            layout.label(text="- select 2 objects in object mode,")
            layout.label(text="- choose what type of weld you want to place (Geometry/Decal)")
            layout.label(text="- click 'Weld' button")
            layout.label(text="- adjust scale by moving the mouse (LMB to apply, RMB sets to default scale)")
            layout.label(text="- adjust rotation by moving the mouse (LMB to apply, RMB sets to default rotation)")
            layout.label(text="2. Welding along selected edgeloop")
            layout.label(text="- select desired edgeloop in edit mode, ")
            layout.label(text="- choose what type of weld you want to place (Geometry/Decal)")
            layout.label(text="- click 'Weld' button")
            layout.label(text="- adjust scale by moving the mouse (LMB to apply, RMB sets to default scale)")
            layout.label(text="- adjust rotation by moving the mouse (LMB to apply, RMB sets to default rotation)")
            layout.label(text="3. Draw welds")
            layout.label(text="- click 'Draw' button while in object mode")
            layout.label(text="- draw on the model's surface")
            layout.label(text="- click RMB or Enter in order to finish drawing and place weld")
            layout.label(text="- adjust scale by moving the mouse (LMB to apply, RMB sets to default scale)")
            layout.label(text="- adjust rotation by moving the mouse (LMB to apply, RMB sets to default rotation)")
            layout.label(text="4. Profile editing")
            layout.label(text="- select weld,")
            layout.label(text="- click 'Modify; button")
            layout.label(text="- adjust weld's profile by playing with curve widget")
            layout.label(text="- click 'Apply' button to accept results")
    
        if self.prefs_tabs == 'options' and bpy.context.scene.materialOverride != None:
            box = layout.box()    
            row = box.row(align=True)
            row.label(text="Panel Category:")
            row.prop(self, "category", text="")
            row = box.row(align=True)
            row.label(text="Performance:")
            row.prop(self, "performance", text="")   
            row = box.row(align=True) 
            row.label(text="Intersection solver:")
            row.prop(self, "solver", text="")    
            row = box.row(align=True) 
            row.label(text="Material Override:")
            row.prop(context.scene, "materialOverride", text="")