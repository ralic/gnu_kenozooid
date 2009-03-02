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

from lxml import etree as et
from datetime import datetime
import pwd
import os

GENERATOR = """
<generator>
    <name>Kenozooid</name>
    <version>%(version)s</version>
    <date>
        <year>%(year)d</year><month>%(month)d</month><day>%(day)d</day>
    </date>
    <time>
        <hour>%(hour)d</hour><minute>%(minute)d</minute>
    </time>
</generator>
"""

NSMAP = {
    'uddf': 'http://www.streit.cc/uddf',
}

def create():
    """
    Create UDDF file for dive profile data.
    """
    now = datetime.now()

    name = pwd.getpwnam(os.environ['USER']).pw_gecos.split(' ', 1)
    if len(name) == 1:
        fn = name
        ln = name
    else:
        fn, ln = name

    root = et.Element('{%(uddf)s}uddf' % NSMAP, version='2.2.0', nsmap=NSMAP)
    generator = et.XML(GENERATOR % {
        'version': '0.1',
        'year': now.year,
        'month': now.month,
        'day': now.day,
        'hour': now.hour,
        'minute': now.minute,
    })
    root.append(generator)
    el = et.SubElement(root, 'diver')
    el = et.SubElement(el, 'owner')
    el = et.SubElement(el, 'personal')
    el1 = et.SubElement(el, 'firstname')
    el1.text = fn
    el2 = et.SubElement(el, 'lastname')
    el2.text = ln
    et.SubElement(root, 'profiledata')
    tree = et.ElementTree(root)
    return tree


def validate(tree):
    """
    Validate UDDF file with UDDF XML Schema.
    """
    schema = et.XMLSchema(et.parse(open('uddf/uddf.xsd')))
    schema.assertValid(tree.getroot())

