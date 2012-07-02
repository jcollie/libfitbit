#!/usr/bin/env python
#################################################################
# python fitbit web client for uploading data to fitbit site
# By Kyle Machulis <kyle@nonpolynomial.com>
# http://www.nonpolynomial.com
#
# Distributed as part of the libfitbit project
#
# Repo: http://www.github.com/openyou/libfitbit
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

import time
import yaml
import sys
import urllib
import urllib2
import base64
import argparse
import xml.etree.ElementTree as et
from fitbit import FitBit, FitBitBeaconTimeout
from antprotocol.bases import FitBitANT, DynastreamANT

class FitBitRequest(object):

    def __init__(self, url):
        self.url = url

    def get_response(self, info_dict):
        data = urllib.urlencode(info_dict)
        req = urllib2.urlopen(self.url, data)
        res = req.read()
        print res
        self.init(res)

    def init(self, response):
        self.current_opcode = {}
        self.opcodes = []
        self.root = et.fromstring(response.strip())
        self.host = None
        self.path = None
        self.response = None
        if self.root.find("response") is not None:
            self.host = self.root.find("response").attrib["host"]
            self.path = self.root.find("response").attrib["path"]
            if self.root.find("response").text:
                # Quick and dirty url encode split
                self.response = dict([x.split("=") for x in urllib.unquote(self.root.find("response").text).split("&")])

        for remoteop in self.root.findall("device/remoteOps/remoteOp"):
            self.opcodes.append(RemoteOp(remoteop))

    def getNext(self):
        if self.host:
            return FitBitRequest("http://%s%s" % (self.host, self.path))
        return None

    def dump(self):
        ops = []
        for op in self.opcodes:
            ops.append(op.dump())
        return ops

    def __repr__(self):
        return "<FitBitRequest object at 0x%x opcode=%s, response=%s>" % (id(self), str(self.opcodes), str(self.response))

class RemoteOp(object):
    def __init__(self, data):
        opcode = base64.b64decode(data.find("opCode").text)
        self.opcode = [ord(x) for x in opcode]
        self.payload = None
        if data.find("payloadData").text is not None:
            payload = base64.b64decode(data.find("payloadData").text)
            self.payload = [ord(x) for x in payload]

    def run(self, fitbit):
        self.response = fitbit.run_opcode(self.opcode, self.payload)
        res = [chr(x) for x in self.response]
        return ''.join(res)

    def dump(self):
        return {'request':
                {'opcode': self.opcode,
                'payload': self.payload},
                'response': self.response}

class FitBitClient(object):
    CLIENT_UUID = "2ea32002-a079-48f4-8020-0badd22939e3"
    #FITBIT_HOST = "http://client.fitbit.com:80"
    FITBIT_HOST = "https://client.fitbit.com" # only used for initial request
    START_PATH = "/device/tracker/uploadData"
    DEBUG = True
    BASES = [FitBitANT, DynastreamANT]

    def __init__(self):
        self.info_dict = {}
        self.log_info = {}
        self.time = time.time()
        self.data = []
        self.fitbit = None
        for base in [bc(debug=self.DEBUG) for bc in self.BASES]:
            for retries in (2,1,0):
                try:
                    if base.open():
                        print "Found %s base" % (base.NAME,)
                        self.fitbit = FitBit(base)
                        break
                    else:
                        break
                except Exception, e:
                    print e
                    if retries:
                        print "retrying"
                        time.sleep(5)
            else:
                raise
            if self.fitbit:
                break
        if not self.fitbit:
            print "No devices connected!"
            exit(1)

    def __del__(self):
        self.close()
        self.fitbit = None

    def form_base_info(self, remote_info=None):
        self.info_dict.clear()
        self.info_dict["beaconType"] = "standard"
        self.info_dict["clientMode"] = "standard"
        self.info_dict["clientVersion"] = "1.0"
        self.info_dict["os"] = "libfitbit"
        self.info_dict["clientId"] = self.CLIENT_UUID
        if remote_info:
            self.info_dict = dict(self.info_dict, **remote_info)
        for f in ['deviceInfo.serialNumber','userPublicId']:
            if f in self.info_dict:
                self.log_info[f] = self.info_dict[f]

    def close(self):
        data = yaml.dump(self.data)
        f = open('connection-%d.txt' % int(self.time), 'w')
        f.write(data)
        f.close()
        try:
            print 'Closing USB device'
            self.fitbit.base.close()
            self.fitbit.base = None
        except AttributeError:
            pass

    def run_request(self, op, index):
        response = op.run(self.fitbit)
        residx = "opResponse[%d]" % index
        statusidx = "opStatus[%d]" % index
        self.info_dict[residx] = base64.b64encode(response)
        self.info_dict[statusidx] = "success"

    def run_upload_requests(self):
        self.fitbit.init_tracker_for_transfer()

        conn = FitBitRequest(self.FITBIT_HOST + self.START_PATH)

        # Start the request Chain
        self.form_base_info()
        while conn is not None:
            conn.get_response(self.info_dict)
            self.form_base_info(conn.response)
            op_index = 0
            for op in conn.opcodes:
                self.run_request(op, op_index)
                op_index += 1
            self.data.append(conn.dump())
            conn = conn.getNext()

        self.fitbit.command_sleep()

class FitBitDaemon(object):

    def __init__(self):
        self.log_info = {}
        self.log = None

    def do_sync(self):
        f = FitBitClient()
        try:
            f.run_upload_requests()
        except:
            f.close()
            raise
        self.log_info = f.log_info

    def sleep_minutes(mins):
        for m in range(mins, 0, -1):
            print time.ctime(), "waiting", m, "minutes and then restarting..."
            time.sleep(60)

    def try_sync(self):
        import traceback
        import usb
        self.log_info = {}
        try:
            self.do_sync()
        except FitBitBeaconTimeout, e:
            # This error is fairly normal, do we don't increase error counter.
            print e
        except usb.USBError, e:
            # Raise this error up the stack, since USB errors are fairly
            # critical.
            self.write_log('ERROR: ' + str(e))
            raise
        except Exception, e:
            # For other errors, log and increase error counter.
            print "Failed with", e
            print
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60
            self.write_log('ERROR: ' + str(e))
            self.errors += 1
        else:
            # Clear error counter after a successful sync.
            print "normal finish"
            self.write_log('SUCCESS')
            self.errors = 0

    def run(self, args):
        import sys, os
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        self.errors = 0
        
        while self.errors < 3:
            self.open_log()
            self.try_sync()
            self.close_log()
            if args.once:
                print "I'm done"
                return
            time.sleep(3)
        
        print 'exiting due to earlier failure'
        sys.exit(1)

    #
    # Logging functions
    #

    def open_log(self):
        self.log = open('fitbit.log', 'a')

    def write_log(self, s):
        self.log.write('[%s] [%s -> %s] %s\n' % (time.ctime(), \
                self.log_field('deviceInfo.serialNumber'), \
                self.log_field('userPublicId'), s))

    def log_field(self, f):
        return (self.log_info[f] if f in self.log_info else 'UNKNOWN')

    def close_log(self):
        if (self.log):
            self.log.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", help="Run the request only once", action="store_true")
    args = parser.parse_args()
    FitBitDaemon().run(args)

# vim: set ts=4 sw=4 expandtab:
