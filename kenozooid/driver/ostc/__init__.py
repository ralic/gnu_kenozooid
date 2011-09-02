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
Driver for OSTC, an open source dive computer.

OSTC dive computer specification and documentation of communication
protocol can be found at address

    http://www.heinrichsweikamp.net/

"""

from collections import OrderedDict
from datetime import datetime, timedelta
from serial import Serial, SerialException
from binascii import hexlify
from functools import partial
import logging

log = logging.getLogger('kenozooid.driver.ostc')

import kenozooid.uddf as ku
import kenozooid.component as kc
from kenozooid.driver import DeviceDriver, Simulator, MemoryDump, DeviceError
from kenozooid.units import C2K
from . import parser as ostc_parser


def pressure(depth):
    """
    Convert depth in meters to pressure in mBars.
    """
    return int(depth + 10)


@kc.inject(DeviceDriver, id='ostc', name='OSTC Driver',
        models=('OSTC', 'OSTC Mk.2', 'OSTC N2'))
class OSTCDriver(object):
    """
    OSTC dive computer driver.
    """
    def __init__(self, port):
        super(OSTCDriver, self).__init__()

        self._device = Serial(port=port,
                baudrate=115200,
                bytesize=8,
                stopbits=1,
                parity='N',
                timeout=5) # 1s timeout is too short sometimes with 'a' command


    def _write(self, cmd):
        log.debug('sending command {}'.format(cmd))
        self._device.write(cmd)
        log.debug('returned after command {}'.format(cmd))


    def _read(self, size):
        assert size > 0
        log.debug('reading {} byte(s)'.format(size))
        data = self._device.read(size)
        log.debug('got {} byte(s) of data'.format(len(data)))
        if len(data) != size:
            raise DeviceError('Device communication error')
        return data


    @staticmethod
    def scan(port=None):
        """
        Look for OSTC dive computer connected to one of USB ports.

        Library pySerial is used, therefore no scanning and port shall be
        specified.
        """
        try:
            drv = OSTCDriver(port)
            log.debug('connected ostc to port {}'.format(port))
            yield drv
        except SerialException as ex:
            log.debug('{}'.format(ex))


    def version(self):
        """
        Read OSTC dive computer firmware version.
        """
        self._write(b'e')
        v1, v2 = self._read(2)
        self._read(16) # fingerprint, ignore as it can be 0x00 if not built yet
        return 'OSTC {}.{}'.format(v1, v2)



@kc.inject(Simulator, id='ostc')
class OSTCSimulator(object):
    """
    OSTC dive computer simulator support.
    """
    def start(self):
        """
        Put OSTC dive computer into dive simulation mode. The dive computer
        will not show dive mode screen until "dived" into configured depth
        (option CF0).
        """
        self.driver._write(b'c')


    def stop(self):
        """
        Stop OSTC dive simulation mode. OSTC stays in dive mode until
        appropriate period of time passes, which is configured with option
        CF2.
        """
        self.driver._write(b'\x00')


    def depth(self, depth):
        """
        Send dive computer to given depth.
        """
        p = pressure(round(depth))
        self.driver._write(bytearray((p,)))



@kc.inject(MemoryDump, id='ostc')
class OSTCMemoryDump(object):
    """
    OSTC dive computer memory dump.
    """
    def dump(self):
        """
        Download OSTC status and all dive profiles.
        """
        self.driver._write(b'a')
        return self.driver._read(33034)


    def dives(self, dump):
        """
        Convert dive data into UDDF format.
        """
        # uddf dive profile sample
        _f = 'alarm', 'deco_depth', 'deco_time', 'deco_kind', 'depth', 'time', 'temp'
        _q = 'uddf:alarm', \
            'uddf:decostop/@duration', 'uddf:decostop/@decodepth', 'uddf:decostop/@kind', \
            'uddf:depth', 'uddf:divetime', 'uddf:temperature',
                
        UDDF_SAMPLE = OrderedDict(zip(_f, _q))

        nodes = []
        dive_data = ostc_parser.get_data(dump.data)

        for h, p in ostc_parser.profiles(dive_data.profiles):
            log.debug('header: {}'.format(hexlify(h)))
            log.debug('profile: {}'.format(hexlify(p)))

            header = ostc_parser.header(h)
            dive_data = ostc_parser.dive_data(header, p)

            # set time of the start of dive
            st = datetime(2000 + header.year, header.month, header.day,
                    header.hour, header.minute)
            # ostc dive computer saves time at the end of dive in its
            # memory, so substract the dive time;
            # sampling amount is substracted as well as below (0, 0)
            # waypoint is added
            duration = timedelta(minutes=header.dive_time_m,
                    seconds=header.dive_time_s + header.sampling)
            st -= duration

            try:
                dn = ku.create_dive_data(time=st,
                        depth=header.max_depth / 100.0,
                        duration=duration.seconds,
                        temp=C2K(header.min_temp / 10.0))

                create_sample = partial(ku.create_dive_profile_sample, dn,
                        queries=UDDF_SAMPLE)

                deco_alarm = False

                # ostc start dive below zero, add (0, 0) waypoint to
                # comply with uddf
                create_sample(time=0, depth=0.0)

                for i, sample in enumerate(dive_data):
                    temp = C2K(sample.temp) if sample.temp else None

                    # deco info
                    deco_time = sample.deco_time if sample.deco_depth else None
                    deco_depth = sample.deco_depth if sample.deco_depth else None
                    deco_kind = 'mandatory' if sample.deco_depth else None

                    # deco info is not stored in each ostc sample, but each
                    # uddf waypoint shall be annotated with deco alarm
                    if deco_alarm and deco_alarm_end(sample):
                        deco_alarm = False
                    elif not deco_alarm and deco_alarm_start(sample):
                        deco_alarm = True

                    create_sample(time=(i + 1) * header.sampling,
                            depth=sample.depth,
                            alarm='deco' if deco_alarm else None,
                            temp=temp,
                            deco_time=deco_time,
                            deco_depth=deco_depth,
                            deco_kind=deco_kind)

                create_sample(time=(i + 2) * header.sampling, depth=0.0)

                yield dn

            except ValueError as ex:
                log.error('invalid dive {0.year:>02d}-{0.month:>02d}-{0.day:>02d}' \
                    ' {0.hour:>02d}:{0.minute:>02d}' \
                    ' max depth={0.max_depth}'.format(header))


    def version(self, data):
        """
        Get OSTC model and version information from raw data.
        """
        status = ostc_parser.get_data(data)
        model = 'OSTC'
        if status.eeprom.serial > 2047:
            model = 'OSTC N2'
        elif status.eeprom.serial > 300:
            model = 'OSTC Mk.2'
        return '{} {}.{}'.format(model, status.ver1, status.ver2)


def deco_alarm_start(sample):
    """
    Check if a dive sample start deco period.

    :Parameters:
     sample
        Dive sample.
    """
    return sample.deco_depth is not None \
        and sample.deco_depth > 0 \
        and sample.deco_time > 0 \
        and sample.depth - sample.deco_depth <= 1.0


def deco_alarm_end(sample):
    """
    Check if a dive sample ends deco period.

    :Parameters:
     sample
        Dive sample.
    """
    return sample.deco_time is not None \
        and (sample.depth - sample.deco_depth > 1.0
            or sample.deco_depth == 0
            or sample.deco_time == 160
            or sample.deco_time == 0)

# vim: sw=4:et:ai
