#################################################################
# ant message protocol
# By Kyle Machulis <kyle@nonpolynomial.com>
# http://www.nonpolynomial.com
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
# Added to and untwistedized and fixed up by Kyle Machulis <kyle@nonpolynomial.com>
#

import operator, struct, array, time
from message import MessageIN, MessageOUT

class ANTException(Exception):
    """ Our Base Exception class """

class ReceiveException(ANTException): pass

class StatusException(ReceiveException): pass

class NoMessageException(ReceiveException): pass

class SendException(ANTException): pass

def hexList(data):
    return map(lambda s: chr(s).encode('HEX'), data)

def hexRepr(data):
    return ' '.join(hexList(data)).upper()

def intListToByteList(data):
    return map(lambda i: struct.pack('!H', i)[1], array.array('B', data))

def log(f):
    def wrapper(self, *args, **kwargs):
        if self._debug:
            print '  '*self._loglevel, "Start", f.__name__, args, kwargs
        self._loglevel += 1
        try:
            res = f(self, *args, **kwargs)
        except:
            if self._debug:
                print '  '*self._loglevel, "Fail", f.__name__
            raise
        finally:
            self._loglevel -= 1
        if self._debug:
            print '  '*self._loglevel, "End", f.__name__, res
        return res
    return wrapper

