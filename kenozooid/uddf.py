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
from lxml import objectify as eto
from datetime import datetime
from operator import itemgetter
import pwd
import os
import re
import bz2
import base64
import logging

log = logging.getLogger('kenozooid.plot')

import kenozooid

RE_Q = re.compile(r'(\b[a-z]+)')

# minimal data for an UDDF file
UDDF_TMPL = """
<uddf xmlns="http://www.streit.cc/uddf" version="2.2.0">
<generator>
    <name>kenozooid</name>
    <version>%s</version>
    <date></date>
    <time></time>
</generator>
%%s
</uddf>
""" % kenozooid.__version__


class UDDFFile(object):
    """
    Basic class for UDDF files.

    The XML tree representing UDDF file is created and can be accessed
    using Objetify API from lxml library.

    The UDDF template needs to be set by all deriving, non-abstract
    classes.

    :Variables:
     tree
        XML tree representing UDDF file.
    :CVariables:
     UDDF
        UDDF template to be parsed by during UDDF file creation.
    """

    # to be set
    UDDF = UDDF_TMPL % ''

    def __init__(self):
        """
        Create an instance of UDDF file with no data.
        """
        self.tree = None


    def create(self):
        """
        Create new UDDF file.
        """
        root = eto.XML(self.UDDF)

        now = datetime.now()
        root.generator.date.year = now.year
        root.generator.date.month = now.month
        root.generator.date.day = now.day
        root.generator.time.hour = now.hour
        root.generator.time.minute = now.minute

        self.tree = et.ElementTree(root)


    def open(self, fn, validate=True):
        """
        Open and parse UDDF file.

        :Parameters:
         fn
            Name of a file containing UDDF data.
         validate
            Validate UDDF file after parsing if set to True.
        """
        f = open(fn)
        self.parse(f)
        f.close()
        if validate:
            self.validate()


    def parse(self, f):
        """
        Parse UDDF file.

        :Parameters:
         f
            File object containing UDDF data.
        """
        self.tree = eto.parse(f)


    def save(self, fn, validate=True):
        """
        Save UDDF data to a file.

        :Parameters:
         fn
            Name of output file to save UDDF data in.
         validate
            Validate UDDF file before saving if set to True.
        """
        self.clean()

        if validate:
            self.validate()

        with open(fn, 'w') as f:
            data = et.tostring(self.tree,
                    encoding='utf-8',
                    xml_declaration=True,
                    pretty_print=True)
            f.write(data)


    def clean(self):
        """
        Clean UDDF XML data structures from unnecessary annotations and
        namespaces.
        """
        log.debug('cleaning uddf file')
        eto.deannotate(self.tree)
        et.cleanup_namespaces(self.tree)


    def validate(self):
        """
        Validate UDDF file with UDDF XML Schema.
        """
        log.debug('validating uddf file')
        schema = et.XMLSchema(et.parse(open('uddf/uddf.xsd')))
        schema.assertValid(self.tree.getroot())


    @staticmethod
    def get_time(node):
        """
        Get datetime instance from XML node parsed from UDDF file.

        :Parameters:
         node
            Parsed XML node.
        """
        year = int(node.date.year)
        month = int(node.date.month)
        day = int(node.date.day)
        hour = int(node.time.hour)
        minute = int(node.time.minute)
        return datetime(year, month, day, hour, minute)



class UDDFProfileData(UDDFFile):
    """
    UDDF file containing dive profile data.
    """
    UDDF = UDDF_TMPL % """\
<diver>
<owner>
<personal></personal>
</owner>
</diver>
<profiledata>
</profiledata>
"""
    def create(self):
        """
        Create an UDDF file suitable for storing dive profile data.
        """
        super(UDDFProfileData, self).create()

        root = self.tree.getroot()

        name = pwd.getpwnam(os.environ['USER']).pw_gecos.split(' ', 1)
        if len(name) == 1:
            fn = name
            ln = name
        else:
            fn, ln = name

        el = root.diver.owner.personal
        el.firstname = fn
        el.lastname = ln


    def save(self, fn):
        """
        Save UDDF data to a file.

        :Parameters:
         fn
            Name of output file to save UDDF data in.
        """
        self.compact()
        super(UDDFProfileData, self).save(fn)


    def compact(self):
        """
        Remove duplicate dives from UDDF file. Dives are sorted by dive
        time.
        """
        root = self.tree.getroot()
        dives = {}
        for dive in self.tree.findall(q('//dive')):
            dt = self.get_time(dive)
            if dt not in dives:
                dives[dt] = dive
        del root.profiledata.repetitiongroup[:]
        n = et.SubElement(root.profiledata, q('repetitiongroup'))
        n.dive = [d[1] for d in sorted(dives.items(), key=itemgetter(0))]


    def get_dives(self):
        """
        Get list of dives stored in an UDDF file.
        """
        dives = self.tree.findall(q('//dive'))
        for i, dive in enumerate(dives):
            k = i + 1
            samples = dive.findall(q('samples/waypoint'))
            depths = [float(s.depth.text) for s in samples]
            times = [float(s.divetime) / 60 for s in samples]
            
            yield (k, self.get_time(dive), times[-1], max(depths))



class UDDFDeviceDump(UDDFFile):
    """
    UDDF device dump file contains all data fetched from a device.

    The binary data fetched from a device is compressed with bzip2 and then
    encoded with base64. Decoding the data is very simple in Python::

        s = base64.b64decode(encoded) # encoded = getdcalldata text
        decoded = bz2.decompress(s)

    """
    UDDF = UDDF_TMPL % """\
<divecomputercontrol>
    <!--
        data is compressed with bzip2, then encoded with base64; to
        decode in Python
            s = base64.b64decode(encoded) # encoded = dcdata text
            decoded = bz2.decompress(s)
        WARNING! dcdata is not part of the standard
    -->
    <dcdata id=''/>
</divecomputercontrol>
"""
    def _get_data_node(self):
        """
        Get node, which stores the data of a device.
        """
        return self.tree.getroot().divecomputercontrol


    def set_data(self, data):
        """
        Encode and set data of a device into appropriate node of UDDF file.

        :Parameters:
         data
            Device data to be stored in UDDF file.
        """
        node = self._get_data_node()
        id = node.dcdata.get('id')
        node.dcdata = self.encode(data)
        if id:
            node.dcdata.set('id', id)


    def get_data(self):
        """
        Get and decode data of a device.
        """
        node = self._get_data_node()
        return self.decode(node.dcdata.text)


    def set_id(self, id):
        """
        Set id of a device, which data is supposed to be stored in UDDF
        file.
        """
        node = self._get_data_node()
        node.dcdata.set('id', id)


    def get_id(self):
        """
        Get id of device, which data is stored in UDDF file.
        """
        node = self._get_data_node()
        return node.dcdata.get('id')


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

