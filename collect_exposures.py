#!/usr/bin/env python
# -*- coding: utf-8 -*-
#########################################################################################
# collect_exposures.py
#
# Author: Philipp Lutz (philipp.lutz@gmx.de)
#
# Description:
# ------------
# A little helper for managing exposure blends and doing batch processing.
# This script has to be started within gimp
#
# Documentation:
# --------------
#
# data structure for settings:
# [
#    {"path":  STRING,
#     "files": STRING_ARRAY[3],
#     "settings": {
#                    "blur":        INT,
#                    "dark_mask":   INT,
#                    "bright_mask": INT,
#                    "blur_radius": INT,
#                    "scale":       STRING,
#                    "dark":        INT,
#                    "trim":        INT,
#                    "align":       INT
#                 }
#    },
#    {
#     ...
#    }
# ]
#
#########################################################################################



#########################################################################################
# external programs
# -----------------
# please adjust the paths to the following programs if necessary
# e.g. if not in PATH variable or for other operating systems
# TODO: check if programs are available
#########################################################################################
CMD__ALIGN_IMAGE_STACK="align_image_stack"
CMD__MOGRIFY="mogrify"
CMD__JHEAD="jhead"
CMD__ENFUSE="enfuse"

PARAM__ENFUSE_DEFAULT= [
    "--compression=100",            # for JPG output don't use compression
    "-m 4096",                      # amount of cache in MB
    "-b 4096",                      # amount of buffer in MB
    "--depth=float",                # image depth for processing
    "--save-masks=%f-softmask.png", # save masks...
]

PARAM__ENFUSE_FOCUS_STACKING= [
    "--exposure-weight=0",          # weight given to well-exposed pixels
    "--saturation-weight=0",        # weight given to highly-saturated pixels
    "--contrast-weight=1",          # weight given to pixels in high-contrast neighborhoods
    "--hard-mask",                  # force hard blend masks and no averaging on finest scale
    "--save-masks=%f-softmask.png", # save masks...
]

PARAM__ENFUSE_EXPOSURE_SERIES= [
    "--save-masks=%f-softmask.png", # save masks...
]

ALLOWED_FILE_FORMATS=["JPG", "JPEG", "TIFF", "PNG"]


#########################################################################################
# Program start
#########################################################################################

from PIL import Image
import ImageStat
import threading 
import Queue
import sys, os, subprocess, math
import wx

# we just assume the script is started in the context
# of a gimp-plugin and check whether it's true!
startedAsGimpPlugin = 1
try:
    import gimp, gimpplugin
    from gimpenums import *
    pdb = gimp.pdb
except ImportError as error:
    # ok, we assume that script has been called outside gimp context
    startedAsGimpPlugin = 0
    for arg in sys.argv[1:]:
        if "gimp" in arg:
            startedAsGimpPlugin = 1
            print "Now that's weird, while gimp started this script the script can't find the gimp libraries..."
    pass

print "startedAsGimpPlugin = %d" % startedAsGimpPlugin

# Blending modes
MODE__LUMINOSITY_MASKS = 1
MODE__ENFUSE = 2
MODE__ALIGN = 3 # just align images and save aligned files

# Button IDs
ID_NEW     = 1
ID_CLEAR   = 2
ID_DELETE  = 3
ID_CONFIG  = 4
ID_PROCESS = 5
ID_ENFUSE  = 6
ID_ALIGN   = 7

# Default settings for blending
DEFAULT_SETTINGS = {"blur":0,
                    "dark_mask":0,
                    "bright_mask":0,
                    "blur_radius":8,
                    "scale":"",
                    "dark":0,
                    "trim":0,
                    "align":0}

# Standard directory which pops up when adding exposure stacks to the list   
CURRENT_DIR="/home/phil"

myEVT_JOB_DONE = wx.NewEventType()
EVT_JOB_DONE   = wx.PyEventBinder(myEVT_JOB_DONE, 1)



