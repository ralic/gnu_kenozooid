#
# Kenozooid - software stack to support different capabilities of dive
# computers.
#
# Copyright (C) 2009 by wrobell <wrobell@pld-linux.org>
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
Set of interfaces to be implemented by dive computers drivers.

Simple interface injection mechanism and searchable registry for classes
implementing given interface are provided.
"""

import itertools

class DeviceDriver(object):
    def id(self):
        pass


class Simulator(object):
    def start(self):
        pass

    def stop(self):
        pass

    def depth(self, d):
        pass

_registry = {}

def inject(iface, **params):
    """
    Class decorator to declare interface implementation.

    Injection parameters can be used to query for classes implementing an
    interface and having appropriate values.

    :Parameters:
     iface
        Interface to inject.
     params
        Injection parameters.
    """
    def f(cls):
        print 'inject', iface, cls, params

        if iface not in _registry:
            _registry[iface] = []
        _registry[iface].append((cls, params))

        return cls

    return f


def _applies(p1, p2):
    keys = set(p2.keys())
    return all(k in keys and p1[k] == p2[k] for k in p1.keys())


def query(iface=None, **params):
    """
    Look for class implementing specified interface.
    """
    if iface is None:
        data = itertools.chain(*_registry.values())
    elif iface in _registry:
        data = _registry[iface]
    else:
        data = ()

    return (cls for cls, p in data if _applies(params, p))


def params(cls):
    for c, p in itertools.chain(*_registry.values()):
        if c == cls:
            return p
