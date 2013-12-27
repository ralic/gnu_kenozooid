#
# Kenozooid - dive planning and analysis toolbox.
#
# Copyright (C) 2009-2013 by Artur Wroblewski <wrobell@pld-linux.org>
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
Decompression dive planning.
"""

import re
from collections import namedtuple

from kenozooid.data import gas
from kenozooid.calc import mod


RE_GAS = re.compile("""
    ^(?P<name>
        (?P<type> O2 | AIR | EAN | TX)
        ((?<=TX|AN)(?P<o2>[0-9]{2}))?
        ((?<=TX..)/(?P<he>[0-9]{2}))?
    )
    (@(?P<depth>[0-9]+))?
    (\|(?P<tank>([2-9]x[1-9]{1,2})))?
    $
""", re.VERBOSE)


class GasList(object):
    """
    List of gas mixes.

    :var travel_gas: List of travel gas mixes.
    :var bottom_gas: Bottom gas mix.
    :var deco_gas: List of decompression gas mixes.
    """
    def __init__(self, gas):
        """
        Create list of gas mixes.

        :param gas: Bottom gas mix.
        """
        self.bottom_gas = gas
        self.travel_gas = []
        self.deco_gas = []



class DivePlan(object):
    """
    Dive plan information.

    :var profiles: List of dive profiles.
    """
    def __init__(self):
        self.profiles = []



class DiveProfile(object):
    """
    Dive profile information.

    :var type: Dive profile type.
    :var gas_list: Gas list for the dive profile.
    :var depth: Maximum dive depth.
    :var time: Dive bottom time.
    :var slate: Dive slate.
    :var gas_info: Gas mix requirements.
    """
    def __init__(self, type, gas_list, depth, time):
        self.type = type
        self.gas_list = gas_list
        self.depth = depth
        self.time = time
        self.slate = []
        self.gas_info = []



class DiveProfileType(object):
    """
    Dive profile type.

    The dive profile types are

    PLANNED
        Dive profile planned by a diver.
    EXTENDED
        Extended dive profile compared to planned dive profile.
    LOST_GAS
        Dive profile as planned dive but for lost decompression gas.
    EXTENDED_LOST_GAS
        Combination of `EXTENDED` and `LOST_GAS` dive profiles.
    """
    PLANNED = 'planned'
    EXTENDED = 'extended'
    LOST_GAS = 'lost gas'
    EXTENDED_LOST_GAS = 'extended + lost gas'



def plan_deco_dive(gas_list, depth, time, ext=(5, 3)):
    """
    Plan decompression dive.
    """
    ext_depth = depth + ext[0]
    ext_time = time + ext[1]

    lost_gas_list = GasList(gas_list.bottom_gas)
    lost_gas_list.travel_gas.extend(gas_list.travel_gas)

    plan = DivePlan()

    p = DiveProfile(DiveProfileType.PLANNED, gas_list, depth, time)
    plan.profiles.append(p)

    p = DiveProfile(DiveProfileType.EXTENDED, gas_list, ext_depth, ext_time)
    plan.profiles.append(p)

    p = DiveProfile(DiveProfileType.LOST_GAS, lost_gas_list, depth, time)
    plan.profiles.append(p)

    p = DiveProfile(
        DiveProfileType.EXTENDED_LOST_GAS, lost_gas_list, ext_depth, ext_time
    )
    plan.profiles.append(p)

    for p in plan.profiles:
        stops = deco_stops(p)
        p.slate = dive_slate(p, stops)
        p.gas_info = gas_info(p)

    return plan


def deco_stops(profile):
    """
    Calculate decompression stops for a dive profile.

    :param profile: Dive profile information.
    """
    import decotengu # configurable in the future, do not import globally
    engine, dt = decotengu.create()

    gas_list = profile.gas_list

    # add gas mix information to decompression engine
    for m in gas_list.travel_gas:
        engine.add_gas(m.depth, m.o2, m.he, travel=True)
    m = gas_list.bottom_gas
    engine.add_gas(m.depth, m.o2, m.he)
    for m in gas_list.deco_gas:
        engine.add_gas(m.depth, m.o2, m.he)

    list(engine.calculate(profile.depth, profile.time))

    return dt.stops


def dive_slate(profile, stops):
    """
    Calculate dive slate for a dive profile.

    The dive decompression stops is a collection of items implementing the
    following interface

    depth
        Depth of dive stop [m].
    time
        Time of dive stop [min].

    :param profile: Dive profile information.
    :parma stops: Dive decompression stops.
    """
    slate = []

    gas_list = profile.gas_list
    depth = profile.depth
    # runtime is float number, which tracks minute and fraction of minute,
    # but it is rounded when added to dive slate
    rt = 0
    fs = stops[0]

    # travel zone
    if gas_list.travel_gas:
        prev_depth = 0
        slate.append((0, None, 0, gas_list.travel_gas[0]))
        for m in gas_list.travel_gas[1:]:
            rt += (m.depth - prev_depth) / 10
            slate.append((m.depth, None, round(rt), m))
            prev_depth = m.depth
        m = gas_list.bottom_gas
        rt += (m.depth - prev_depth) / 10
        slate.append((m.depth, None, round(rt), m))

    # dive bottom
    rt = profile.time # reset runtime to dive bottom time
    m = None if gas_list.travel_gas else gas_list.bottom_gas
    slate.append((depth, None, rt, m))

    # deco free zone
    switch = [m for m in gas_list.deco_gas if m.depth > fs.depth]
    prev_depth = depth
    for m in switch:
        rt += (prev_depth - m.depth) / 10
        slate.append((m.depth, None, round(rt), m))
        prev_depth = m.depth

    # deco zone
    switch = {(m.depth // 3) * 3: m for m in gas_list.deco_gas if m.depth <= fs.depth}
    for s in stops:
        m = switch.get(s.depth)
        rt += (prev_depth - s.depth) / 10
        rt += s.time
        slate.append((s.depth, s.time, round(rt), m))
        prev_depth = s.depth

    rt += prev_depth / 10
    slate.append((0, None, round(rt), None))

    return slate


def gas_info(profile):
    """
    Calculate gas requirements information.

    :param profile: Dive profile information.
    """
    info = []
    return info


def plan_to_text(plan):
    """
    Convert decompressiond dive plan to text.
    """
    txt = []
    for p in plan.profiles:
        txt.append('')

        t = 'Slate: {}'.format(p.type)
        txt.append(t)
        txt.append('-' * len(t))

        slate = p.slate
        t = ' {:>3} {:>3} {:>4} {:7}'.format('D', 'DT', 'RT', 'GAS')
        txt.append(t)
        txt.append(' ' + '-' * (len(t) - 1))
        for item in slate:
            st = int(item[1]) if item[1] else ''

            m = item[3]
            star = '*' if m else ' '
            m = m.name if m else ''

            t = '{}{:>3} {:>3} {:>4} {}'.format(
                star, int(item[0]), st, int(item[2]), m
            )
            txt.append(t)

    return '\n'.join(txt)


def parse_gas(t, travel=False):
    """
    Parse gas mix.

    :param t: Gas mix string.
    :param travel: True if travel gas mix.
    """
    t = t.upper()
    v = RE_GAS.search(t)
    m = None

    if v:
        n = v.group('name')

        p = v.group('o2')
        if p is None:
            if n == 'AIR':
                o2 = 21
            elif n == 'O2':
                o2 = 100
            else:
                return None
        else:
            o2 = int(p)

        p = v.group('he')
        he = 0 if p is None else int(p)

        p = v.group('depth')
        depth = mod(o2, 1.6) if p is None else int(p)
        #tank = v.group('tank')
        m = gas(o2, he, depth=int(depth))

    return m


def parse_gas_list(*args):
    """
    Parse gas mix list.

    :param *args: List of gas mix strings.
    """
    travel_gas = [parse_gas(a[1:], True) for a in args if a[0] == '+']
    deco_gas = [parse_gas(a) for a in args if a[0] != '+']
    bottom_gas = deco_gas[0]
    del deco_gas[0]

    gl = GasList(bottom_gas)
    gl.travel_gas.extend(travel_gas)
    gl.deco_gas.extend(deco_gas)
    return gl


# vim: sw=4:et:ai
