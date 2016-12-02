#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Script to open watermark file and insert it into a picture with both
# a bright and a dark 
#
# Author: Philipp Lutz (philipp.lutz@gmx.de)
#
#########################################################
### Important constants which have to be changed! #######
#########################################################
use_fxfoundry_interface    = 0
scale_factor               = 0.15 # relative to the smaller edge in the picture
watermark                  = "/home/phil/signature3.png" #"/home/phil/path3700.png"
watermark_opacity          = 30.0
watermark_shadow_opacity   = 35.0
#########################################################

from gimpfu import *
import math

class image(object):
        def __init__(self, runmode, img, drawable):
                self.img = img
                self.drawable = drawable
                self.width = drawable.width
                self.height = drawable.height
        def get_size(self):
                return (get_width(self), get_height(self))
        def get_width(self):
                return width
        def get_height(self):
                return height

def insert_watermark(timg, tdrawable):
    width = tdrawable.width
    height = tdrawable.height

    pdb.gimp_image_undo_group_start(timg)

    layer_watermark = pdb.gimp_file_load_layer(timg, watermark)
    layer_watermark.name = "watermark"
    layer_watermark.mode = GRAIN_EXTRACT_MODE
    layer_watermark.opacity = watermark_opacity
    pdb.gimp_image_add_layer(timg, layer_watermark, 0)
    image_aspect = float(width) / float(height)
    watermark_aspect = float(layer_watermark.width) / float(layer_watermark.height)
    if(width < height):
        new_height = height * scale_factor
        scale      = new_height / layer_watermark.height 
        new_width  = layer_watermark.width * scale
    else:
        new_width  = width * scale_factor
        scale      = new_width / layer_watermark.width
        new_height = layer_watermark.height * scale
    print "image width: %u / height: %u / aspect: %f" % (width, height, image_aspect)
    print "watermark: width: %u  / height: %u  / aspect: %f" % (new_width, new_height, watermark_aspect)
    pdb.gimp_layer_scale_full(layer_watermark, new_width, new_height, 1, INTERPOLATION_LANCZOS)
    timg.active_layer = layer_watermark
    if use_fxfoundry_interface == 1:
        pdb.gimp_layer_resize_to_image_size(layer_watermark)
        pdb.script_fu_layer_effects_drop_shadow(timg,layer_watermark,gimpcolor.RGB(0, 0, 0, 255),
                                                30.0, 6.0, 0.0, 5.0, watermark_shadow_opacity, NORMAL_MODE)
    else:                                   
        pdb.python_layerfx_drop_shadow(timg,layer_watermark,gimpcolor.RGB(0, 0, 0, 255),
                                       watermark_shadow_opacity,0,0.0,NORMAL_MODE,0.0,5,120.0,5.0,1,0)
                                    
    layer_watermark_dropshadow = timg.layers[1]
    pdb.gimp_item_set_linked(layer_watermark, 1)
    pdb.gimp_item_set_linked(layer_watermark_dropshadow, 1)
    pdb.gimp_image_undo_group_end(timg)


register(
        "python_fu_insert_watermark",
        "Insert Watermark",
        "Insert Watermark",
        "Philipp Lutz",
        "Philipp Lutz",
        "2010-2011",
        "<Image>/Filters/Misc/Insert Watermark",
        "RGB*, GRAY*",
        [],
        [],
        insert_watermark)

main()
