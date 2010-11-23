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
UDDF file format support.
"""

from lxml import etree as et
from datetime import datetime
from dateutil.parser import parse as dparse
from operator import itemgetter
import pwd
import os
import re
import bz2
import base64
import logging

log = logging.getLogger('kenozooid.uddf')

import kenozooid

RE_Q = re.compile(r'(\b[a-z]+)')


class UDDFFile(object):
    pass
    def set_model(self, id, model):
        """
        Set dive computer model, from which data was dumped.
        """
        tree = self.tree
        root = tree.getroot()
        dc = tree.find(q('//diver/owner//divecomputer'))
        dc.set('id', id)
        dc.model = model


    def get_model_id(self):
        """
        Get dive computer model id, which data is stored in UDDF file.
        """
        dc = self.tree.find(q('//diver/owner//divecomputer'))
        return dc.get('id')


    def get_model(self):
        """
        Get model of dive computer, which data is stored in UDDF file.
        """
        tree = self.tree
        model = tree.find(q('//diver/owner//divecomputer/model'))
        return model.text


    @staticmethod
    def get_datetime(node):
        """
        Get datetime instance from XML node parsed from UDDF file.

        :Parameters:
         node
            Parsed XML node.
        """
        return dparse(node.datetime.text)



class UDDFProfileData(UDDFFile):
    """
    UDDF file containing dive profile data.
    """
#    UDDF = UDDF_TMPL % """\
#<profiledata>
#</profiledata>
#"""
    def create(self):
        """
        Create an UDDF file suitable for storing dive profile data.
        """
        super(UDDFProfileData, self).create()


    def save(self, fn):
        """
        Save UDDF data to a file.

        :Parameters:
         fn
            Name of output file to save UDDF data in.
        """
        self.compact()
        super(UDDFProfileData, self).save(fn)


    def get_dives(self):
        """
        Get list of dives stored in an UDDF file.
        """
        dives = self.tree.findall(q('//dive'))
        for i, dive in enumerate(dives):
            k = i + 1
            samples = dive.findall(q('samples/waypoint'))
            depths = [float(s.depth.text) for s in samples]
            times = [float(s.time) / 60 for s in samples]
            
            yield (k, self.get_datetime(dive), times[-1], max(depths))



class UDDFDeviceDump(UDDFFile):
    """
    UDDF device dump file contains all data fetched from a device.

    The binary data fetched from a device is compressed with bzip2 and then
    encoded with base64. Decoding the data is very simple in Python::

        s = base64.b64decode(encoded) # encoded = getdcalldata text
        decoded = bz2.decompress(s)

    """
#    UDDF = UDDF_TMPL % """\
#<divecomputercontrol>
#    <divecomputerdump>
#        <link ref=''/>
#        <datetime></datetime>
#        <dcdump></dcdump>
#    </divecomputerdump>
#</divecomputercontrol>
#"""
    def create(self):
        """
        Create an UDDF file suitable for storing dive profile data.
        """
        super(UDDFDeviceDump, self).create()
        tree = self.tree
        root = tree.getroot()
        dump = root.divecomputercontrol.divecomputerdump
        dump.datetime = datetime.now().strftime(FMT_DATETIME)


    def set_data(self, data):
        """
        Encode and set data of a device into appropriate node of UDDF file.

        :Parameters:
         data
            Device data to be stored in UDDF file.
        """
        tree = self.tree
        root = tree.getroot()
        dump = root.divecomputercontrol.divecomputerdump

        dc = tree.find(q('//diver/owner//divecomputer'))
        dc_id = dc.get('id')
        assert dc_id
        dump.link.set('ref', dc_id)

        dump.dcdump = self.encode(data)


    def get_data(self):
        """
        Get and decode data of a device.
        """
        root = self.tree.getroot()
        dcdump = root.divecomputercontrol.divecomputerdump.dcdump
        return self.decode(dcdump.text)


    @staticmethod
    def encode(data):
        """
        Encode device data, so it can be stored in UDDF file.

        The encoded string is returned.
        """
        s = bz2.compress(data)
        return base64.b64encode(s)


    @staticmethod
    def decode(data):
        """
        Decode device data, which is stored in UDDF file.

        Decoded device data is returned.
        """
        s = base64.b64decode(data)
        return bz2.decompress(s)



def q(expr):
    """
    Convert tag names and ElementPath expressions to qualified ones. 
    """
    return RE_Q.sub('{http://www.streit.cc/uddf}\\1', expr)


def has_deco(w):
    """
    Check if a waypoint has deco information.
    """
    return hasattr(w, 'alarm') and any(a.text == 'deco' for a in w.alarm)


def has_temp(w):
    """
    Check if a waypoint has temperature information.
    """
    return hasattr(w, 'temperature')

