#################################################################
# python fitbit object
# By Kyle Machulis <kyle@nonpolynomial.com>
# http://www.nonpolynomial.com
#
# Distributed as part of the libfitbit project
#
# Repo: http://www.github.com/qdot/libfitbit
#
# Licensed under the BSD License, as follows
#
# Copyright (c) 2011, Kyle Machulis/Nonpolynomial Labs
# All rights reserved.
#
# Redistribution and use in source and binary forms,
# with or without modification, are permitted provided
# that the following conditions are met:
#
#    * Redistributions of source code must retain the
#      above copyright notice, this list of conditions
#      and the following disclaimer.
#    * Redistributions in binary form must reproduce the
#      above copyright notice, this list of conditions and
#      the following disclaimer in the documentation and/or
#      other materials provided with the distribution.
#    * Neither the name of the Nonpolynomial Labs nor the names
#      of its contributors may be used to endorse or promote
#      products derived from this software without specific
#      prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#################################################################
#
# ANT code originally taken from
# http://code.google.com/p/mstump-learning-exercises/source/browse/trunk/python/ANT/ant_twisted.py
# Added to and untwistedized and basically fixed up by Kyle Machulis <kyle@nonpolynomial.com>
#
# What's Done
#
# - Basic ANT protocol implementation
# - Basic FitBit protocol implementation
# - FitBit Base Initialization
# - FitBit Tracker Connection, Initialization, Info Retreival
# - Blind data retrieval (can get it, don't know what it is)
# - Talking to the fitbit website
# - Fix ANT Burst packet identifer
# - Add checksum checks for ANT receive
# - Fix packet status identifiers in ANT
#
# To Do (Big)
#
# - Dividing out into modules (ant classes may become their own library)
# - Figuring out more data formats and packets
# - Implementing data clearing

import itertools, sys, random, operator, datetime, time
from antprotocol.protocol import ANTException, ReceiveException, SendException

