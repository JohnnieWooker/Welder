'''
Copyright (C) 2016-2024 Łukasz Hoffmann
johnniewooker@gmail.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

'''

import bpy
import os 
import bpy.utils.previews

from . import utils
from . import parameters
from . import operators
from . import panel

bl_info = {
    "name": "Welder",
    "author": "Łukasz Hoffmann",
    "version": (1,4,9),
    "location": "View 3D > Object Mode > Tool Shelf",
    "wiki_url": "https://documentation.forgegon.com/Welder",
    "tracker_url": "https://documentation.forgegon.com/Welder",
    "blender": (3, 2, 0),
    "description": "Generate weld along the edge of intersection of two objects",
    "warning": "",
    "category": "Object",
    }

class WelderVariables(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(name="object", type=bpy.types.Object)   

class WelderSettings(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    blend: bpy.props.BoolProperty(name="Surface blend", description="Surface blend", default=False, update=utils.surfaceBlendUpdate)
    thumbnails: bpy.props.EnumProperty(items=[])

def generate_previews(redraw=False):
    enum_items = []
    if redraw:
        enum_items.append(("test", "test", "", 0, 0))
    else:    
        # We are accessing all of the information that we generated in the register function below
        pcoll = preview_collections["thumbnail_previews"]
        image_location = pcoll.images_location
        VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg')
            
        # Generate the thumbnails
        for i, image in enumerate(os.listdir(image_location)):
            if image.endswith(VALID_EXTENSIONS):
                filepath = os.path.join(image_location, image)
                thumb = pcoll.load(filepath, filepath, 'IMAGE')
                enum_items.append((image, image, "", thumb.icon_id, i))
                    
    return enum_items 

bpy.types.Scene.weldsmooth=bpy.props.BoolProperty(name="weldsmooth", description="weldsmooth", default=False)
bpy.types.Scene.welddrawing=bpy.props.BoolProperty(name="welddrawing", description="welddrawing", default=False)
bpy.types.Scene.shapemodified=bpy.props.BoolProperty(name="shapemodified", description="shapemodified", default=False)     
preview_collections = {}
bpy.types.Scene.shapebuttonname=bpy.props.StringProperty(name="Shape button name", default="Modify")
pcoll = bpy.utils.previews.new()
images_path = pcoll.images_location = os.path.join(os.path.dirname(__file__), "welder_images")
pcoll.images_location = bpy.path.abspath(images_path)
preview_collections["thumbnail_previews"] = pcoll
bpy.types.Scene.my_thumbnails = bpy.props.EnumProperty(items=generate_previews()) 
bpy.types.Scene.cyclic=bpy.props.BoolProperty(name="cyclic", description="cyclic",default=True)
bpy.types.Scene.materialOverride=bpy.props.BoolProperty(name="materialOverride", description="materialOverride",default=False,update=panel.update_material_names())
bpy.types.Scene.overridenMaterial=bpy.props.EnumProperty(items=panel.generate_material_enum)
bpy.types.Scene.surfaceblend=bpy.props.BoolProperty(name="Surface blend", description="Surface blend",default=False)
bpy.types.Scene.collapsesubsurf=bpy.props.BoolProperty(name="Collapse subsurf", description="Collapse subsurf",default=False)
bpy.types.Scene.collapseBool=bpy.props.BoolProperty(name="Boolean Intersectors", description="Boolean Intersectors",default=False)
bpy.types.Scene.weldCollapseJoin=bpy.props.BoolProperty(name="Join With Source", description="Join with source mesh", default=False)
bpy.types.Scene.type=bpy.props.EnumProperty(items=[
    ("Geometry", "Geometry", "Geometry", 0),
    ("Decal", "Decal", "Decal", 1),
    ])
bpy.types.Object.welder_weldType=bpy.props.EnumProperty(items=[
    ("Geometry", "Geometry", "Geometry", 0),
    ("Decal", "Decal", "Decal", 1),
    ], update=utils.updateGeoDecalSwitch)
bpy.types.Object.welder_weldEnabled=bpy.props.BoolProperty(name="welder_weldEnabled", description="welder_weldEnabled", default=False)

classes =(
operators.OBJECT_OT_OnLoadCleanup,
operators.OBJECT_OT_SimplifyCurve,
operators.OBJECT_OT_WeldButton,
operators.OBJECT_OT_WeldTransformModal,
operators.OBJECT_OT_WelderDrawOperator,
operators.OBJECT_OT_CollapseButton,
operators.OBJECT_OT_ShapeModifyButton,
operators.OBJECT_OT_ShapeModifyModal,
operators.OBJECT_OT_OptimizeButton,
panel.PANEL_PT_WelderToolsPanel,
panel.PANEL_PT_WelderSubPanelDynamic,
panel.WelderPreferences,
WelderVariables,
WelderSettings
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(e)
            pass  
    context = bpy.context
    prefs = context.preferences.addons[__package__].preferences
    panel.update_material_names()
    panel.update_welder_category(prefs, context)             
    bpy.types.Object.weld = bpy.props.PointerProperty(type=WelderSettings)
    bpy.types.VIEW3D_MT_object.append(operators.menu_func)
    bpy.app.handlers.depsgraph_update_post.append(panel.material_update_handler)

def unregister():
    for cls in classes:
        if utils.debug: print(cls)
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_post.remove(panel.material_update_handler)    
    #bpy.utils.unregister_class(PANEL_PT_WelderToolsPanel)
    