"""
UDDF file format support.

UDDF files are basis for Kenozooid data model.

The UDDF data is parsed and queried with XPath. The result of a query is
generator[1] of records (named tuples in Python terms), which should
guarantee memory efficiency[2].

Module `lxml` is used for XML parsing and XPath querying and full
capabilities of underlying `libxml2' library should be used. The
ElementTree XML data model is used.

Namespace Support
=================
Each tag name in every XPath expression should be prefixed with `uddf`
string. Appropriate namespace mapping for this prefix is defined for each
XPath query.

Remarks
=======
[1] Ideally, it is generator. Some of the routines implemented in this
module need to be optimized to _not_ return lists.

TODO: More research is needed to cache results of some of the queries. 
"""

from collections import namedtuple
from lxml import etree as et
from functools import partial

#
# Default UDDF namespace mapping.
#
_NSMAP = {'uddf': 'http://www.streit.cc/uddf'}

#
# Parsing and searching.
#

# XPath query constructor for UDDF data.
XPath = partial(et.XPath, namespaces=_NSMAP)

# XPath query for default dive data
XP_DEFAULT_DIVE_DATA = (XPath('uddf:datetime/text()'), )

# XPath query for default dive profile sample data
XP_DEFAULT_PROFILE_DATA =  (XPath('uddf:divetime/text()'),
        XPath('uddf:depth/text()'),
        XPath('uddf:temperature/text()'))

# XPath query to locate dive profile sample
XP_WAYPOINT = XPath('.//uddf:waypoint')


class RangeError(ValueError):
    """
    Error raised when a range cannot be parsed.

    .. seealso::
        node_range
    """
    pass


def parse(f, query):
    """
    Find nodes in UDDF file using XPath query.

    UDDF file can be a file name, file object, URL or basically everything
    what is supported by `lxml`.

    :Parameters:
     f
        UDDF file to parse.
     query
        XPath expression.
    """
    log.debug('parsing and searching with with query: {0}'.format(query))
    doc = et.parse(f)
    for n in doc.xpath(query, namespaces=_NSMAP):
        yield n


def find_data(name, node, fields, fqueries, types, nquery=None):
    """
    Find data records starting from specified XML node.

    A record type (namedtuple) is created with specified fields. The data
    of a record is retrieved with XPath expression objects, which is
    converted from string to appropriate type using types information.

    A type converter can be any function, i.e. `float`, `int` or
    `dateutil.parser.parse`.

    If XML node is too high to execture XPath expression objects, then the
    basis for field queries can be relocated with `nquery` parameter. If
    `nquery` parameter is not specified, then only one record is returned.
    Otherwise it is generator of records.

    The length of fields, types and field queries should be the same.

    :Parameters:
     name
        Name of the record to be created.
     node
        XML node.
     fields
        Names of fields to be created in a record.
     fqueries
        XPath expression objects for each field to retrieve its value.
     types
        Type converters of field values to be created in a record.
     nquery
        XPath expression object to relocate from node to more appropriate
        position in XML document for record data retrieval.

    .. seealso::
        dive_data
        dive_profile
    """
    T = namedtuple(name, ' '.join(fields))._make
    if nquery:
        data = nquery(node)
        return (_record(T, n, fqueries, types) for n in data)
    else:
        return _record(T, node, fqueries, types)


def dive_data(node, fields=None, fqueries=None, types=None):
    """
    Specialized function to return record of a dive data.

    At the moment record of dive data contains dive start time only, by
    default. It should be enhanced in the future to return more rich data
    record.

    Dive record data can be reconfigured with optional fields, types and
    field queries parameters.

    :Parameters:
     node
        XML node.
     fields
        Names of fields to be created in a record.
     fqueries
        XPath expression object for each field to retrieve its value.
     types
        Type converters of field values to be created in a record.

    .. seealso::
        find_data
    """

    if fields is None:
        fields = ('time', )
        fqueries = XP_DEFAULT_DIVE_DATA
        types = (dparse, )

    return find_data('Dive', node, fields, fqueries, types)


def dive_profile(node, fields=None, fqueries=None, types=None):
    """
    Specialized function to return generator of dive profiles records.

    By default, dive profile record contains following fields

    time
        dive time is seconds
    depth
        dive depth in meters
    temp
        temperature in Kelvins

    Dive profile record data can be reconfigured with optional fields,
    types and field queries parameters.

    :Parameters:
     node
        XML node.
     fields
        Names of fields to be created in a record.
     fqueries
        XPath expression objects for each field to retrieve its value.
     types
        Type converters of field values to be created in a record.

    .. seealso::
        find_data
    """
    if fields is None:
        fields = ('time', 'depth', 'temp')
        fqueries = XP_DEFAULT_PROFILE_DATA
        types = (float, ) * 3

    return find_data('Sample', node, fields, fqueries, types,
            nquery=XP_WAYPOINT)


