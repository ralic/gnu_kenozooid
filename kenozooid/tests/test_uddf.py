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
UDDF file format tests.
"""

from lxml import etree as et
from cStringIO import StringIO
from datetime import datetime
from functools import partial
import unittest

import kenozooid.uddf as ku


UDDF_PROFILE = """\
<?xml version="1.0" encoding="utf-8"?>
<uddf xmlns="http://www.streit.cc/uddf" version="3.0.0">
  <generator>
    <name>kenozooid</name>
    <version>0.1.0</version>
    <manufacturer>
      <name>Kenozooid Team</name>
      <contact>
        <homepage>http://wrobell.it-zone.org/kenozooid/</homepage>
      </contact>
    </manufacturer>
    <datetime>2010-11-16 23:55:13</datetime>
  </generator>
  <diver>
    <owner>
      <personal>
        <firstname>Anonymous</firstname>
        <lastname>Guest</lastname>
      </personal>
      <equipment>
        <divecomputer id="su">
          <model>Sensus Ultra</model>
        </divecomputer>
      </equipment>
    </owner>
  </diver>
  <profiledata>
    <repetitiongroup>
      <dive>
        <datetime>2009-09-19 13:10:23</datetime>
        <samples>
          <waypoint>
            <depth>1.48</depth>
            <divetime>0</divetime>
            <temperature>289.02</temperature>
          </waypoint>
          <waypoint>
            <depth>2.43</depth>
            <divetime>10</divetime>
            <temperature>288.97</temperature>
          </waypoint>
          <waypoint>
            <depth>3.58</depth>
            <divetime>20</divetime>
          </waypoint>
        </samples>
      </dive>
      <dive>
        <datetime>2010-10-30 13:24:43</datetime>
        <samples>
          <waypoint>
            <depth>2.61</depth>
            <divetime>0</divetime>
            <temperature>296.73</temperature>
          </waypoint>
          <waypoint>
            <depth>4.18</depth>
            <divetime>10</divetime>
          </waypoint>
          <waypoint>
            <depth>6.25</depth>
            <divetime>20</divetime>
          </waypoint>
          <waypoint>
            <depth>8.32</depth>
            <divetime>30</divetime>
            <temperature>297.26</temperature>
          </waypoint>
        </samples>
      </dive>
    </repetitiongroup>
  </profiledata>
</uddf>
"""

UDDF_DUMP = """\
<?xml version='1.0' encoding='utf-8'?>
<uddf xmlns="http://www.streit.cc/uddf" version="3.0.0">
  <generator>
    <name>kenozooid</name>
    <version>0.1.0</version>
    <manufacturer>
      <name>Kenozooid Team</name>
      <contact>
        <homepage>http://wrobell.it-zone.org/kenozooid/</homepage>
      </contact>
    </manufacturer>
    <datetime>2010-11-07 21:13:24</datetime>
  </generator>
  <diver>
    <owner>
      <personal>
        <firstname>Anonymous</firstname>
        <lastname>Guest</lastname>
      </personal>
      <equipment>
        <divecomputer id="ostc">
          <model>OSTC Mk.1</model>
        </divecomputer>
      </equipment>
    </owner>
  </diver>
  <divecomputercontrol>
    <divecomputerdump>
      <link ref="ostc"/>
      <datetime>2010-11-07 21:13:24</datetime>
      <!-- dcdump: '01234567890abcdef' -->
      <dcdump>QlpoOTFBWSZTWZdWXlwAAAAJAH/gPwAgACKMmAAUwAE0xwH5Gis6xNXmi7kinChIS6svLgA=</dcdump>
    </divecomputerdump>
  </divecomputercontrol>
