__author__    = "ktown"
__copyright__ = "Copyright Adafruit Industries 2014 (adafruit.com)"
__license__   = "MIT"
__version__   = "0.1.0"

import os
import sys
import time
import argparse
import logging

from SnifferAPI import Logger
from SnifferAPI import Sniffer
from SnifferAPI.Devices import Device
from SnifferAPI.Devices import DeviceList
from PcapPipe import PcapPipe

mySniffer = None
"""@type: SnifferAPI.Sniffer.Sniffer"""

myPipe = None
"""@type: PcapPipe.PcapPipe"""

def setup(serport, delay=6):
    """
    Tries to connect to and initialize the sniffer using the specific serial port
    @param serport: The name of the serial port to connect to ("COM14", "/dev/tty.usbmodem1412311", etc.)
    @type serport: str
    @param delay: Time to wait for the UART connection to be established (in seconds)
    @param delay: int
    """
    global mySniffer

    # Initialize the device on the specified serial port
    print "Connecting to sniffer on " + serport
    mySniffer = Sniffer.Sniffer(serport)
    # Start the sniffer
    mySniffer.start()
    # Wait a bit for the connection to initialise
    time.sleep(delay)


def scanForDevices(scantime=5):
    """
    @param scantime: The time (in seconds) to scan for BLE devices in range
    @type scantime: float
    @return: A DeviceList of any devices found during the scanning process
    @rtype: DeviceList
    """
    if args.verbose:
        print "Starting BLE device scan ({0} seconds)".format(str(scantime))

    mySniffer.scan()
    time.sleep(scantime)
    devs = mySniffer.getDevices()
    return devs


def selectDevice(devlist):
    """
    Attempts to select a specific Device from the supplied DeviceList
    @param devlist: The full DeviceList that will be used to select a target Device from
    @type devlist: DeviceList
    @return: A Device object if a selection was made, otherwise None
    @rtype: Device
    """
    count = 0

    if len(devlist):
        print "Found {0} BLE devices:\n".format(str(len(devlist)))
        # Display a list of devices, sorting them by index number
        for d in devlist.asList():
            """@type : Device"""
            count += 1
            print "  [{0}] {1} ({2}:{3}:{4}:{5}:{6}:{7}, RSSI = {8})".format(count, d.name,
                                                                             "%02X" % d.address[0],
                                                                             "%02X" % d.address[1],
                                                                             "%02X" % d.address[2],
                                                                             "%02X" % d.address[3],
                                                                             "%02X" % d.address[4],
                                                                             "%02X" % d.address[5],
                                                                             d.RSSI)
        try:
            i = int(raw_input("\nSelect a device to sniff, or '0' to scan again\n> "))
        except:
            return None

        # Select a device or scan again, depending on the input
        if (i > 0) and (i <= count):
            # Select the indicated device
            return devlist.find(i - 1)
        else:
            # This will start a new scan
            return None

def loop():
    """Main loop printing some useful statistics"""

    nLoops = 0
    nPackets = 0
    connected = False
    while myPipe.isOpen():
        time.sleep(0.1)

        packets   = mySniffer.getPackets()
        nLoops   += 1
        nPackets += len(packets)

        if connected != mySniffer.inConnection or nLoops % 20 == 0:
            connected = mySniffer.inConnection
            print "\rconnected: {}, packets: {}, missed: {}".format(mySniffer.inConnection, nPackets, mySniffer.missedPackets),
            sys.stdout.flush()

if __name__ == '__main__':
    """Main program execution point"""

    # Instantiate the command line argument parser
    argparser = argparse.ArgumentParser(description="Interacts with the Bluefruit LE Friend Sniffer firmware")

    # Add the individual arguments
    # Mandatory arguments:
    argparser.add_argument("serialport",
                           help="serial port location ('COM14', '/dev/tty.usbserial-DN009WNO', etc.)")

    # Optional arguments:
    argparser.add_argument("-v", "--verbose",
                           dest="verbose",
                           action="store_true",
                           default=False,
                           help="verbose mode")

    # Parser the arguments passed in from the command-line
    args = argparser.parse_args()

    # Try to open the serial port
    try:
        setup(args.serialport)
    except OSError:
        # pySerial returns an OSError if an invalid port is supplied
        print "Unable to open serial port '" + args.serialport + "'"
        sys.exit(-1)

    # Optionally display some information about the sniffer
    if args.verbose:
        print "Sniffer Firmware Version: " + str(mySniffer.swversion)
        # Configure log level to INFO
        logger = logging.getLogger()
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

    # Scan for devices in range until the user makes a selection
    try:
        d = None
        """@type: Device"""
        while d is None:
            print "Scanning for BLE devices (5s) ..."
            devlist = scanForDevices()
            if len(devlist):
                # Select a device
                d = selectDevice(devlist)

        # Start sniffing the selected device
        print "Attempting to follow device {0}:{1}:{2}:{3}:{4}:{5}".format("%02X" % d.address[0],
                                                                           "%02X" % d.address[1],
                                                                           "%02X" % d.address[2],
                                                                           "%02X" % d.address[3],
                                                                           "%02X" % d.address[4],
                                                                           "%02X" % d.address[5])
        # Make sure we actually followed the selected device (i.e. it's still available, etc.)
        if d is not None:
            # Create a named pipe for Wireshark capture
            pipeFilePath = os.path.join(Logger.logFilePath, "ble.pipe")
            if os.path.exists(pipeFilePath):
                os.remove(pipeFilePath)

            print "Start wireshark with -Y btle -k -i %s" % os.path.abspath(pipeFilePath)

            myPipe = PcapPipe()
            myPipe.open_and_init(pipeFilePath)

            mySniffer.follow(d)

            mySniffer.subscribe("NEW_BLE_PACKET", myPipe.newBlePacket)
        else:
            print "ERROR: Could not find the selected device"

        # Main loop
        loop();

        # Close gracefully
        mySniffer.doExit()
        myPipe.close()
        sys.exit()

    except KeyboardInterrupt:
        # Close gracefully on CTRL+C
        mySniffer.doExit()
        myPipe.close()
        sys.exit(-1)