class ConfigureDialog(wx.Dialog):
    def __init__(self, parent, title, item):
        super(ConfigureDialog, self).__init__(parent=parent, title=title, size=(450, 280))
        self.parent = parent
        self.item = item
        self.settings = parent.list_items[item]["settings"]

        blur_choices=["Gaussian/None", "Selective/Low", "Selective/Medium", "Selective/High"]
        dark_mask_choices=["Dark", "Normal", "Bright"]
        bright_mask_choices=["Bright (inverted)", "Normal (inverted)", "Dark (inverted)"]

        self.label_7 = wx.StaticText(self, -1, "Blur Type / Edge Protection")
        self.blur = wx.ComboBox(self, -1, choices=blur_choices, value=blur_choices[0],
                                        style=wx.CB_DROPDOWN|wx.CB_READONLY)
        self.label_8 = wx.StaticText(self, -1, "Dark Mask Grayscale")
        self.dark_mask = wx.ComboBox(self, -1, choices=dark_mask_choices, value=dark_mask_choices[0],
                                        style=wx.CB_DROPDOWN|wx.CB_READONLY)
        self.label_9 = wx.StaticText(self, -1, "Bright Mask Grayscale")
        self.bright_mask = wx.ComboBox(self, -1, choices=bright_mask_choices,
                                        value=bright_mask_choices[0], style=wx.CB_DROPDOWN|wx.CB_READONLY)
        self.label_10 = wx.StaticText(self, -1, "Blend Mask Blur Radius")
        self.blur_radius = wx.SpinCtrl(self, -1, "8", min=0, max=100)
        self.label_11 = wx.StaticText(self, -1, "Scale Largest Image Dimension to")
        self.scale = wx.TextCtrl(self, -1, "")
        self.label_12 = wx.StaticText(self, -1, "Dark Takes Precedence")
        self.dark_takes_precedence = wx.CheckBox(self, -1, "", style=wx.ALIGN_RIGHT)
        self.label_13 = wx.StaticText(self, -1, "Auto-Trim Mask Histograms")
        self.auto_trim_mask_hist = wx.CheckBox(self, -1, "", style=wx.ALIGN_RIGHT)
        self.label_14 = wx.StaticText(self, -1, "Align Layers")
        self.align_layers = wx.CheckBox(self, -1, "", style=wx.ALIGN_RIGHT)
        self.defaultsButton = wx.Button(self, -1, "Defaults")
        self.okButton = wx.Button(self, -1, "Ok")

        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.FlexGridSizer(6, 2, 3, 12)
        grid_sizer_1.Add(self.label_7, 0, 0, 0)
        grid_sizer_1.Add(self.blur, 0, 0, 0)
        grid_sizer_1.Add(self.label_8, 0, 0, 0)
        grid_sizer_1.Add(self.dark_mask, 0, 0, 0)
        grid_sizer_1.Add(self.label_9, 0, 0, 0)
        grid_sizer_1.Add(self.bright_mask, 0, 0, 0)
        grid_sizer_1.Add(self.label_10, 0, 0, 0)
        grid_sizer_1.Add(self.blur_radius, 0, 0, 0)
        grid_sizer_1.Add(self.label_11, 0, 0, 0)
        grid_sizer_1.Add(self.scale, 0, 0, 0)
        grid_sizer_1.Add(self.label_12, 0, 0, 0)
        grid_sizer_1.Add(self.dark_takes_precedence, 0, 0, 0)
        grid_sizer_1.Add(self.label_13, 0, 0, 0)
        grid_sizer_1.Add(self.auto_trim_mask_hist, 0, 0, 0)
        grid_sizer_1.Add(self.label_14, 0, 0, 0)
        grid_sizer_1.Add(self.align_layers, 0, 0, 0)
        grid_sizer_1.Add(self.defaultsButton, 0, wx.EXPAND, 0)
        grid_sizer_1.Add(self.okButton, 0, wx.EXPAND, 0)
        sizer_1.Add(grid_sizer_1, 1, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL, 5)
        self.SetSizer(sizer_1)
        self.Layout()
        self.okButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.defaultsButton.Bind(wx.EVT_BUTTON, self.OnDefaults)

        self.loadSettings(self.settings)

    def OnDefaults(self, e):
        self.loadSettings(DEFAULT_SETTINGS)

    def loadSettings(self, settings):
        # load settings...
        self.blur.SetSelection(settings["blur"])
        self.dark_mask.SetSelection(settings["dark_mask"])
        self.bright_mask.SetSelection(settings["bright_mask"])
        self.blur_radius.SetValue(settings["blur_radius"])
        self.scale.SetValue(settings["scale"])
        self.dark_takes_precedence.SetValue(settings["dark"])
        self.auto_trim_mask_hist.SetValue(settings["trim"])
        self.align_layers.SetValue(settings["align"])

    def OnClose(self, e):
        # save settings...
        settings={}
        settings["blur"]=self.blur.GetSelection()
        settings["dark_mask"]=self.dark_mask.GetSelection()
        settings["bright_mask"]=self.bright_mask.GetSelection()
        settings["blur_radius"]=self.blur_radius.GetValue()
        settings["scale"]=self.scale.GetValue()
        settings["dark"]=self.dark_takes_precedence.GetValue()
        settings["trim"]=self.auto_trim_mask_hist.GetValue()
        settings["align"]=self.align_layers.GetValue()
        self.parent.list_items[self.item]["settings"]=settings
        self.Destroy()