</uddf>
"""

class FindDataTestCase(unittest.TestCase):
    """
    Data search within UDDF tests.
    """
    def test_parsing(self):
        """Test basic XML parsing routine"""
        f = StringIO(UDDF_PROFILE)
        depths = list(ku.parse(f, '//uddf:waypoint//uddf:depth/text()'))
        self.assertEqual(7, len(depths))

        expected = ['1.48', '2.43', '3.58', '2.61', '4.18', '6.25', '8.32']
        self.assertEqual(expected, depths)


    def test_dive_data(self):
        """Test parsing UDDF default dive data"""
        f = StringIO(UDDF_PROFILE)
        node = ku.parse(f, '//uddf:dive[1]').next()
        dive = ku.dive_data(node)
        self.assertEquals(datetime(2009, 9, 19, 13, 10, 23), dive.time)


    def test_profile_data(self):
        """Test parsing UDDF default dive profile data"""
        f = StringIO(UDDF_PROFILE)
        node = ku.parse(f, '//uddf:dive[2]').next()
        profile = list(ku.dive_profile(node))
        self.assertEquals(4, len(profile))

        self.assertEquals((0, 2.61, 296.73), profile[0])
        self.assertEquals((10, 4.18, None), profile[1])
        self.assertEquals((20, 6.25, None), profile[2])
        self.assertEquals((30, 8.32, 297.26), profile[3])


    def test_dump_data(self):
        """Test parsing UDDF dive computer dump data"""
        f = StringIO(UDDF_DUMP)
        node = ku.parse(f, '//uddf:divecomputerdump').next()
        dump = ku.dump_data(node)

        expected = ('ostc',
                'OSTC Mk.1',
                datetime(2010, 11, 7, 21, 13, 24),
                '01234567890abcdef')
        self.assertEquals(expected, dump)


    def test_dump_data_decode(self):
        """Test dive computer data decoding stored in UDDF dive computer dump file
        """
        data = 'QlpoOTFBWSZTWZdWXlwAAAAJAH/gPwAgACKMmAAUwAE0xwH5Gis6xNXmi7kinChIS6svLgA='
        s = ku._dump_decode(data)
        self.assertEquals('01234567890abcdef', s)



class CreateDataTestCase(unittest.TestCase):
    """
    UDDF creation and saving tests
    """
    def test_create_basic(self):
        """
        Test basic UDDF file creation.
        """
        now = datetime.now()

        doc = ku.create(time=now)
        self.assertEquals('3.0.0', doc.get('version'))

        q = '//uddf:generator/uddf:datetime/text()'
        dt = doc.xpath(q, namespaces=ku._NSMAP)
        self.assertEquals(now.strftime(ku.FMT_DATETIME), dt[0])


    def test_save(self):
        """
        Test UDDF data saving
        """
        doc = ku.create()
        f = StringIO()
        ku.save(doc, f)
        s = f.getvalue()
        self.assertFalse('uddf:' in s)
        f.close() # check if file closing is possible

        preamble = """\
