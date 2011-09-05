# Kenozooid - dive planning and analysis toolbox.
#
# Copyright (C) 2009-2011 by Artur Wroblewski <wrobell@pld-linux.org>
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
Functions for plotting dive profile data.

Plotting functions generate graphs with dive time in minutes of x-axis and
profile data on y-axis (usually depth in meters).

Basic dive information can be shown

- start time of a dive
- time length of a dive
- maximum depth
- minimum temperature during a dive

"""

import rpy2.robjects as ro
R = ro.r

import itertools
import logging

import kenozooid
from kenozooid.util import min2str, FMT_DIVETIME
from kenozooid.units import K2C
import kenozooid.rglue as kr

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
            deco.append((float(s1.time) / 60, float(s1.depth)))
        if has_deco(s2):
            deco.append((float(s2.time) / 60, float(s2.depth)))


def _inject_profile(dp):
    """
    Inject dive profile as data frame into R namespace.

    Created data frame reference is returned.

    :Parameters:
     dp
        Dive profile.   
    """

    vtime, vdepth, vtemp, vdtime, vddepth, vdalarm = zip(*dp)
    df = ro.DataFrame({
        'time': kr.float_vec(vtime),
        'depth': kr.float_vec(vdepth),
        'temp': kr.float_vec(vtemp),
        'deco_time': kr.float_vec(vdtime),
        'deco_depth': kr.float_vec(vddepth),
        'deco_alarm': kr.bool_vec(v == 'deco' for v in vdalarm),
    })
    ro.globalenv['dp'] = df
    return df


def _plot_sig():
    """
    Display Kenozooid signature on a graph.
    """
    R("""
grid.text('generated by kenozooid ver. {ver}', x=0.99, y=0.01,
        just=c('right', 'bottom'),
        gp=gpar(cex=0.6, fontface='italic'))
    """.format(ver=kenozooid.__version__))


def plot(fout, dives, title=False, info=False, temp=False, sig=True,
        legend=False, format='pdf'):
    """
    Plot graphs of dive profiles.
    
    :Parameters:
     fout
        Name of output file.
     dives
        Dives and their profiles to be plotted.
     title
        Set plot title.
     info
        Display dive information (time, depth, temperature).
     temp
        Plot temperature graph.
     sig
        Display Kenozooid signature.
     legend
        Display graph legend.
     format
        Format of output file (i.e. pdf, png, svg).
    """
    R("""
library(Hmisc)
library(grid)

cairo_pdf('%s', width=10, height=5, onefile=T)
    """ % fout)

    if not title:
        R('par(mar=c(5, 4, 1, 2) + 0.1)')

    for dive, dp in dives:
        log.debug('plotting dive profile') 

        _inject_profile(dp)

        R(r"""
ylim = rev(range(dp$depth))
dive_time = dp$time / 60.0
plot(dive_time, dp$depth, ylim=ylim,
    type='l', col='blue',
    xlab='Time [min]', ylab='Depth [m]')

# deco info
if (any(!is.na(dp$deco_time))) {
    deco_depth = approxfun(dp$time, dp$deco_depth, method='constant')(dp$time)

    n = length(dp$time)
    dc = rep(rgb(0, 0, 0.9, 0.4), n - 1)
    dc[which(dp$deco_alarm)] = rgb(0.9, 0, 0, 0.4)
    rect(dive_time[1:n - 1], deco_depth[1:n - 1], dive_time[2:n], rep(0, n - 1),
        col=dc, border=NA, lwd=0)
}

minor.tick(nx=5, ny=2)
grid()
        """)
        if title:
            st = dive.time.strftime(FMT_DIVETIME)
            R("""title('Dive {0}')""".format(st))

        #R('print(p)') # trigger R plotting procedure

        if info:
            R("""
info = 't = {}\n\u21a7 = {:.1f}m\nT = {:.1f}\u00b0C'
grid.text(info, x=0.85, y=0.25, just=c('left', 'bottom'),
    gp=gpar(cex=0.8, fontfamily='monospace'))
            """.format(min2str(dive.duration / 60.0),
                dive.depth,
                K2C(dive.temp)))

        if sig:
            _plot_sig()

    R('dev.off()')


def plot_overlay(fout, dives, title=False, info=False, temp=False, sig=True,
        legend=False, labels=None, format='pdf'):
    """
    Plot dive profiles on one graph.
    
    :Parameters:
     fout
        Name of output file.
     dives
        Dives and their profiles to be plotted.
     title
        Set plot title.
     info
        Display dive information (time, depth, temperature).
     temp
        Plot temperature graph.
     sig
        Display Kenozooid signature.
     legend
        Display graph legend.
     labels
        Alternative labels for dives.
     format
        Format of output file (i.e. pdf, png, svg).
    """

    R("""
library(Hmisc)
library(grid)
library(colorspace)

cairo_pdf('%s', width=10, height=5, onefile=T)
""" % fout)

    if not title:
        R('par(mar=c(5, 4, 1, 2) + 0.1)')

    R("""
times = list()
depths = list()
    """)

    lstr = []
    for k, (dive, dp) in enumerate(dives):
        log.debug('plotting dive profile') 
        _inject_profile(dp)
        R("""
times[[{k}]] = dp$time / 60.0
depths[[{k}]] = dp$depth
        """.format(k=k + 1))

        lstr.append(dive.time.strftime(FMT_DIVETIME))

    k += 1 # total amount of dives

    log.debug('saving graph') 

    # copy labels provided by user
    if not labels:
        labels = []
    for i, l in enumerate(labels):
        if l:
            lstr[i] = l
    ro.globalenv['labels'] = ro.StrVector(lstr)

    R("""
cols = diverge_hcl({nd})

r_time = range(sapply(times, range))
r_depth = range(sapply(depths, range))
plot(NA, xlim=r_time, ylim=rev(r_depth),
    xlab='Time [min]', ylab='Depth [m]')
for (i in 1:{nd}) {{
    lines(times[[i]], depths[[i]], col=cols[i])
}}
minor.tick(nx=5, ny=2)
grid()
""".format(nd=k))
    if legend:
        R("""
if ({nd} > 10) {{
    lscale = 0.7
}} else {{
    lscale = 1.0
}}
legend('bottomright', labels, col=cols, lwd=1, inset=c(0.02, 0.05),
    ncol=ceiling({nd} / 10), cex=lscale)
        """.format(nd=k))

    if sig:
        _plot_sig()

    R('dev.off()')


# vim: sw=4:et:ai
