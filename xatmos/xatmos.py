#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
import pandas
import os
import gzip
import glob
import re
from pyface.qt import QtGui, QtCore
from traits.etsconfig.api import ETSConfig
ETSConfig.toolkit = 'qt4'

import matplotlib as mpl
mpl.rcParams['backend.qt4']='PySide'

mpl.use('Qt4Agg')
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.widgets import  RectangleSelector, AxesWidget
from matplotlib.ticker import FormatStrFormatter

from traitsui.qt4.editor import Editor
from traitsui.qt4.basic_editor_factory import BasicEditorFactory
from traits.api import CFloat, HasTraits, Property, Instance, on_trait_change, List, Button, Float, Str
from traitsui.api import View, Item, TextEditor, HGroup, VGroup, CustomEditor, Handler, CheckListEditor, Heading

from pkg_resources import resource_filename

#TODO: would like two-finger swipe side-to-side to move plot in wavenumber
#TODO: (maybe) would like pinch to zoom/unzoom in wavenumber?
#TODO:  vertical resizing, extra space should go into plot, not UI area
#TODO: central wavelength should have some up/down arrow buttons

import itertools


class _MPLFigureEditor(Editor):

   scrollable  = True

   def init(self, parent):
       self.control = self._create_canvas(parent)
       self.set_tooltip()

   def update_editor(self):
       pass

   def _create_canvas(self, parent):
       """ Create the MPL canvas. """
       frame = QtGui.QWidget()
       mpl_canvas = FigureCanvas(self.value)
       mpl_canvas.setParent(frame)

       vbox = QtGui.QVBoxLayout()
       vbox.addWidget(mpl_canvas)
       frame.setLayout(vbox)

       return frame

class MPLFigureEditor(BasicEditorFactory):

   klass = _MPLFigureEditor

class MPLInitHandler(Handler):
    """Handler calls mpl_setup() to initialize mpl events"""

    def init(self, info):
        """This method gets called after the controls have all been
        created but before they are displayed.
        """
        info.object.mpl_setup()
        return True

size = (800, 600)
title = "xatmos viewer"

colors = itertools.cycle(['b', 'g', 'r', 'c', 'm', 'orange'])
hitran_path = os.path.split(resource_filename(__name__, 'atmos.txt.gz'))[0]
hitran_files = glob.glob(hitran_path + '/hitran_abridged*txt*')
molecules = {}
for curfile in hitran_files:
    curname = re.match('^.*hitran_abridged_(.*)\.txt.*$', curfile).groups()[0]
    molecules[curname] = {'hitran_filename':resource_filename(__name__, os.path.split(curfile)[-1]),
                          'hitran':None, 'plot_lines':None, 'plot_text':None, 'color':colors.next()}