<?xml version='1.0' encoding='utf-8'?>
<uddf xmlns="http://www.streit.cc/uddf" version="3.0.0">\
"""
        self.assertTrue(s.startswith(preamble), s)


    def test_create_data(self):
        """
        Test generic method for creating XML data
        """
        doc = et.XML('<uddf><diver></diver></uddf>')
        fq = {
            'fname': 'diver/firstname',
            'lname': 'diver/lastname',
        }
        ku.create_data(doc, fq, fname='A', lname='B')

        sd = et.tostring(doc)

        divers = doc.xpath('//diver')
        self.assertEquals(1, len(divers), sd)
        self.assertTrue(divers[0].text is None, sd)

        fnames = doc.xpath('//firstname/text()')
        self.assertEquals(1, len(fnames), sd)
        self.assertEquals('A', fnames[0], sd)

        lnames = doc.xpath('//lastname/text()')
        self.assertEquals(1, len(lnames), sd)
        self.assertEquals('B', lnames[0], sd)

        # create first name but not last name
        ku.create_data(doc, fq, fname='X')
        sd = et.tostring(doc)

        divers = doc.xpath('//diver')
        self.assertEquals(1, len(divers), sd)
        self.assertTrue(divers[0].text is None, sd)

        fnames = doc.xpath('//firstname/text()')
        self.assertEquals(2, len(fnames), sd)
        self.assertEquals(['A', 'X'], fnames, sd)

        lnames = doc.xpath('//lastname/text()')
        self.assertEquals(1, len(lnames), sd)
        self.assertEquals('B', lnames[0], sd)


    def test_create_node(self):
        """
        Test generic method for creating XML nodes
        """
        doc = et.XML('<uddf><diver></diver></uddf>')

        dq = et.XPath('//diver')
        tq = et.XPath('//test')

        d, t = ku.create_node('diver/test')
        self.assertEquals('diver', d.tag)
        self.assertEquals('test', t.tag)

        list(ku.create_node('diver/test', parent=doc))
        sd = et.tostring(doc, pretty_print=True)
        self.assertEquals(1, len(dq(doc)), sd)
        self.assertEquals(1, len(tq(doc)), sd)

        list(ku.create_node('diver/test', parent=doc))
        sd = et.tostring(doc, pretty_print=True)
        self.assertEquals(1, len(dq(doc)), sd)
        self.assertEquals(2, len(tq(doc)), sd)


    def test_create_dc_data(self):
        """
        Test creating dive computer information data in UDDF file
        """
        doc = ku.create()
        xpath = partial(doc.xpath, namespaces=ku._NSMAP)
        owner = xpath('//uddf:owner')[0]

        ku.create_dc_data(owner, dc_model='Test 1')
        sd = et.tostring(doc, pretty_print=True)

        id_q = '//uddf:owner//uddf:divecomputer/@id'
        ids = xpath(id_q)
        self.assertEquals(1, len(ids), sd)
        self.assertEquals('id206a9b642b3e16c89a61696ab28f3d5c', ids[0], sd)

        model_q = '//uddf:owner//uddf:divecomputer/uddf:model/text()'
        models = xpath(model_q)
        self.assertEquals('Test 1', models[0], sd)

        # update again with the same model
        ku.create_dc_data(owner, dc_model='Test 1')
        sd = et.tostring(doc, pretty_print=True)
        ids = xpath(id_q)
        self.assertEquals(1, len(ids), sd)

        # add different model
        ku.create_dc_data(owner, dc_model='Test 2')
        sd = et.tostring(doc, pretty_print=True)

        eqs = xpath('//uddf:equipment')
        self.assertEquals(1, len(eqs), sd)

        ids = xpath(id_q)
        self.assertEquals(2, len(ids), sd)
        expected = ['id206a9b642b3e16c89a61696ab28f3d5c',
                'id605e79544a68819ce664c088aba92658']
        self.assertEquals(expected, ids, sd)

        models = xpath(model_q)
        expected = ['Test 1', 'Test 2']
        self.assertEquals(expected, models, sd)


    def test_dump_data_encode(self):
        """Test dive computer data encoding to be stored in UDDF dive computer dump file
        """
        s = ku._dump_encode('01234567890abcdef')
        self.assertEquals('QlpoOTFBWSZTWZdWXlwAAAAJAH/gPwAgACKMmAAUwAE0xwH5Gis6xNXmi7kinChIS6svLgA=', s)



class PostprocessingTestCase(unittest.TestCase):
    """
    UDDF postprocessing tests.
    """
    def test_reorder(self):
        """Test UDDF reordering
        """
        doc = et.parse(StringIO("""
<uddf xmlns="http://www.streit.cc/uddf">
<profiledata>
<repetitiongroup>
<dive>
    <datetime>2009-03-02 23:02</datetime>
</dive>
<dive>
    <datetime>2009-04-02 23:02</datetime>
</dive>
<dive>
    <datetime>2009-04-02 23:02</datetime>
</dive>
<dive>
    <datetime>2009-03-02 23:02</datetime>
</dive>
</repetitiongroup>
<repetitiongroup> <!-- one more repetition group which shall be removed -->
<dive>
    <datetime>2009-03-02 23:02</datetime>
</dive>
</repetitiongroup>
</profiledata>
</uddf>
"""))
        ku.reorder(doc)

        f = StringIO()
        ku.save(doc.getroot(), f)

        f = StringIO(f.getvalue())

        nodes = list(ku.parse(f, '//uddf:repetitiongroup'))
        self.assertEquals(1, len(nodes))
        nodes = list(ku.parse(f, '//uddf:dive'))
        self.assertEquals(2, len(nodes))

        # check the order of dives
        times = list(ku.parse(f, '//uddf:dive/uddf:datetime/text()'))
        self.assertEquals(['2009-03-02 23:02', '2009-04-02 23:02'], times)


# vim: sw=4:et:ai
