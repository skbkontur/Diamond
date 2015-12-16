#!/usr/bin/env python
# coding=utf-8

# This is the MIT License
# http://www.opensource.org/licenses/mit-license.php
#
# Copyright (c) 2007,2008 Nick Galbreath
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

#
# Version 1.0 - 21-Apr-2007
#   initial
# Version 2.0 - 16-Nov-2008
#   made class Gmetric thread safe
#   made gmetrix xdr writers _and readers_
#   Now this only works for gmond 2.X packets, not tested with 3.X
#
# Version 3.0 - 09-Jan-2011 Author: Vladimir Vuksan
#   Made it work with the Ganglia 3.1 data format


from xdrlib import Packer, Unpacker
import socket

slope_str2int = {'zero': 0,
                 'positive': 1,
                 'negative': 2,
                 'both': 3,
                 'unspecified': 4}

# could be autogenerated from previous but whatever
slope_int2str = {0: 'zero',
                 1: 'positive',
                 2: 'negative',
                 3: 'both',
                 4: 'unspecified'}


class Gmetric:
    """
    Class to send gmetric/gmond 2.X packets

    Thread safe
    """

    type = ('', 'string', 'uint16', 'int16', 'uint32', 'int32', 'float',
            'double', 'timestamp')
    protocol = ('udp', 'multicast')

    def __init__(self, host, port, protocol):
        if protocol not in self.protocol:
            raise ValueError("Protocol must be one of: " + str(self.protocol))

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if protocol == 'multicast':
            self.socket.setsockopt(socket.IPPROTO_IP,
                                   socket.IP_MULTICAST_TTL, 20)
        self.hostport = (host, int(port))
        # self.socket.connect(self.hostport)

    def send(self, NAME, VAL, TYPE='', UNITS='', SLOPE='both',
             TMAX=60, DMAX=0, GROUP=""):
        if SLOPE not in slope_str2int:
            raise ValueError("Slope must be one of: " + str(self.slope.keys()))
        if TYPE not in self.type:
            raise ValueError("Type must be one of: " + str(self.type))
        if len(NAME) == 0:
            raise ValueError("Name must be non-empty")

        (meta_msg, data_msg) = gmetric_write(NAME,
                                             VAL,
                                             TYPE,
                                             UNITS,
                                             SLOPE,
                                             TMAX,
                                             DMAX,
                                             GROUP)
        # print msg

        self.socket.sendto(meta_msg, self.hostport)
        self.socket.sendto(data_msg, self.hostport)


def gmetric_write(NAME, VAL, TYPE, UNITS, SLOPE, TMAX, DMAX, GROUP):
    """
    Arguments are in all upper-case to match XML
    """
    packer = Packer()
    HOSTNAME = "test"
    SPOOF = 0
    # Meta data about a metric
    packer.pack_int(128)
    packer.pack_string(HOSTNAME)
    packer.pack_string(NAME)
    packer.pack_int(SPOOF)
    packer.pack_string(TYPE)
    packer.pack_string(NAME)
    packer.pack_string(UNITS)
    packer.pack_int(slope_str2int[SLOPE])  # map slope string to int
    packer.pack_uint(int(TMAX))
    packer.pack_uint(int(DMAX))
    # Magic number. Indicates number of entries to follow. Put in 1 for GROUP
    if GROUP == "":
        packer.pack_int(0)
    else:
        packer.pack_int(1)
        packer.pack_string("GROUP")
        packer.pack_string(GROUP)

    # Actual data sent in a separate packet
    data = Packer()
    data.pack_int(128 + 5)
    data.pack_string(HOSTNAME)
    data.pack_string(NAME)
    data.pack_int(SPOOF)
    data.pack_string("%s")
    data.pack_string(str(VAL))

    return packer.get_buffer(),  data.get_buffer()


def gmetric_read(msg):
    unpacker = Unpacker(msg)
    values = dict()
    unpacker.unpack_int()
    values['TYPE'] = unpacker.unpack_string()
    values['NAME'] = unpacker.unpack_string()
    values['VAL'] = unpacker.unpack_string()
    values['UNITS'] = unpacker.unpack_string()
    values['SLOPE'] = slope_int2str[unpacker.unpack_int()]
    values['TMAX'] = unpacker.unpack_uint()
    values['DMAX'] = unpacker.unpack_uint()
    unpacker.done()
    return values


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option("", "--protocol", dest="protocol", default="udp",
                      help="The gmetric internet protocol, either udp or" +
                           "multicast, default udp")
    parser.add_option("", "--host",  dest="host",  default="127.0.0.1",
                      help="GMond aggregator hostname to send data to")
    parser.add_option("", "--port",  dest="port",  default="8649",
                      help="GMond aggregator port to send data to")
    parser.add_option("", "--name",  dest="name",  default="",
                      help="The name of the metric")
    parser.add_option("", "--value", dest="value", default="",
                      help="The value of the metric")
    parser.add_option("", "--units", dest="units", default="",
                      help="The units for the value, e.g. 'kb/sec'")
    parser.add_option("", "--slope", dest="slope", default="both",
                      help="Sign of the derivative of the value over time," +
                           "one of zero, positive, negative, both (default)")
    parser.add_option("", "--type",  dest="type",  default="",
                      help="The value data type, one of string, int8, uint8," +
                           "int16, uint16, int32, uint32, float, double")
    parser.add_option("", "--tmax",  dest="tmax",  default="60",
                      help="Maximum time in seconds between gmetric calls," +
                           "default 60")
    parser.add_option("", "--dmax",  dest="dmax",  default="0",
                      help="Lifetime in seconds of this metric, default=0," +
                           "meaning unlimited")
    parser.add_option("", "--group",  dest="group",  default="",
                      help="Group metric belongs to. If not specified Ganglia" +
                           "will show it as no_group")
    (options, args) = parser.parse_args()

    g = Gmetric(options.host, options.port, options.protocol)
    g.send(options.name, options.value, options.type, options.units,
           options.slope, options.tmax, options.dmax, options.group)
