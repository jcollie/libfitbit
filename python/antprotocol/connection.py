import usb, os, sys

class ANTConnection(object):
    """ An abstract class that represents a connection """

    def open(self):
        """ Open the connection """
        raise NotImplementedError()

    def close(self):
        """ Close the connection """
        raise NotImplementedError()

    def send(self, bytes):
        """ Send some bytes away """
        raise NotImplementedError()

    def receive(self, amount):
        """ Get some bytes """
        raise NotImplementedError()

class ANTUSBConnection(ANTConnection):
    ep = {
        'in'  : 0x81,
        'out' : 0x01
    }

    def __init__(self):
        self._connection = False
        self.timeout = 1000

    def open(self):
        self._connection = usb.core.find(idVendor = self.VID,
                                         idProduct = self.PID)
        if self._connection is None:
            return False

        # For some reason, we have to set config, THEN reset,
        # otherwise we segfault back in the ctypes (on linux, at
        # least).
        self._connection.set_configuration()
        self._connection.reset()
        # The we have to set our configuration again
        self._connection.set_configuration()

        # Then we should get back a reset check, with 0x80
        # (SUSPEND_RESET) as our status
        #
        # I've commented this out because -- though it should just work
        # it does seem to be causing some odd problems for me and does
        # work with out it. Reed Wade - 31 Dec 2011
        ##self._check_reset_response(0x80)
        return True

    def close(self):
        if self._connection is not None:
            self._connection = None

    def send(self, command):
        # libusb expects ordinals, it'll redo the conversion itself.
        c = command
        self._connection.write(self.ep['out'], map(ord, c), 0, 100)

    def receive(self, amount):
        return self._connection.read(self.ep['in'], amount, 0, self.timeout)

class DynastreamANT(ANTUSBConnection):
    """Class that represents the Dynastream USB stick base, for
    garmin/suunto equipment. Only needs to set VID/PID.

    """
    VID = 0x0fcf
    PID = 0x1008
    NAME = "Dynastream"

class FitBitANT(ANTUSBConnection):
    """Class that represents the fitbit base. Due to the extra
    hardware to handle tracker connection and charging, has an extra
    initialization sequence.

    """

    VID = 0x10c4
    PID = 0x84c4
    NAME = "FitBit"

    def open(self):
        if not super(FitBitANT, self).open():
            return False
        self.init()
        return True

    def init(self):
        # Device setup
        # bmRequestType, bmRequest, wValue, wIndex, data
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        # At this point, we get a 4096 buffer, then start all over
        # again? Apparently doesn't require an explicit receive
        self._connection.ctrl_transfer(0x40, 0x00, 0x0, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x4A, 0x0, [])
        # Receive 1 byte, should be 0x2
        self._connection.ctrl_transfer(0xC0, 0xFF, 0x370B, 0x0, 1)
        self._connection.ctrl_transfer(0x40, 0x03, 0x800, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x13, 0x0, 0x0, \
                                       [0x08, 0x00, 0x00, 0x00,
                                        0x40, 0x00, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00
                                        ])
        self._connection.ctrl_transfer(0x40, 0x12, 0x0C, 0x0, [])
        try:
            self.receive(1024)
        except usb.USBError:
            pass

CONNS = [FitBitANT, DynastreamANT]


def getConn():
    for conn in [bc() for bc in CONNS]:
        if conn.open():
            os.write(sys.stdout.fileno(), "\n%s: " % conn.NAME)
            return conn
    print "Failed to find a base"
    return None
