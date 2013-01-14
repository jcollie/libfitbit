#################################################################
# csv writer
# export the fitbit data into csv files under ~/.fitbit/id/csv
# so they can be read by other software packages (e.g. gnuplot)
#
#
# Distributed as part of the libfitbit project
#
# Repo: https://github.com/benallard/libfitbit
#
# Licensed under the BSD License, as follows
#
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

import os, csv, yaml, datetime, itertools

ENABLE_LOGGING = True

def _log(msg):
    if ENABLE_LOGGING:
        print "csv_writer: " + str(msg)

def _read_yaml(yaml_file_path):
    f = open(yaml_file_path)
    raw_data = f.read()
    f.close()
    result = yaml.load(raw_data)
    return result

def _get_flat_req_resp_list(data):
    if (len(data)>1):
        result = []
        for outer_list in data:
            for inner_list in outer_list:
                for req_resp in inner_list:
                    if "request" in req_resp:
                        result.append(inner_list)
                    
        return result
    else:
        raise Exception("data does not have the expected format")

def _filter_by_opcodes(req_resp_list, filter_function):
    """
    filter_function receives the opcodes as first and only parameter and returns a boolean
    returns a list with all requests where filter_function returns true
    """
    result = []
    for reqresp in req_resp_list:
        req = reqresp["request"]
        opcode = req['opcode']
        include = filter_function(opcode)
        if (include):
            result.append(reqresp)
            
    return result

def _p_0(data):
    i = 0
    tstamp = 0
    result = []
    while i < len(data):
        if (data[i] & 0x80) == 0x80:
            d = data[i:i+3]
            d0 = d[0] - 0x80 # ???
            d1 = (d[1] - 10) / 10. # score
            d2 = d[2] # steps
            row = {'timestamp':tstamp, 'datetime':datetime.datetime.fromtimestamp(tstamp), '?':d0, 'score':d1, 'steps':d2}
            _log(row)
            result.append(row)
            i += 3
            tstamp += 60
            continue
        d = data[i:i+4]
        tstamp = d[3] | d[2] << 8 | d[1] << 16 | d[0] << 24
        if i != 0: _log('---xx--xx--xx--xx')
        i += 4
    return result

def _p_1(data):
    assert len(data) % 16 == 0
    result = []
    for i in xrange(0, len(data), 16):
        d = data[i:i+16]
        tstamp = d[0] | d[1] << 8 | d[2] << 16 | d[3] << 24
        #if date in seen: continue
        #seen.add(date)
        date = datetime.datetime.fromtimestamp(tstamp)
        if date.minute == 0 and date.hour == 0 and date.second == 0:
            #print a2s(d[4:])
            daily_steps = d[7] << 8 | d[6]
            daily_dist = (d[11] << 8 | d[10] | d[13] << 24 | d[12] << 16) / 1000000.
            daily_floors = (d[15] << 8 | d[14]) / 10
            daily_cals = (d[5] << 8 | d[4]) *.1103 - 7
            row = {'timestamp':tstamp, 'datetime':date, 'steps': daily_steps, 'distance': daily_dist,'floors':daily_floors, 'calories':daily_cals}
            _log(row)
            result.append(row)
            
    return result

def _p_6(data):
    result = []
    i = 0
    tstamp = 0
    while i < len(data):
        if data[i] == 0x80:
            floors = data[i+1] / 10
            row = {'timestamp':tstamp, 'datetime':datetime.datetime.fromtimestamp(tstamp), 'floors':floors}
            _log(row)
            result.append(row)
            i += 2
            tstamp += 60
            continue
        
        d = data[i:i+4]
        tstamp = d[3] | d[2] << 8 | d[1] << 16 | d[0] << 24
        i += 4
    return result

def convert_for_csv(data):
    """
    returns a dict with 'minute_activity'-, 'daily_stats' and 'minute_floors'-data  
    """
    result = {}
    request_response_list = _get_flat_req_resp_list(data)
    p0 = _filter_by_opcodes(request_response_list, lambda opcode: (opcode[0] == 0x22 and opcode[1] == 0x00) )
    minute_activity = map( _p_0, ( map(lambda e: e['response'], p0) ) ) 
    _log( minute_activity )
    
    p1 = _filter_by_opcodes(request_response_list, lambda opcode: (opcode[0] == 0x22 and opcode[1] == 0x01))
    daily_stats = map( _p_1, ( map(lambda e: e['response'], p1) ) )
    _log( daily_stats )
    
    p6 = _filter_by_opcodes(request_response_list, lambda opcode: (opcode[0] == 0x22 and opcode[1] == 0x06))
    minute_floors = map( _p_6, ( map(lambda e: e['response'], p6) ) )
    _log( minute_activity )
    
    result['minute_activity'] = list(itertools.chain.from_iterable(minute_activity))
    result['daily_stats'] = list(itertools.chain.from_iterable(daily_stats))
    result['minute_floors'] = list(itertools.chain.from_iterable(minute_floors)) 
    
    return result

def _write_csv_file(directory, filename, header, rows):
    """
    uses a csv.DictWriter to write the rows (list of dicts) into a csv-file (in the order given in header)
    """
    csv_file_path = os.path.join(directory, filename)
    is_new_csv = (not os.path.exists(csv_file_path)) 
    if is_new_csv:
        f = open(csv_file_path, 'wb')
    else:
        f = open(csv_file_path, 'ab')
        
    writer = csv.DictWriter(f, header, delimiter=';')
    if is_new_csv:
        writer.writeheader()
        
    writer.writerows(rows)
    f.close()

def write_csv(converted_data, tracker_id, directory='~/.fitbit'):
    directory = os.path.expanduser(directory)
    directory = os.path.join(directory, tracker_id)
    directory = os.path.join(directory, 'csv')
    if not os.path.isdir(directory):
        os.makedirs(directory)
        
    _write_csv_file(directory, "minute_activity.csv", 
                                 ['timestamp', 'datetime', '?', 'score', 'steps'], converted_data['minute_activity'])
    
    _write_csv_file(directory, "minute_floors.csv", 
               ['timestamp', 'datetime', 'floors'], converted_data['minute_floors'])
    _write_csv_file(directory, "daily_stats.csv",   
               ['timestamp', 'datetime', 'steps', 'distance', 'floors', 'calories'], converted_data['daily_stats'] )

def convert_dump_to_csv(yaml_file_path, tracker_id, directory='~/.fitbit'):
    data = _read_yaml(yaml_file_path)
    converted = convert_for_csv(data)
    write_csv(converted, tracker_id)

    
def main():
    """
    Finds the most recent connection-dump and tries to convert it + write CSV
    Used for testing 
    """
    directory = os.path.expanduser('~/.fitbit') 
    dirlist = filter(lambda name: os.path.isdir( os.path.join(directory, name) ), os.listdir(directory))
    
    if (len(dirlist) == 0):
        _log("No Tracker-Directory found. Aborting.")
    
    
    tracker_id = dirlist[0] #use first tracker
        
    directory = os.path.join(directory, tracker_id) #use first tracker
    
    
    most_recent = None
    most_recent_time = 0.0
    for fname in os.listdir(directory):
        if 'connection-' in fname:
            full_path = os.path.join(directory, fname)
            time =  os.path.getctime(full_path)
            if (time > most_recent_time):
                most_recent = full_path                
                most_recent_time = time

    if most_recent:
        convert_dump_to_csv(most_recent, tracker_id)
    else:
        _log("Found no connection dump. Aborting.")
        
    _log("done")            
    
if __name__ == "__main__":
    main()