class FitBit(object):
    """Class to represent the fitbit tracker device, the portion of
    the fitbit worn by the user. Stores information about the tracker
    (serial number, hardware version, etc...).

    """

    def __init__(self, base = None):
        #: Iterator cycle of 0-8, for creating tracker packet serial numbers
        self.tracker_packet_count = itertools.cycle(range(0,8))

        # The tracker expects to start on 1, i.e. 0x39 This is set
        # after a reset (which is why we create the tracker in the
        # reset function). It won't talk if you try anything else.
        self.tracker_packet_count.next()

        #: used to track which internal databank we're on when
        self.current_bank_id = 0
        #: tracks current packet id for fitbit communication
        self.current_packet_id = None
        #: serial number of the tracker
        self.serial = None
        #: hardware version loaded on the tracker
        self.hardware_version = None
        #: Major version of BSL (?)
        self.bsl_major_version = None
        #: Minor version of BSL (?)
        self.bsl_minor_version = None
        #: Major version of App (?)
        self.app_major_version = None
        #: Minor version of App (?)
        self.app_minor_version = None
        #: True if tracker is in BSL Mode (?), False otherwise
        self.in_mode_bsl = None
        #: True if tracker is currently on charger, False otherwise
        self.on_charger = None

        self.base = base

    def gen_packet_id(self):
        """Generates the next packet id for information sent to the
        tracker.

        """

        self.current_packet_id = 0x38 + self.tracker_packet_count.next()
        return self.current_packet_id

    def parse_info_packet(self, data):
        """Parses the information gotten from the 0x24 retrieval command"""

        self.serial = data[0:5]
        self.hardware_version = data[5]
        self.bsl_major_version = data[6]
        self.bsl_minor_version = data[7]
        self.app_major_version = data[8]
        self.app_minor_version = data[9]
        self.in_mode_bsl = (False, True)[data[10]]
        self.on_charger = (False, True)[data[11]]

    def __str__(self):
        """Returns string representation of tracker information"""

        return "Tracker Serial: %s\n" \
               "Hardware Version: %d\n" \
               "BSL Version: %d.%d\n" \
               "APP Version: %d.%d\n" \
               "In Mode BSL? %s\n" \
               "On Charger? %s\n" % \
               ("".join(["%x" % (x) for x in self.serial]),
                self.hardware_version,
                self.bsl_major_version,
                self.bsl_minor_version,
                self.app_major_version,
                self.app_minor_version,
                self.in_mode_bsl,
                self.on_charger)

    def init_fitbit(self):
        self.init_device_channel([0xff, 0xff, 0x01, 0x01])

    def init_device_channel(self, channel):
        # ANT device initialization
        self.base.reset()
        self.base.send_network_key(0, [0,0,0,0,0,0,0,0])
        self.base.assign_channel()
        self.base.set_channel_period([0x0, 0x10])
        self.base.set_channel_frequency(0x2)
        self.base.set_transmit_power(0x3)
        self.base.set_search_timeout(0xFF)
        self.base.set_channel_id(channel)
        self.base.open_channel()

    def init_tracker_for_transfer(self):
        self.init_fitbit()
        self.wait_for_beacon()
        self.reset_tracker()

        # 0x78 0x02 is device id reset. This tells the device the new
        # channel id to hop to for dumpage
        cid = [random.randint(0,254), random.randint(0,254)]
        self.base.send_acknowledged_data([0x78, 0x02] + cid + [0x00, 0x00, 0x00, 0x00])
        self.base.close_channel()
        self.init_device_channel(cid + [0x01, 0x01])
        self.wait_for_beacon()
        self.ping_tracker()

    def reset_tracker(self):
        # 0x78 0x01 is apparently the device reset command
        self.base.send_acknowledged_data([0x78, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def command_sleep(self):
        self.base.send_acknowledged_data([0x7f, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3c])

    def wait_for_beacon(self):
        self.base.receive_bdcast()

    def _get_tracker_burst(self):
        d = self.base._check_burst_response()
        if d[1] != 0x81:
            raise ReceiveException("Response received is not tracker burst! Got %s" % (d[0:2]))
        size = d[3] << 8 | d[2]
        if size == 0:
            return []
        return d[8:8+size]

    def run_opcode(self, opcode, payload = []):
        for tries in range(4):
            try:
                self.send_tracker_packet(opcode)
                data = self.base.receive_acknowledged_reply()
            except ANTException, ae:
                print 'Failed to send Opcode %s : ' % opcode, ae
                continue
            if data[0] != self.current_packet_id:
                print "Tracker Packet IDs don't match! %02x %02x" % (data[0], self.current_packet_id)
                continue
            if data[1] == 0x42:
                return self.get_data_bank()
            if data[1] == 0x61:
                # Send payload data to device
                if len(payload) > 0:
                    self.send_tracker_payload(payload)
                    data = self.base.receive_acknowledged_reply()
                    return data[1:]
                raise SendException("run_opcode: opcode %s, no payload" % (opcode))
            if data[1] == 0x41:
                return data[1:]
        raise ANTException("Failed to run opcode %s" % (opcode))

    def send_tracker_payload(self, payload):
        # The first packet will be the packet id, the length of the
        # payload, and ends with the payload checksum
        p = [0x00, self.gen_packet_id(), 0x80, len(payload), 0x00, 0x00, 0x00, 0x00, reduce(operator.xor, payload)]
        prefix = itertools.cycle([0x20, 0x40, 0x60])
        for i in range(0, len(payload), 8):
            current_prefix = prefix.next()
            plist = []
            if i+8 >= len(payload):
                plist += [(current_prefix + 0x80) | self.base._chan]
            else:
                plist += [current_prefix | self.base._chan]
            plist += payload[i:i+8]
            while len(plist) < 9:
                plist += [0x0]
            p += plist
        # TODO: Sending burst data with a guessed sleep value, should
        # probably be based on channel timing
        self.base._send_burst_data(p, .01)

    def get_tracker_info(self):
        data = self.run_opcode([0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.parse_info_packet(data)
        return data

    def send_tracker_packet(self, packet):
        p = [self.gen_packet_id()] + packet
        self.base.send_acknowledged_data(p)

    def ping_tracker(self):
        self.base.send_acknowledged_data([0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def check_tracker_data_bank(self, index, cmd):
        self.send_tracker_packet([cmd, 0x00, 0x02, index, 0x00, 0x00, 0x00])
        return self._get_tracker_burst()

    def run_data_bank_opcode(self, index):
        return self.run_opcode([0x22, index, 0x00, 0x00, 0x00, 0x00, 0x00])

    def erase_data_bank(self, index, tstamp=None):
        if tstamp is None: tstamp = int(time.time())
        return self.run_opcode([0x25, index,
                                (tstamp & 0xff000000) >> 24,
                                (tstamp & 0x00ff0000) >> 16,
                                (tstamp & 0x0000ff00) >> 8,
                                (tstamp & 0x000000ff),
                                0x00])

    def get_data_bank(self):
        data = []
        cmd = 0x70  # Send 0x70 on first burst
        for parts in range(2000):
            bank = self.check_tracker_data_bank(self.current_bank_id, cmd)
            self.current_bank_id += 1
            cmd = 0x60  # Send 0x60 on subsequent bursts
            if len(bank) == 0:
                return data
            data = data + bank
        raise ReceiveException("Cannot complete data bank")

    def parse_bank0_data(self, data):
        # First 4 bytes are a time
        i = 0
        last_date_time = 0
        time_index = 0
        while i < len(data):
            # Date is in bigendian. No, really. And I think it's
            # because they're prefixing the 3 accelerometer reading
            # bytes with 0x80, so they can & against it.
            if not data[i] & 0x80:
                last_date_time = data[i+3] | data[i+2] << 8 | data[i+1] << 16 | data[i] << 24
                print "Time: %s" % (datetime.datetime.fromtimestamp(last_date_time))
                i = i + 4
                time_index = 0
            else:
                record_date = (datetime.datetime.fromtimestamp(last_date_time + 60 * time_index))
                # steps are easy. It's just the last byte
                steps = data[i+2]
                # active score: second byte, subtract 10 (because METs
                # start at 1 but 1 is subtracted per minute, see
                # asterisk note on fitbit website, divide by 10.
                active_score = (data[i+1] - 10) / 10.0
                # first byte: I don't know. It starts at 0x81. So we at least subtract that.
                not_sure = data[i] - 0x81
                print "%s: ???: %d Active Score: %f Steps: %d" % (record_date, not_sure, active_score, steps)
                i = i + 3
                time_index = time_index + 1

    def parse_bank1_data(self, data):
        ultra = self.hardware_version >= 12
        banklen = {12:16}.get(self.hardware_version, 14)
        for i in range(0, len(data), banklen):
            d = data[i:i+banklen]
            # First 4 bytes are seconds from Jan 1, 1970
            maybe_calories = d[5] << 8| d[4]
            daily_steps = d[9] << 24 | d[8] << 16 | d[7] << 8 | d[6]
            daily_dist = (d[13] << 24 | d[12] << 16 | d[11] << 8 | d[10]) / 1000000.
            daily_floors = 0
            if ultra:
                daily_floors = (d[15] << 8 | d[14]) / 10
            record_date = datetime.datetime.fromtimestamp(d[0] | d[1] << 8 | d[2] << 16 | d[3] << 24)
            print "Time: %s %d Daily Steps: %d, Daily distance: %fkm Daily floors: %d" % (
                record_date, maybe_calories, daily_steps, daily_dist, daily_floors)

    def parse_bank2_data(self, data):
        ultra = self.hardware_version >= 12
        banklen = {12:15}.get(self.hardware_version, 13)
        for i in range(0, len(data), banklen):
            d = data[i:i+banklen]
            # First 4 bytes are seconds from Jan 1, 1970
            print "Time: %s" % (datetime.datetime.fromtimestamp(d[0] | d[1] << 8 | d[2] << 16 | d[3] << 24))
            if d[6] == 1:
                elapsed = (d[5] << 8) | d[4]
                steps = (d[9]<< 16) | (d[8] << 8) | d[7]
                dist = (d[12] << 16) | (d[11]<< 8) | d[10]
                floors = 0
                if ultra:
                    floors = ((d[14] << 8) | d[13]) / 10
                print "Activity summary: duration: %s, %d steps, %fkm, %d floors" % (
                    datetime.timedelta(seconds=elapsed), steps, dist / 100000., floors / 10)
            else:
                print ' '.join(['%02X' % x for x in d[4:]])


    def parse_bank4_data(self, data):
        assert len(data) == 64
        print ' '.join(["0x%.02x" % x for x in data[:24]])
        print "Greeting : ", ''.join([chr(x) for x in data[24:24+8]])
        print "Chatter: ", ', '.join([''.join([chr(x) for x in data[i:i+8]]) for i in range(34, 64, 10)])

    def parse_bank6_data(self, data):
        i = 0
        tstamp = 0
        while i < len(data):
            if data[i] == 0x80:
                floors = data[i+1] / 10
                print "Time: %s: %d Floors" % (datetime.datetime.fromtimestamp(tstamp), floors)
                i += 2
                tstamp += 60
                continue
            d = data[i:i+4]
            tstamp = d[3] | d[2] << 8 | d[1] << 16 | d[0] << 24
            i += 4


    def write_settings(self, options ,greetings = "", chatter = []):
        greetings = greetings.ljust( 8, '\0')
        for i in range(max(len(chatter), 3)):
            chatter[i] = chatter[i].ljust(8, '\0')
        payload = []
        if False: # not ready yet
           self.write_bank(4, payload)

    def write_bank(self, index, data):
        self.run_opcode([0x25, index, len(data), 0,0,0,0], data)

# vim: set ts=4 sw=4 expandtab:
