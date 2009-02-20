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

import unittest

from kenozooid.driver.ostc import byte, pressure
from kenozooid.driver.ostc import OSTCMemoryDump
import kenozooid.driver.ostc.parser as ostc_parser
from kenozooid.uddf import create

class ConversionTestCase(unittest.TestCase):
    def test_byte_conversion(self):
        """Test int to to byte conversion
        """
        self.assertEquals('\x00', byte(0))
        self.assertEquals('\xff', byte(0xff))
        self.assertEquals('\x0f', byte(15))


    def test_pressure_conversion(self):
        """Test depth to pressure conversion
        """
        self.assertEquals(11, pressure(1))
        self.assertEquals(30, pressure(20))
        self.assertEquals(25, pressure(15.5))



class UDDFTestCase(unittest.TestCase):
    """
    OSTC data to UDDF format conversion tests.
    """
    def test_conversion(self):
        dumper = OSTCMemoryDump()
        f = open('dumps/ostc-01.dump')
        tree = create()
        dumper.convert(f, tree)
        print
        print
        import lxml.etree
        lxml.etree.dump(tree.getroot())
        print

