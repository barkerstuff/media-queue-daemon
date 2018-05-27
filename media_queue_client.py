#!/usr/bin/env python3

# This script is really just responsible for sending a TCP datagram to the media_queue_daemon

import sys
import socket

target_ip="127.0.0.1"
target_port=8099

def bind_socket():
    # Create a UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return s

def main():
    s = bind_socket()

    # Receive_datagram
    def send_datagram():
        data = s.sendto(link,((target_ip,target_port)))
        print(data)

    # Initial values
    link = sys.argv[1].encode()
    print(link)
    send_datagram()


if __name__ == main():
    main()
