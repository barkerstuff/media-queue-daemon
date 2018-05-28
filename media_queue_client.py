#!/usr/bin/env python3

# Media queue daemon - A daemon that can aggregate an entire series of URLs sent to the client program over a designated timeframe, sort them as logically it can and formulate a playlist for a selected media player
# (C) 2018  Jason Barker
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# This part of the program is really just responsible for sending a TCP datagram to the media_queue_daemon

from sys import argv
from socket import socket
from socket import AF_INET
from socket import SOCK_DGRAM

target_ip="127.0.0.1"
target_port=8099

def bind_socket():
    # Create a UDP socket
    s = socket(AF_INET, SOCK_DGRAM)
    return s

def main():
    s = bind_socket()

    # Receive_datagram
    def send_datagram():
        data = s.sendto(link,((target_ip,target_port)))
        print(data)

    # Initial values
    link = argv[1].encode()
    print(link)
    send_datagram()


if __name__ == main():
    main()
