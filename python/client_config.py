import ConfigParser, os

class ClientConfig(object):
    """
    Example-Configuration
    
    [output]
    dump_connection = True
    write_csv = False
    """
    
    def __init__(self):        
        self.parser = ConfigParser.SafeConfigParser({'dump_connection':False, 'write_csv':False})
        config_path = os.path.expanduser('~/.fitbit/config')
        if os.path.exists(config_path):         
            self.parser.read(config_path)
    
    def dump_connection(self):
        return self.parser.getboolean('output', 'dump_connection')
    
    def write_csv(self):
        return self.parser.getboolean('output', 'write_csv')
