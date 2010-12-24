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
Tests for Kenozooid utility functions.
"""

import unittest

from kenozooid.util import nformat

class FormatTestCase(unittest.TestCase):
    """
    Formatting tests.
    """
    def test_format(self):
        """Test None value formatting"""
        self.assertEquals('test ', nformat('{0} {1}', 'test', None))
        self.assertEquals('', nformat('{0}', None))


# vim: sw=4:et:ai