class ANT(object):

    def __init__(self, chan=0x00, debug=False):
        self._debug = debug
        self._chan = chan

        self._state = 0
        self._receiveBuffer = []
        self._loglevel = 0

    def _event_to_string(self, event):
        return { 0:"RESPONSE_NO_ERROR",
                 1:"EVENT_RX_SEARCH_TIMEOUT",
                 2:"EVENT_RX_FAIL",
                 3:"EVENT_TX",
                 4:"EVENT_TRANSFER_RX_FAILED",
                 5:"EVENT_TRANSFER_TX_COMPLETED",
                 6:"EVENT_TRANSFER_TX_FAILED",
                 7:"EVENT_CHANNEL_CLOSED",
                 8:"EVENT_RX_FAIL_GO_TO_SEARCH",
                 9:"EVENT_CHANNEL_COLLISION",
                 10:"EVENT_TRANSFER_TX_START",
                 21:"CHANNEL_IN_WRONG_STATE",
                 22:"CHANNEL_NOT_OPENED",
                 24:"CHANNEL_ID_NOT_SET",
                 25:"CLOSE_ALL_CHANNELS",
                 31:"TRANSFER_IN_PROGRESS",
                 32:"TRANSFER_SEQUENCE_NUMBER_ERROR",
                 33:"TRANSFER_IN_ERROR",
                 40:"INVALID_MESSAGE",
                 41:"INVALID_NETWORK_NUMBER",
                 48:"INVALID_LIST_ID",
                 49:"INVALID_SCAN_TX_CHANNEL",
                 51:"INVALID_PARAMETER_PROVIDED",
                 53:"EVENT_QUE_OVERFLOW",
                 64:"NVM_FULL_ERROR",
                 65:"NVM_WRITE_ERROR",
                 66:"ASSIGN_CHANNEL_ID",
                 81:"SET_CHANNEL_ID",
                 0x4b:"OPEN_CHANNEL"}.get(event, "%02x" % event)

    def _check_reset_response(self, status):
        for tries in range(8):
            try:
                msg = self._receive_message()
            except ReceiveException:
                continue
            if msg.id == 0x6f and msg.data[0] == status:
                return
        raise StatusException("Failed to detect reset response")

    def _check_ok_response(self, msgid):
        # response packets will always be 7 bytes
        msg = self._receive_message()

        if msg.id == 0x40 and msg.data[1:3] == [msgid, 0x00]:
            return

        raise StatusException("Message status %d does not match 0x0 (NO_ERROR)" % (msg.data[2]))

    @log
    def reset(self):
        self._send_message(0x4a, 0x00)
        # According to protocol docs, the system will take a maximum
        # of .5 seconds to restart
        #
        # sleep time was 0.6, changed to 1.0 which reduces fail rate; a retry might
        # be more sensible but wasn't sure if that might lead to possible duplicate 
        # acknowledgements in the receive queue. A setting of 2.0 caused the interface 
        # to not read fitbit devices. - Reed 31 Dec 2011
        #
        time.sleep(1.0)
        #
        # This is a requested reset, so we expect back 0x20
        # (COMMAND_RESET)
        self._check_reset_response(0x20)

    @log
    def set_channel_frequency(self, freq):
        self._send_message(0x45, self._chan, freq)
        self._check_ok_response(0x45)

    @log
    def set_transmit_power(self, power):
        self._send_message(0x47, 0x0, power)
        self._check_ok_response(0x47)

    @log
    def set_search_timeout(self, timeout):
        self._send_message(0x44, self._chan, timeout)
        self._check_ok_response(0x44)

    @log
    def send_network_key(self, network, key):
        self._send_message(0x46, network, key)
        self._check_ok_response(0x46)

    @log
    def set_channel_period(self, period):
        self._send_message(0x43, self._chan, period)
        self._check_ok_response(0x43)

    @log
    def set_channel_id(self, id):
        self._send_message(0x51, self._chan, id)
        self._check_ok_response(0x51)

    @log
    def open_channel(self):
        self._send_message(0x4b, self._chan)
        self._check_ok_response(0x4b)

    @log
    def close_channel(self):
        self._send_message(0x4c, self._chan)
        self._check_ok_response(0x4c)

    @log
    def assign_channel(self):
        self._send_message(0x42, self._chan, 0x00, 0x00)
        self._check_ok_response(0x42)

    @log
    def receive_acknowledged_reply(self, size = 13):
        for tries in range(30):
            msg = self._receive_message(size)
            if msg.len > 0 and msg.id == 0x4F:
                return msg.data[1:]
        raise ReceiveException("Failed to receive acknowledged reply")

    @log
    def _check_tx_response(self, maxtries = 16):
        for msgs in range(maxtries):
            msg = self._receive_message()
            if msg.len > 1 and msg.id == 0x40:
                if msg.data[2] == 0x0a: # TX Start
                    continue
                if msg.data[2] == 0x05: # TX successful
                    return
                if msg.data[2] == 0x06: # TX failed
                    raise ReceiveException("Transmission Failed")
        raise ReceiveException("No Transmission Ack Seen")

    @log
    def _send_burst_data(self, data, sleep = None):
        for tries in range(2):
            for l in range(0, len(data), 9):            
                self._send_message(0x50, data[l:l+9])
                # TODO: Should probably base this on channel timing
                if sleep != None:
                    time.sleep(sleep)
            try:
                self._check_tx_response()
            except ReceiveException:
                continue
            return
        raise ReceiveException("Failed to send burst data")

    @log
    def _check_burst_response(self):
        response = []
        for tries in range(128):
            msg = self._receive_message()
            if msg.len > 1 and msg.id == 0x40 and msg.data[2] == 0x4:
                raise ReceiveException("Burst receive failed by event!")
            elif msg.len > 0 and msg.id == 0x4f:
                response = response + msg.data[1:]
                return response
            elif msg.len > 0 and msg.id == 0x50:
                response = response + msg.data[1:]
                if msg.data[0] & 0x80:
                    return response
        raise ReceiveException("Burst receive failed to detect end")

    @log
    def send_acknowledged_data(self, l):
        for tries in range(8):
            try:
                self._send_message(0x4f, self._chan, l)
                self._check_tx_response()
            except ReceiveException:
                continue
            return
        raise ReceiveException("Failed to send Acknowledged Data")

    def send_str(self, instring):
        if len(instring) > 8:
            raise "string is too big"

        return self._send_message(0x4e, list(struct.unpack('%sB' % len(instring), instring)))

    def _send_message(self, msgid, *args):
        msg = MessageOUT(msgid, *args)
        if self._debug:
            print '  '*self._loglevel, msg
        return self._send(msg.toBytes())

    def _find_sync(self, buf, start=0):
        i = 0;
        for v in buf:
            if i >= start and (v == 0xa4 or v == 0xa5):
                break
            i = i + 1
        if i != 0:
            if self._debug:
                print "Searching for SYNC, discarding: " + hexRepr(buf[0:i])
            del buf[0:i]
        return buf

    def _receive_message(self, size = 4096):
        timeouts = 0
        data = self._receiveBuffer
        l = 4 # Minimum packet size (SYNC, LEN, CMD, CKSM)
        while True:
            if len(data) < l:
                # data[] too small, try to read some more
                from usb.core import USBError
                try:
                    data += self._receive(size).tolist()
                    timeouts = 0
                except USBError:
                    timeouts = timeouts+1
                    if timeouts > 3:
                        # It looks like there isn't anything else coming.  Try
                        # to find a plausable packet..
                        data = self._find_sync(data)
                        while len(data) > 1 and len(data) < data[1]+4:
                            data = self._find_sync(data, 2)
                        if len(data) == 0:
                            # Failed to find anything..
                            self._receiveBuffer = []
                            raise NoMessageException()
                continue
            data = self._find_sync(data)
            if len(data) < l: continue
            if data[1] < 0 or data[1] > 32:
                # Length doesn't look "reasonable"
                data = self._find_sync(data, 1)
                continue
            l = data[1] + 4
            if len(data) < l:
                continue
            msg = MessageIN(data[:l])
            if not msg.check_CS():
                if self._debug:
                    print "Checksum error for proposed packet: " + hexRepr(p)
                data = self._find_sync(data, 1)
                continue
            self._receiveBuffer = data[l:]
            if self._debug:
                print '  '*self._loglevel, msg
            return msg

    def _receive(self, size=4096):
        raise NotImplementedError("Need to define _receive function for ANT child class!")

    def _send(self):
        raise NotImplementedError("Need to define _send function for ANT child class!")