def node_range(s):
    """
    Parse textual representation of number range into XPath expression.

    Examples of a ranges

    >>> node_range('1-3,5')
    '1 <= position() and position() <= 3 or position() = 5'

    >>> node_range('-3,10')
    'position() <= 3 or position() = 10'

    Example of infinite range

    >>> node_range('20-')
    '20 <= position()'

    :Parameters:
     s
        Textual representation of number range.
    """
    data = []
    try:
        for r in s.split(','):
            d = r.split('-')
            if len(d) == 1:
                data.append('position() = %d' % int(d[0]))
            elif len(d) == 2:
                p1 = d[0].strip()
                p2 = d[1].strip()
                if p1 and p2:
                    data.append('%d <= position() and position() <= %d' \
                            % (int(p1), int(p2)))
                elif p1 and not p2:
                    data.append('%d <= position()' % int(p1))
                elif not p1 and p2:
                    data.append('position() <= %d' % int(p2))
            else:
                raise RangeError('Invalid range %s' % s)
    except ValueError, ex:
        raise RangeError('Invalid range %s' % s)
    return ' or '.join(data)


def _record_data(node, query, t=float):
    """
    Find text value of a node starting from specified XML node.

    The text value is converted with function `t` and then returned.

    If node is not found, then `None` is returned.

    :Parameters:
     node
        XML node.
     query
        XPath expression object to find node with text value.
     t
        Function to convert text value to requested type.
    """
    data = query(node)
    if data:
        return t(data[0])


def _record(rt, node, fqueries, types):
    """
    Create record with data.

    The record data is found with XPath expressions objects starting from
    XML node.  The data is converted using functions specified in `types`
    parameters.

    :Parameters:
    rt
        Record type (named tuple) of record data.
    node
        XML node.
     fqueries
        XPath expression objects for each field to retrieve its value.
     types
        Type converters of field values to be created in a record.
    """
    return rt(_record_data(node, f, t) for f, t in zip(fqueries, types))


#
# Creating UDDF data.
#

# default format for timestamps within UDDF file
FMT_DATETIME = '%Y-%m-%d %H:%M:%S%z'

# basic data for an UDDF file
UDDF_BASIC = """\
<uddf xmlns="http://www.streit.cc/uddf" version="3.0.0">
<generator>
    <name>kenozooid</name>
    <version>{kzver}</version>
    <manufacturer>
      <name>Kenozooid Team</name>
      <contact>
        <homepage>http://wrobell.it-zone.org/kenozooid/</homepage>
      </contact>
    </manufacturer>
    <datetime></datetime>
</generator>
<diver>
    <owner>
        <personal>
            <firstname>Anonymous</firstname>
            <lastname>Guest</lastname>
        </personal>
    </owner>
</diver>
</uddf>
""".format(kzver=kenozooid.__version__)

###<equipment>
###    <divecomputer id=''>
###        <model></model>
###    </divecomputer>
###</equipment>


def create(time=datetime.now()):
    """
    Create basic UDDF structure.

    :Parameters:
     time
        Timestamp of file creation, current time by default.
    """
    root = et.XML(UDDF_BASIC)

    now = datetime.now()
    n = root.xpath('//uddf:generator/uddf:datetime', namespaces=_NSMAP)[0]
    n.text = time.strftime(FMT_DATETIME)
    return root


def save(doc, f, validate=True):
    """
    Save UDDF data to a file.

    A file can be a file name or file like object.

    :Parameters:
     doc
        UDDF document to save.
     f
        UDDF output file.
     validate
        Validate UDDF file before saving if set to True.
    """
    log.debug('cleaning uddf file')
    #et.deannotate(doc)
    et.cleanup_namespaces(doc)

    if validate:
        log.debug('validating uddf file')
        #schema = et.XMLSchema(et.parse(open('uddf/uddf.xsd')))
        #schema.assertValid(doc.getroot())

    fopened = False
    if isinstance(f, basestring):
        fopened = True
        f = open(f)

    data = et.tostring(doc,
            encoding='utf-8',
            xml_declaration=True,
            pretty_print=True)
    f.write(data)

    if fopened:
        f.close()


def reorder(doc):
    """
    Reorder and cleanup dives in UDDF document.

    Following operations are being performed

    - dives are sorted by dive start time 
    - duplicate dives and repetition groups are removed

    :Parameters:
     doc
        UDDF document.

    TODO: Put dives into appropriate repetition groups.
    """
    find = partial(doc.xpath, namespaces=_NSMAP)

    profiles = find('//uddf:profiledata')
    rgroups = find('//uddf:profiledata/uddf:repetitiongroup')
    if not profiles or not rgroups:
        raise ValueError('No profile data to reorder')
    pd = profiles[0]

    nodes = find('//uddf:dive')
    times = find('//uddf:dive/uddf:datetime/text()')

    dives = {}
    for n, t in zip(nodes, times):
        dt = dparse(t) # don't rely on string representation for sorting
        if dt not in dives:
            dives[dt] = n

    log.debug('removing old repetition groups')
    for rg in rgroups: # cleanup old repetition groups
        pd.remove(rg)
    rg = et.SubElement(pd, 'repetitiongroup')

    # sort dive nodes by dive time
    log.debug('sorting dives')
    for dt, n in sorted(dives.items(), key=itemgetter(0)):
        rg.append(n)


# vim: sw=4:et:ai