class FileDrop(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, x, y, filenames):
        # check if we can read all files and if the filetypes are supported
        total_count = 0
        count = 0
        for name in filenames:
            total_count += 1
            try:
                file = open(name, 'r')
                file.close()
            except IOError, error:
                dlg = wx.MessageDialog(None, 'Error opening file\n' + str(error))
                dlg.ShowModal()
                return
            for filetype in ALLOWED_FILE_FORMATS:
                if name.upper().endswith(filetype.upper()):
                    count += 1
            if count != total_count:
                dlg = wx.MessageDialog(None, 'Filetype not supported')
                dlg.ShowModal()
                return
        self.window.NewItem(filenames)


class BlendDoneEvent(wx.PyCommandEvent):
    """Event to signal that a count value is ready"""
    def __init__(self, etype, eid, value=None):
        """Creates the event object"""
        wx.PyCommandEvent.__init__(self, etype, eid)
        self._value = value

    def GetValue(self):
        """Returns the value from the event.
        @return: the value of this event

        """
        return self._value


class MainWindow(wx.Frame):
    def __init__(self, parent, id, title):
        self.list_items       = []
        self.list_item_count  = 0
        self.currentDirectory = CURRENT_DIR
        self.batch  = ""
        self.active_jobs = [] 
        wx.Frame.__init__(self, parent, id, title, size=(750, 300))

        panel = wx.Panel(self, -1)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.listbox = wx.ListBox(panel, -1)
        hbox.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 20)

        btnPanel = wx.Panel(panel, -1)
        vbox     = wx.BoxSizer(wx.VERTICAL)
        self.new     = wx.Button(btnPanel, ID_NEW,	'New',       size=(90, 30))
        self.dlt     = wx.Button(btnPanel, ID_DELETE,	'Delete',    size=(90, 30))
        self.clr     = wx.Button(btnPanel, ID_CLEAR,	'Clear',     size=(90, 30))
        self.config  = wx.Button(btnPanel, ID_CONFIG,	'Configure', size=(90, 30))
        self.align   = wx.Button(btnPanel, ID_ALIGN,	'Align',     size=(90, 30))
        self.process = wx.Button(btnPanel, ID_PROCESS,	'Process',   size=(90, 30))
        self.enfuse  = wx.Button(btnPanel, ID_ENFUSE,	'Enfuse',    size=(90, 30))
        
        self.Bind(wx.EVT_BUTTON, self.AddFiles, id=ID_NEW)
        self.Bind(wx.EVT_BUTTON, self.OnConfigure, id=ID_CONFIG)
        self.Bind(wx.EVT_BUTTON, self.OnDelete, id=ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.OnClear, id=ID_CLEAR)
        self.Bind(wx.EVT_BUTTON, self.OnProcess, id=ID_PROCESS)
        self.Bind(wx.EVT_BUTTON, self.OnEnfuse, id=ID_ENFUSE)
        self.Bind(wx.EVT_BUTTON, self.OnAlign,  id=ID_ALIGN)
        
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnConfigure)
        self.Bind(wx.EVT_LISTBOX, self.OnSelect)
        self.Bind(EVT_JOB_DONE, self.OnJobDone)
        
        vbox.Add((-1, 20))
        vbox.Add(self.new)
        vbox.Add(self.dlt, 0, wx.TOP, 5)
        vbox.Add(self.clr, 0, wx.TOP, 5)
        vbox.Add((0, 20))
        vbox.Add(self.config,  0, wx.TOP, 5)
        vbox.Add(self.align,   0, wx.TOP, 5)
        vbox.Add(self.process, 0, wx.TOP, 5)
        vbox.Add(self.enfuse,  0, wx.TOP, 5)
        
        btnPanel.SetSizer(vbox)
        hbox.Add(btnPanel, 0.6, wx.EXPAND | wx.RIGHT, 20)
        panel.SetSizer(hbox)

        self.dlt.Disable()
        self.config.Disable()
        self.clr.Disable()
        self.align.Disable()
        self.process.Disable()
        self.enfuse.Disable()
        
        dt = FileDrop(self)
        self.listbox.SetDropTarget(dt)
        self.Centre()
        self.Show(True)

    def OnSelect(self, event):
        sel = event.GetSelection()
        if sel < 0:
            self.config.Disable()
            self.align.Disable()
            self.dlt.Disable()
            self.process.Disable()
        else:
            self.config.Enable()
            self.dlt.Enable()
            if self.active_jobs[sel] == 0:
                self.align.Enable()
                self.process.Enable()
                self.enfuse.Enable()
            else:
                self.align.Disable()
                self.process.Disable()
                self.enfuse.Disable()
            
    def AddFiles(self, event):
        my_wildcard="JPG Files (*.jpg; *.JPG)|*.jpg;*.JPG| TIF Files (*.tif; *.TIF)|*.tif;*.TIF\
                     | PNG files (*.png; *.PNG)|*.png;*.PNG| All files (*.*)|*.*"
        dlg = wx.FileDialog(self, message="Choose a file",
                            defaultDir=self.currentDirectory,
                            wildcard=my_wildcard,style=wx.OPEN | wx.MULTIPLE)
        if dlg.ShowModal() == wx.ID_OK:
            paths = dlg.GetPaths()     
            self.NewItem(paths)
        dlg.Destroy()

    def NewItem(self, paths):
        files = []
        count = 0
        root = ""
        for path in paths:
            count += 1
            print path
            [root, single_file] = path.rsplit('/',1)
            files.append(single_file)
        if count < 2:
            wx.MessageBox("Please select at least 2 pictures!", "Info", wx.OK | wx.ICON_ERROR)
        else:
            text = '  |  '.join(files)
            if text != '':
                self.active_jobs.append(0)
                self.listbox.Append(text)
                self.clr.Enable()
                self.list_items.append({"path": root+"/", "files": files, "settings": DEFAULT_SETTINGS})
                self.list_item_count += 1
                print self.list_items
                print self.list_item_count

    def OnConfigure(self, event):
        sel = self.listbox.GetSelection()
        text = self.listbox.GetString(sel)
        configDlg = ConfigureDialog(self, 'Settings', sel)
        configDlg.ShowModal()
        configDlg.Destroy()
        
    def OnDelete(self, event):
        sel = self.listbox.GetSelection()
        text = self.listbox.GetString(sel)
        if sel != -1:
            self.listbox.Delete(sel)
            self.list_items.pop(sel)
            self.active_jobs.remove(sel)
            self.list_item_count -= 1
        if self.list_item_count == 0:
            self.clr.Disable()
    
    def OnClear(self, event):
        self.listbox.Clear()
        self.clr.Disable()
        self.align.Disable()
        self.process.Disable()
        self.enfuse.Disable()
        del self.list_items[:]
        self.list_item_count = 0
        self.active_jobs = []
         
    def OnAlign(self, event):
        sel = self.listbox.GetSelection()
        self.align.Disable()
        self.process.Disable()
        self.enfuse.Disable()
        self.active_jobs[sel] = 1;
        self.batch = blend(self, sel, MODE__ALIGN,
                            self.list_items[sel]["path"],  
                            self.list_items[sel]["files"], 
                            self.list_items[sel]["settings"]["align"])
        self.batch.start()    
    
    def OnProcess(self, event):
        sel = self.listbox.GetSelection()
        self.align.Disable()
        self.process.Disable()
        self.enfuse.Disable()
        self.active_jobs[sel] = 1;
        self.batch = blend(self, sel, MODE__LUMINOSITY_MASKS,
                           self.list_items[sel]["path"],
                           self.list_items[sel]["files"],
                           self.list_items[sel]["settings"]["align"])
        self.batch.start()
        print "Start blending (main GUI thread)"

    def OnEnfuse(self, event):
        #
        ## TODO: check if enfuse is available at all before invoking it
        #
        sel = self.listbox.GetSelection()
        self.active_jobs[sel] = 1;
        self.align.Disable()
        self.process.Disable()
        self.enfuse.Disable()
        self.batch = blend(self, sel, MODE__ENFUSE,
                           self.list_items[sel]["path"],  
                           self.list_items[sel]["files"],
                           self.list_items[sel]["settings"]["align"])
        self.batch.start()

    def OnJobDone(self, event):
        sel = event.GetValue()
        print "Processing of list entry %s done" % (sel)
        self.active_jobs[sel] = 0
        self.align.Enable()
        self.process.Enable()
        self.enfuse.Enable()
        self.batch.join()


