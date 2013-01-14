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

import os
import time
import yaml
import sys
import urllib
import urllib2
import urlparse
import base64
import argparse
import xml.etree.ElementTree as et
from fitbit import FitBit
import csv_writer
from antprotocol.connection import getConn
from antprotocol.protocol import ANT, ANTException, FitBitBeaconTimeout

class FitBitRequest(object):

    def __init__(self, host, path, https = False, response = None, opcodes = []):
        self.current_opcode = {}
        self.opcodes = opcodes
        self.response = response
        self.host = host
        self.path = path
        if https:
            scheme = 'https://'
        else:
            scheme = 'http://'
        self.url = scheme + host + path

    def upload(self, params):
        data = urllib.urlencode(params)
        req = urllib2.urlopen(self.url, data)
        self.rawresponse = req.read()

    def getNext(self):
        root = et.fromstring(self.rawresponse.strip())
        xmlresponse = root.find("response")
        if xmlresponse is None:
            print "That was it."
            return None
        
        host = xmlresponse.attrib["host"]
        path = xmlresponse.attrib["path"]
        response = xmlresponse.text
        if response:
            response = dict(urlparse.parse_qsl(response))

        opcodes = []
        for remoteop in root.findall("device/remoteOps/remoteOp"):
            opcodes.append(RemoteOp(remoteop))

        return FitBitRequest(host, path, response=response, opcodes=opcodes)

    def run_opcodes(self, fitbit):
        res = {}
        op_index = 0
        for op in self.opcodes:
            try:
                op.run(fitbit)
                res["opResponse[%d]" % op_index] = op.response
                res["opStatus[%d]" % op_index] = op.status
            except ANTException:
                print "failed running", op.dump()
                break

            op_index += 1
        return res

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
        self.status = "failed"
        self.payload = None
        self.rawresponse = []
        self.response = ''
        payload = data.find("payloadData").text
        if  payload is not None:
            payload = base64.b64decode(payload)
            self.payload = [ord(x) for x in payload]

    def run(self, fitbit):
        self.rawresponse = fitbit.run_opcode(self.opcode, self.payload)
        response = [chr(x) for x in self.rawresponse]
        self.response = base64.b64encode(''.join(response))
        self.status = "success"

    def dump(self):
        return {'request':
                {'opcode': self.opcode,
                'payload': self.payload},
                'status': self.status,
                'response': self.rawresponse}

class FitBitClient(object):
    CLIENT_UUID = "2ea32002-a079-48f4-8020-0badd22939e3"
    FITBIT_HOST = "client.fitbit.com"
    START_PATH = "/device/tracker/uploadData"

    def __init__(self, debug=False):
        self.info_dict = {}
        self.log_info = {}
        self.time = time.time()
        self.data = []
        conn = getConn()
        if conn is None:
            print "No base found!"
            exit(1)
        base = ANT(conn)
        self.fitbit = FitBit(base)
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
            self.info_dict.update(remote_info)
        for f in ['deviceInfo.serialNumber','userPublicId']:
            if f in self.info_dict:
                self.log_info[f] = self.info_dict[f]
               

    def dump_connection(self, directory='~/.fitbit'):
        directory = os.path.expanduser(directory)
        output_file = os.path.join(directory,'connection-%d.txt' % int(self.time))
        data = yaml.dump(self.data)
        if 'userPublicId' in self.log_info:            
            if not os.path.isdir(directory):
                os.makedirs(directory)
            f = open(output_file, 'w')
            f.write(data)
            f.close()
        print data
        return output_file
    
    def write_csv(self):
        import traceback
        try:
            if 'userPublicId' in self.log_info:
                csv_writer.write_csv( csv_writer.convert_for_csv(self.data), self.log_info['userPublicId'] )
        except Exception:
            print "Could not write csv files."
            traceback.print_exc(file=sys.stdout)

    def close(self):
        self.dump_connection()
        self.write_csv()
            
        print 'Closing USB device'
        try:
            self.fitbit.base.connection.close()
        except AttributeError:
            pass
        self.fitbit.base = None

    def run_upload_requests(self):
        self.fitbit.init_tracker_for_transfer()

        conn = FitBitRequest(self.FITBIT_HOST, self.START_PATH, https=True)

        # Start the request Chain
        self.form_base_info()
        while conn is not None:
            self.form_base_info(conn.response)

            self.info_dict.update(conn.run_opcodes(self.fitbit))

            conn.upload(self.info_dict)

            self.data.append(conn.dump())
            conn = conn.getNext()

        self.fitbit.command_sleep()

class FitBitDaemon(object):

    def __init__(self, debug):
        self.log_info = {}
        self.log = None
        self.debug = debug

    def do_sync(self):
        f = FitBitClient(self.debug)
        try:
            f.run_upload_requests()
        except:
            f.close()
            raise
        f.close()
        self.log_info = f.log_info

    def try_sync(self):
        import traceback
        import usb
        self.log_info = {}
        try:
            self.do_sync()
        except FitBitBeaconTimeout, e:
            # This error is fairly normal, so we don't increase error counter.
            print e
        except ANTException, e:
            # For ANT errors, log and increase error counter.
            print "Failed with", e
            print
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60
            self.write_log('ERROR: ' + str(e))
            self.errors += 1
        except usb.USBError, e:
            # Raise this error up the stack, since USB errors are fairly
            # critical.
            self.write_log('ERROR: ' + str(e))
            raise
        else:
            # Clear error counter after a successful sync.
            print "normal finish"
            self.write_log('SUCCESS')
            self.errors = 0

    def run(self, args):
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
    parser.add_argument("--debug", help="Display debug information", action="store_true")
    args = parser.parse_args()
    FitBitDaemon(args.debug).run(args)

# vim: set ts=4 sw=4 expandtab:
