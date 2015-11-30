#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Description: Script adds rulers into the current picture which are used to crop 
#              portraits according to the german / european passport standard which is done in two steps.
#              References:
#              - https://www.bundesdruckerei.de/sites/default/files/fotomustertafel_72dpi.pdf
#              - https://www.bundesdruckerei.de/sites/default/files/passbildschablone_erwachsene.pdf
#
# Author: Philipp Lutz (philipp.lutz@gmx.de)
#

from gimpfu import *
import math



def passport_rulers1(timg, tdrawable):
        width = tdrawable.width
        height = tdrawable.height
        
        height_eyes_top = height * (1 - 0.71)
        height_eyes_bottom = height * (1 - 0.487)

        width_nose_left = width * 0.444
        width_nose_right = width * 0.556

        pdb.gimp_image_undo_group_start(timg)
        pdb.gimp_image_add_hguide(timg, height_eyes_top)
        pdb.gimp_image_add_hguide(timg, height_eyes_bottom)

        pdb.gimp_image_add_vguide(timg, width_nose_left)
        pdb.gimp_image_add_vguide(timg, width_nose_right)
        pdb.gimp_image_undo_group_end(timg)

def passport_rulers2(timg, tdrawable):
        width = tdrawable.width
        height = tdrawable.height
        
        height_face_opt_top = height * (1 - 0.948)
        height_face_opt_bottom = height * (1 - 0.86)
        height_face_bottom = height * (1 - 0.75)
        
        height_chin = height * (1 - 0.137)

        pdb.gimp_image_undo_group_start(timg)
        pdb.gimp_image_add_hguide(timg, height_face_opt_bottom)
        pdb.gimp_image_add_hguide(timg, height_face_opt_top)
        pdb.gimp_image_add_hguide(timg, height_face_bottom)
        pdb.gimp_image_add_hguide(timg, height_chin)
        pdb.gimp_image_undo_group_end(timg)


register(
        "python_fu_passport_rulers1",
        "Passport Rulers - Step 1",
        "Passport Rulers - Step 1",
        "Philipp Lutz",
        "Philipp Lutz",
        "2010-2011",
        "<Image>/Filters/Misc/Passport Rulers - Step 1",
        "RGB*, GRAY*",
        [],
        [],
        passport_rulers1)

register(
        "python_fu_passport_rulers2",
        "Passport Rulers - Step 2",
        "Passport Rulers - Step 2",
        "Philipp Lutz",
        "Philipp Lutz",
        "2010-2011",
        "<Image>/Filters/Misc/Passport Rulers - Step 2",
        "RGB*, GRAY*",
        [],
        [],
        passport_rulers2)

main()