class AtmosViewer(HasTraits):
    central_wavenumber = CFloat(1000)
    bandwidth = CFloat(10)

    selected_line_wavenumber = Float(-1.)

    figure = Instance(Figure, ())

    all_on = Button()
    all_off = Button()
    selected_molecules = List(editor=CheckListEditor(values=molecules.keys(),
                                                            cols=2, format_str = '%s'))

    mplFigureEditor = MPLFigureEditor()

    trait_view = View(VGroup(Item('figure', editor=mplFigureEditor, show_label=False),
                             HGroup('10',
                                    VGroup('40',
                                           Item(name='central_wavenumber',
                                                editor=TextEditor(auto_set=False, enter_set=True)),
                                           Item(name='bandwidth',
                                                editor=TextEditor(auto_set=False, enter_set=True)),
                                           HGroup(Item(name='selected_line_wavenumber'),
                                                  show_border=True),
                                           show_border=True),
                                    HGroup(
                                        VGroup('20', Heading("Molecules"),
                                               Item(name='all_on', show_label=False),
                                               Item(name='all_off', show_label=False)),
                                        Item(name='selected_molecules', style='custom', show_label=False),
                                        show_border=True), '10'),
                             '10'),
                      handler=MPLInitHandler,
                      resizable=True, title=title, width=size[0], height=size[1])


    def __init__(self):
        super(AtmosViewer, self).__init__()
        self.colors = {'telluric':'black',
                       'orders':'black'}
        self.molecules = molecules
        self.selected_molecules = []
        orders_filename = resource_filename(__name__, 'orders.txt')
        self.texes_orders = pandas.io.parsers.read_csv(orders_filename, sep='\t', header=None, skiprows=3)
        atmos_filename = resource_filename(__name__, 'atmos.txt.gz')
        self.atmos = pandas.io.parsers.read_csv(gzip.open(atmos_filename, 'r'), sep='\t', skiprows=7, index_col='# wn')
        self.molecule_lookup_points = {}  #  keys are e.g. 'O3', with a dict of {'wn':..., 'y':...}
        self.axes = self.figure.add_subplot(111)
        self.axes.plot(self.atmos.index, self.atmos['trans1mm'], color=self.colors['telluric'])
        self.axes.plot(self.atmos.index, self.atmos['trans4mm'], color=self.colors['telluric'])
        for i in self.texes_orders.index:
            self.axes.plot(self.texes_orders.ix[i].values, [0.05, 0.07], color=self.colors['orders'])
        self.axes.set_xlim(self.central_wavenumber - self.bandwidth / 2.,
                           self.central_wavenumber + self.bandwidth / 2.)
        self.axes.set_ylim(0, 1.0)
        self.axes.set_xlabel('Wavenumber (cm-1)')
        self.axes.xaxis.set_major_formatter(FormatStrFormatter('%6.1f'))
        self.onclick_connected = False  # I don't understand why I can't do the connection here.
        self.selected_line = None
        self.selected_line_text = None

    def on_click(self, event):
        if event.xdata is None or event.ydata is None:
            return
        if self.selected_line in self.axes.lines:
            self.axes.lines.pop(self.axes.lines.index(self.selected_line))
        if self.selected_line_text in self.axes.texts:
            self.axes.texts.remove(self.selected_line_text)
        self.selected_line = None
        self.selected_line_text = None
        self.selected_line_wavenumber = -1
        if len(self.molecule_lookup_points) == 0:
            return
        closest = {'name':None, 'wn':-1., 'dist':9e9}
        for cur_molecule in self.molecule_lookup_points:
            wn = self.molecule_lookup_points[cur_molecule]['wn']
            ys = self.molecule_lookup_points[cur_molecule]['y']
            dist_x2 = (wn - event.xdata)**2
            xlim = self.axes.get_xlim()
            scale = ((xlim[1] - xlim[0]) /  # this is like wavenumbers/inch
                     (self.axes.figure.get_figwidth() * self.axes.get_position().bounds[2]))
            dist_y2 = ((ys - event.ydata)*(self.axes.figure.get_figheight() *
                                                  self.axes.get_position().bounds[3]) * scale)**2
            dist = np.sqrt(dist_x2 + dist_y2)
            if dist.min() < closest['dist']:
                closest = {'name':cur_molecule, 'wn':wn[dist.argmin()], 'dist':dist.min()}
        self.selected_line_wavenumber = closest['wn']
        self.selected_line = self.axes.plot([closest['wn'], closest['wn']], [0, 1], '-.', color='black')[0]
        self.selected_line_text = self.axes.annotate(closest['name'] + ('%11.5f' % closest['wn']),
                                                     (closest['wn'], 1.03), ha='center',
                                                     annotation_clip=False)
        self.redraw()

    def on_scroll(self, event):
        self.central_wavenumber += self.bandwidth * event.step

    def _all_on_fired(self):
        self.selected_molecules = self.molecules.keys()

    def _all_off_fired(self):
        self.selected_molecules = []

    def mpl_setup(self):
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('button_press_event', self.on_click)
        self.axes_widget.connect_event('scroll_event', self.on_scroll)

    @on_trait_change("central_wavenumber, bandwidth")
    def replot_molecular_overplots(self):
        for i, cur_molecule in enumerate(self.selected_molecules):
            if self.molecules[cur_molecule]['hitran'] is None:
                self.molecules[cur_molecule]['hitran'] = pandas.io.parsers.read_csv( gzip.open(
                                        self.molecules[cur_molecule]['hitran_filename'], 'r'), skiprows=2)
            wn = self.molecules[cur_molecule]['hitran']['wavenumber']
            intensity = self.molecules[cur_molecule]['hitran']['intensity']
            w = ( (wn >= self.central_wavenumber - self.bandwidth / 2.) &
                  (wn <= self.central_wavenumber + self.bandwidth / 2.) )
            wn = wn[w]
            intensity = intensity[w]
            plot_orders_of_magnitude = 2.
            max_line_intensity = intensity.max()
            min_line_intensity = max_line_intensity / 10**plot_orders_of_magnitude
            wn = wn[intensity >= min_line_intensity]
            intensity = intensity[intensity >= min_line_intensity]
            intensity = ((np.log10(intensity) - np.log10(min_line_intensity)) /
                         (np.log10(max_line_intensity) - np.log10(min_line_intensity)))
            intensity = intensity * 0.1
            self.molecule_lookup_points[cur_molecule] = {'wn':wn, 'y':intensity + (i * 0.1) + 0.05}
            wn = wn.repeat(3)
            intensity = np.column_stack((np.zeros(len(intensity)),
                                         intensity,
                                         np.zeros(len(intensity)))).flatten() + (i * 0.1) + 0.05
            newplot = self.axes.plot(wn, intensity, self.molecules[cur_molecule]['color'])
            newtext = self.axes.annotate(cur_molecule, (self.central_wavenumber + self.bandwidth * 0.51,
                                                        i * 0.1 + 0.065), ha='left',
                                         va='center', annotation_clip=False, color=self.molecules[cur_molecule]['color'])
            if self.molecules[cur_molecule]['plot_lines'] in self.axes.lines:
                self.axes.lines.pop(self.axes.lines.index(self.molecules[cur_molecule]['plot_lines']))
            self.molecules[cur_molecule]['plot_lines'] = None
            if self.molecules[cur_molecule]['plot_text'] in self.axes.texts:
                self.axes.texts.remove(self.molecules[cur_molecule]['plot_text'])
                self.molecules[cur_molecule]['plot_text'] = None
            self.molecules[cur_molecule]['plot_lines'] = newplot[0]
            self.molecules[cur_molecule]['plot_text'] = newtext
        self.redraw()

    def _selected_molecules_changed(self, old, new):
        self.replot_molecular_overplots()
        for cur_molecule in old:
            if cur_molecule not in new:
                if self.molecules[cur_molecule]['plot_lines'] in self.axes.lines:
                    self.axes.lines.pop(self.axes.lines.index(self.molecules[cur_molecule]['plot_lines']))
                if self.molecules[cur_molecule]['plot_text'] in self.axes.texts:
                    self.axes.texts.remove(self.molecules[cur_molecule]['plot_text'])
                self.molecules[cur_molecule]['plot_lines'] = None
                self.molecules[cur_molecule]['plot_text'] = None
                self.molecule_lookup_points.pop(cur_molecule, None)
        self.redraw()

    @on_trait_change("central_wavenumber, bandwidth")
    def redraw(self):
        self.axes.set_xlim(self.central_wavenumber - self.bandwidth / 2.,
                           self.central_wavenumber + self.bandwidth / 2.)
        self.axes.set_ylim(0, 1.0)
        self.figure.canvas.draw()



AtmosViewer().configure_traits()

