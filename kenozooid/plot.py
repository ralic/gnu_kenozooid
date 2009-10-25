#
# Kenozooid - software stack to support different capabilities of dive
# computers.
#
# Copyright (C) 2009 by Artur Wroblewski <wrobell@pld-linux.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Plot dive profile graph.

Basic dive information is shown

- time of the dive
- maximum depth
- temperature

Showing any statistical information (like average temperature or depth) is
out of scope, now.
"""

from lxml import objectify as eto
import math
import logging

import matplotlib
matplotlib.use('cairo')

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.font_manager import FontProperties

import kenozooid
from kenozooid.uddf import UDDFProfileData, q, has_deco, has_temp
from kenozooid.units import K2C
from kenozooid.util import min2str, FMT_DIVETIME

log = logging.getLogger('kenozooid.plot')


def get_deco(samples):
    """
    Get iterator of lists containing deco waypoints.
    """
    deco = []
    for s1, s2 in zip(samples[:-1], samples[1:]):
        if has_deco(s1) and not has_deco(s2):
            yield deco
            deco = []
        elif not deco and has_deco(s1):
            deco.append((float(s1.divetime) / 60, float(s1.depth)))
        if has_deco(s2):
            deco.append((float(s2.divetime) / 60, float(s2.depth)))


def plot_dive(dive, fout, title=True, info=True, temp=True, sig=True):
    """
    Plot dive profile graph using Matplotlib library.

    Dive data are fetched from parsed UDDF file (using ETree) and graph is
    saved into graphical file. Type of graphical file depends on output
    file extension and is handled by Matplotlib library.

    :Parameters:
     dive
        Dive node.
     fout
        Output filename.
     title
        Set plot title.
     info
        Display dive information (time, depth, temperature).
     temp
        Plot temperature graph.
    """
    samples = dive.findall(q('samples/waypoint'))
    depths = [float(s.depth) for s in samples]
    times = [float(s.divetime) / 60 for s in samples]

    temps = [K2C(float(s.temperature)) for s in samples if has_temp(s)]
    temp_times = [float(s.divetime) / 60 for s in samples if has_temp(s)]

    max_depth = max(depths)
    max_time = times[-1]
    min_temp = min(temps)
    max_temp = max(temps)

    dive_time = UDDFProfileData.get_time(dive)

    left, width = 0.07, 0.90
    bottom, height = 0.08, 0.87
    if not title:
        height = 0.89
    rect1 = [left, bottom + 0.2, width, height - 0.2]
    rect2 = [left, bottom, width, 0.1]
    axesBG  = '#f6f6f6'

    plt.rc('font', size=10)
    if temp:
        ax_depth = plt.axes(rect1, axisbg=axesBG)
        ax_temp = plt.axes(rect2, axisbg=axesBG, sharex=ax_depth)
    else:
        rect1[1] = bottom
        rect1[-1] = height
        ax_depth = plt.axes(rect1, axisbg=axesBG)

    #ax_depth.plot(times, depths, label='air')
    ax_depth.plot(times, depths, color='blue')
    for deco in get_deco(samples):
        ax_depth.plot(*zip(*deco), color='red')

    # check depth axis limits
    ymin, ymax = ax_depth.get_ylim()
    # some devices may report negative depth (i.e. sensus ultra)
    ymin = max(0, ymin)
    # reverse y-axis, to put 0m depth at top and max depth at the bottom of
    # graph
    ax_depth.set_ylim([ymax, ymin])

    if title:
        ax_depth.set_title(dive_time.strftime(FMT_DIVETIME))
    ax_depth.set_xlabel('Time [min]')
    ax_depth.set_ylabel('Depth [m]')
    ax_depth.legend(loc='lower right', shadow=True)
    if info:
        ax_depth.text(0.95, 0.05,
            u't = %s\n\u21a7 = %.2fm\nT = %.1f\u00b0C' \
                % (min2str(max_time), max_depth, min_temp),
            family='monospace',
            transform=ax_depth.transAxes,
            bbox=dict(facecolor='white', edgecolor='none'),
            multialignment='left',
            horizontalalignment='right',
            verticalalignment='bottom')
    ax_depth.grid(True)

    if temp:
        ax_temp.set_ylim(math.floor(min_temp), math.ceil(max_temp))
        ax_temp.set_ylabel(u'T [\u00b0C]')
        ax_temp.plot(temp_times, temps)
        for l in ax_temp.get_yticklabels():
            l.set_fontsize(8) 
        ax_temp.grid(True)
        ax_temp.yaxis.set_major_locator(MaxNLocator(3))

    # put info about software used to generate the plot
    font = FontProperties()
    font.set_style('italic')
    font.set_size('xx-small')

    f = plt.gcf()
    f.text(left + width, 0.03,
        'generated by kenozooid ver. %s' % kenozooid.__version__,
        fontproperties=font,
        horizontalalignment='right',
        verticalalignment='top')

    # save dive plot and clear matplotlib space
    plt.savefig(fout)
    plt.clf()


def plot(tree, fprefix, format, dives=None, **params):
    """
    Plot graphs of dive profiles using Matplotlib library.
    
    :Parameters:
     tree
        XML file (UDDF data) parsed with ETree API.
     fprefix
        Prefix of output file.
     format
        Format of output file (i.e. pdf, png, svg).
     dives
        Dives to be plotted.
     params
        Additional keyword parameters for `plot_dive` function.
    """
    nodes = tree.findall(q('//dive'))
    n = len(nodes)
    if dives is None:
        dives = range(1, n + 1)
    for i in dives:
        if i > n: # i.e. range was 4-5 and there are only 4 dives
            log.warn('dive number %02d does not exist' % i)
            break
        fout = '%s-%03d.%s' % (fprefix, i, format)
        plot_dive(nodes[i - 1], fout, **params)


