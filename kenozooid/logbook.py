#
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
Dive logbook functionality.
"""

import lxml.etree as et
import os.path
import logging

import kenozooid.uddf as ku

log = logging.getLogger('kenozooid.logbook')


def add_dive(fout, time=None, depth=None, duration=None, dive_no=None, fin=None):
    """
    Add new dive to logbook file.

    The logbook file is created if it does not exist.

    :Parameters:
     fout
        Logbook file.
     time
        Dive time.
     depth
        Dive maximum depth.
     duration
        Dive duration (in minutes).
     dive_no
        Dive number in dive profile file.
     fin
        Dive profile file.
    """
    dive = None # obtained from profile file

    if os.path.exists(fout):
        doc = et.parse(fout).getroot()
    else:
        doc = ku.create()

    if dive_no is not None and fin is not None:
        q = ku.XPath('//uddf:dive[position() = $no]')
        dives = ku.parse(fin, q, no=no)
        dive = next(dives, None)
        if dive is None:
            raise ValueError('Cannot find dive in UDDF profile data')
        if next(dives, None) is not None:
            raise ValueError('Too many dives found')

    elif (time, depth, duration) is not (None, None, None):
        duration = int(duration * 60)
    else:
        raise ValueError('Dive data or dive profile needs to be provided')

    if dive is not None:
        if time is None:
            time = ku.xp(dive, 'datetime/text()')
        if depth is None:
            depth = ku.xp(dive, 'greatestdepth/text()')
        if duration is None:
            duration = ku.xp(dive, 'diveduration/text()')
            
    ku.create_dive_data(doc, time=time, depth=depth,
            duration=duration)

    if dive is not None:
        _, rg = ku.create_node('uddf:profiledata/uddf:repetitiongroup',
                parent=doc)
        rg.append(deepcopy(dive))

    ku.reorder(doc)
    ku.save(doc, fout)


# vim: sw=4:et:ai