class blend(threading.Thread):
    def __init__(self, parent, task, mode, root, files, align=0):
        self.id = task
        self.mode = mode
        self.parent = parent
        self.path = root
        self.files = files                  # sorted to: dark_exp, normal_exp, bright_exp
        self._align = align
        self.prefix="aligned"
        self.blur_radius = 8
        self.blur_typ = 0                   # 0 - Gaussian / None
                                            # 1 - Selective / Low
                                            # 2 - Selective / Medium
                                            # 3 - Selective / High
        self.dark_mask_grayscale = 0        # 0 - dark
                                            # 1 - normal
                                            # 2 - bright
        self.bright_mask_grayscale = 0      # 0 - bright (inverted)
                                            # 1 - normal (inverted)
                                            # 2 - dark (inverted)
        self.dark_takes_precedence = 0      # 0 - disabled
                                            # 1 - enabled
        self.auto_trim_mask_histograms = 0  # 0 - disabled
                                            # 1 - enabled
        self.scale_largest_dim_to = ""
        threading.Thread.__init__(self)

    def run(self):
        print "Los gehts!"
        os.chdir(self.path)
        self.start_blend()
        evt = BlendDoneEvent(myEVT_JOB_DONE, -1, self.id)
        wx.PostEvent(self.parent, evt)               

    def align(self):
        """
        Align bracketed files with the help of the tool 'align_image_stack', which
        is part of the hugin stitching suite. Only recommended when bracketed images
        have been created handheld
        """
        count=0
        files=[]
        command=[CMD__ALIGN_IMAGE_STACK, "-a", self.prefix]
        command.extend(self.files)
        output = subprocess.Popen(command).communicate()[0]
        for file in self.files:
            tmp_filename=self.prefix+str(count).zfill(4)+".tif"
            new_filename=file.rsplit(".",1)[0]+"_"+self.prefix
            files.append(new_filename+".jpg")
            os.rename(tmp_filename,new_filename+".tif")
            command=[CMD__MOGRIFY,"-format","jpg","-quality","100",new_filename+".tif"]
            output = subprocess.Popen(command).communicate()[0]
            command=[CMD__JHEAD,"-te",file,new_filename+".jpg"]
            output = subprocess.Popen(command).communicate()[0]
            os.remove(new_filename+".tif")
            count+=1
        self.files = files # update filenames


    def sort_exposures(self):
        """
        Sort files in this order (dark to bright): dark_exp, normal_exp, bright_exp
        according to the histogram mean value of the blue channel with index 2 (R, G, B)
        Return the sorted files, does not change self.files!
        """
        files = []
        means = []
        hist_mean = {}             
        os.chdir(self.path)
        print "--- Sorting bracketing exposures..."
        for file in self.files:
            im   = Image.open(self.path+file)
            stat = ImageStat.Stat(im)
            hist_mean[file] = int(stat.mean[2])
            means.append(int(stat.mean[2]))
        means.sort()        
        for m in means:
            for hist_f, hist_m in hist_mean.iteritems():
                if(hist_m == m):
                    print "Mean histogram value: %d (image: %s)" % (m, hist_f)
                    files.append(hist_f)
        return files


    def start_blend(self):
        i = 0
        if (self._align == 1) or (self.mode == MODE__ALIGN):
            print "--- Aligning bracketing exposures..."
            self.align()
            print "--- Alignment finised"        
        if (self.mode == MODE__LUMINOSITY_MASKS):
            files = self.sort_exposures()
            print "files:"
            print files
            print "self.files:"
            print self.files
            print "normal exp: %s" % self.path+files[1]
            print "dark  exp: %s"  % self.path+files[0]
            print "bright exp: %s" % self.path+files[2]
            pdb.script_fu_exposure_blend(self.path+files[1], # normal_exp
                                         self.path+files[0], # dark_exp
                                         self.path+files[2], # bright_exp,
                                         self.blur_radius,
                                         self.blur_typ,
                                         self.dark_mask_grayscale,
                                         self.bright_mask_grayscale,
                                         self.dark_takes_precedence,
                                         self.auto_trim_mask_histograms,
                                         self.scale_largest_dim_to
                                         )
        elif (self.mode == MODE__ENFUSE):
            files = self.files
            enfuse_filename = files[0].rsplit(".",1)[0]+"_enfuse"+str(i)+".jpg"
            while os.path.exists(enfuse_filename):
                i += 1
                enfuse_filename = files[0].replace(".jpg", "")+"_enfuse"+str(i)+".jpg"
            # add the following constants as arguments:
            # - PARAM__ENFUSE_EXPOSURE_SERIES
            # - PARAM__ENFUSE_DEFAULT
            command = [CMD__ENFUSE] + PARAM__ENFUSE_DEFAULT + ["-o", enfuse_filename]
            command.extend(files)
            print "command: '%s'" % " ".join(command)
            output = subprocess.Popen(command).communicate()[0]

        #filename = self.path + normal_exp.split(".")[0] + ".xcf"
        #cur_drawable = pdb.gimp_image_get_active_drawable(img)
        #pdb.gimp_xcf_save(img, cur_drawable, filename, normal_exp.split(".")[0])


if startedAsGimpPlugin:
    print "Started as gimp plug-in!"
    class ExposureBlendingBatch(gimpplugin.plugin):
        def start(self):
            gimp.main(self.init, self.quit, self.query, self._run)

        def init(self):
            pass

        def quit(self):
            pass

        def query(self):
            authorname = "Philipp Lutz"
            copyright = "Philipp Lutz"
            menu_location = "<Image>/Filters/Misc/Batch Blend Test"
            date = "November 2011"
            description = "Test"
            help = "Test"
            params = [(PDB_INT32, "run_mode", "Run mode")]
            gimp.install_procedure("py_exposure_blending_batch",
                                description,
                                help,
                                authorname,
                                copyright,
                                date,
                                menu_location,
                                "",
                                PLUGIN,
                                params,
                                [])

        def py_exposure_blending_batch(self, runmode):
            app = wx.App()
            MainWindow(None, -1, 'Exposure Blending Batch')
            app.MainLoop()


if __name__ == '__main__':
    if startedAsGimpPlugin:
        print "Started script as gimp plug-in!"
        ExposureBlendingBatch().start()
    else:
        app = wx.App()
        MainWindow(None, -1, 'Exposure Blending Batch')
        app.MainLoop()
