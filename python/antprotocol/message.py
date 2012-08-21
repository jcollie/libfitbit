import operator

UNASSIGN_CHANNEL = 0x41
ASSIGN_CHANNEL = 0x42
CHANNEL_ID = 0x51
CHANNEL_PERIOD = 0x43
SEARCH_TIMEOUT = 0x44
CHANNEL_RF_FREQ = 0x45
SET_NETWORK = 0x46
TRANSMIT_POWER = 0x47
ID_LIST_ADD = 0x59
ID_LIST_CONFIG = 0x5A
CHANNEL_TX_POWER = 0x60
LOW_PRIORITY_SEARCH_TIMEOUT = 0x63
SERIAL_NUMBER_SET_CHANNEL_ID = 0x65
ENABLE_EXT_RX_MESGS = 0x66
ENABLE_LED = 0x68
CRYSTAL_ENABLE = 0x6D
LIB_CONFIG = 0x6E
FREQUENCY_AGILITY = 0x70
PROXIMITY_SEARCH = 0x71
CHANNEL_SEARCH_PRIORITY = 0x75

STARTUP_MESSAGE = 0x6F
SERIAL_ERROR_MESSAGE = 0xAE

SYSTEM_RESET = 0x4A
OPEN_CHANNEL = 0x4B
CLOSE_CHANNEL = 0x4C
OPEN_RX_SCAN_MODE = 0x5B
REQUEST_MESSAGE = 0x4D
SLEEP_MESSAGE = 0xC5

BROADCAST_DATA = 0x4E
ACKNOWLEDGE_DATA = 0x4F
BURST_TRANSFER_DATA = 0x50

CHANNEL_RESPONSE = 0x40

RESP_CHANNEL_STATUS = 0x52
RESP_CHANNEL_ID = 0x51
RESP_ANT_VERSION = 0x3E
RESP_CAPABILITIES = 0x54
RESP_SERIAL_NUMBER = 0x61

CW_INIT = 0x53
CW_TEST = 0x48

class Message(object):
    def __init__(self):
        self.sync = 0xa4
        try:
            # for MessageOUT
            self.len = 0
            self.cs = 0
        except AttributeError:
            pass
        self.id = None
        self.data = []

    def _raw(self, CS=False):
        raw = [self.sync, self.len, self.id] + self.data
        if CS:
            raw.append(self.cs)
        return raw

    def check_CS(self):
        raw = [self.sync, self.len, self.id] + self.data
        return reduce(operator.xor, self._raw()) == self.cs

    def toBytes(self):
        return map(chr, self._raw(True))

    def __str__(self):
        return ' '.join(['%02X' % x for x in self._raw(True)])


class MessageIN(Message):
    def __init__(self, raw):
        Message.__init__(self)
        assert len(raw) >= 4
        assert raw[1] == len(raw) - 4
        self.sync = raw[0]
        self.len = raw[1]
        self.id = raw[2]
        self.data = raw[3:-1]
        self.cs = raw[-1]

    def __str__(self):
        return '<== ' + Message.__str__(self)

class MessageOUT(Message):
    def __init__(self, msgid, *data):
        Message.__init__(self)
        self.id = msgid

        for l in list(data):
            if isinstance(l, list):
                self.data += l
            else:
                self.data.append(l)


    @property
    def cs(self):
        return reduce(operator.xor, self._raw())


    @property
    def len(self):
        return len(self.data)


    def __str__(self):
        return '==> ' + Message.__str__(self)
