#!/usr/bin/env python3

# Media queue daemon - A daemon that can aggregate an entire series of URLs sent to the client program over a designated timeframe, sort them as logically it can and formulate a playlist for a selected media player
#(C) 2018  Jason Barker
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

import sys
import socket
from time import time
from time import mktime
import subprocess
import re
import requests
import argparse
import threading
from datetime import date

# This script is intended to just gather links that are send to it.
# It's usefor stuff such as newsboat which doesn't collate the URLs into a long string, but rather just hammers the media player each time
#   i.e. opening 100 instances of mpv if 100 videos are selected

# Here's how it works:
# 1) Runs as a daemon
# 2) Listens for a while and collates the standard input
# 3) If no output for a few seconds, processes the data, sorts as best it can and then exports to mpv
# There is mpv_queue_client.py, which is ideal for calling to send stuff to the daemon
#  (using pipes with netcat can also work, but flaky with the launch strings in newsboat)

# ToDo
# - Investigate why some youtube videos do not seem to get a regexp match for the published date.  Perhaps they don't have the metatag?
# - Remove some of those globals

listen_ip="127.0.0.1"
listen_port=8099
wait_period = 2 # In seconds

# Initialises this variable
url_list = []

# Creates the global thread lock
lock = threading.Lock()

# Creates the parser
parser = argparse.ArgumentParser(description="A daemon that listens for incoming media URLs over a network, sorts them and sends them to a media player as a playlist.  This is useful when whatever program calls the media player is not playlist aware. \n By default this program will sort the links alphanumerically")

# Add the arguments to the parser
parser.add_argument('--disable_directory_recursion','-d',action='store_true',help="If directories are given to the daemon then it will recurse into them and find relevant media links")
parser.add_argument('--notify_on_enumerate','-n',action='store_true',help='If directories are being enumerated then send a notification of the delay')

# Create the parser
args = parser.parse_args()

def main():

    global first_run, called_mpv, url_list

    def init():
        global url_list
        s = bind_socket()
        return s

     # This calls the stuff that only needs to happen one time
    def first_run():
        s = init()


    # This function actually receives the datagrams
    def receive_datagram(s):
        data = (s.recvfrom(1024)[0]).decode().rstrip()
        datagram_time = time()
        return data, datagram_time

    # This is called when waiting for the first datagram containing a new set of URLs
    # I.e. on first run or if the daemon just finished passing to mpv
    def first_link(s):
        # First run through
        # Wait as long as needed to receive the first datagram and timestamp it
        s.settimeout(None)
        data, first_datagram_time = receive_datagram(s)

        # Append the data
        url_list.append(data)
        return first_datagram_time

    # This is called after first_link() has grabbed its link.  Timestamps are compared to figure out when
    # it's time to finish
    def subsequent_links():
        global called_mpv

        # This is used to ensure that the socket timed out and that the date comparison can be made
        # Otherwise it blocks
        s.settimeout(1)

        try:
            data, datagram_time = receive_datagram(s)
            url_list.append(data)
        except Exception as E:
            datagram_time = time()
            #print(E)

        if (datagram_time - first_datagram_time) > wait_period:
            print('Data received.  Calling mpv')
            call_mpv()
            url_list.clear()
            called_mpv = True

    # Main daemon loop
    while True:
        if first_run:
            s = init()
            first_run = False

        if len(url_list) == 0:
            print('Waiting for initial datagram')

            # Reset called_mpv to False for the new set of links
            called_mpv = False
            # Get that first datagram, add the url to the list (global) and get the timestamp
            first_datagram_time = first_link(s)
        elif len(url_list) > 0:
            print('Waiting for subsequent datagrams')
            while called_mpv == False:
                subsequent_links()

# This function is essentially the main loop for the 2nd half of this program
# It is responsible for parsing the URLs, finding out additional info as needed and then calling mpv
def call_mpv():

    global url_list, date_dict

    # Check if the target is a directory. Before doing this set a flag to false and then when the notification is called it triggers the flag and no more subsequent notifications are given
    # This prevents spamming of the notification process
    def find_media():

        global url_list, date_dict
        # Threads will be appended into this list
        threads = []

        # Grabs an appropriate link from within the folder with requests
        # Then replaces the index with the more accurate media link (i.e. rather
        # than passing the directory itself to mpv)
        def make_request_directories(i,j):
            global url_list
            p = requests.get(j)
            true_name = re.findall(r'http[s]://[\S]*.mp3|aac|mp4|flac',p.content.decode('utf-8'))[0]
            print('Got the actual name',true_name)
            try:
                lock.acquire()
                url_list[i] = true_name
            except Exception as E:
                print(E)
            finally:
                lock.release()

        # Parses youtube links to get the published dates of a series of videos
        # This is used to create a list that is sorted by upload time
        def make_request_youtube(i,j):
            global url_list, date_dict
            p = requests.get(j)
            #print('Parsing date into its individual components')

            # Regexp match the youtube date published format
            try:
                published_date = re.findall(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',p.content.decode('utf-8'))[0]
            except Exception:
                print('No published date found')

            year = published_date.split('-')[0]
            month = published_date.split('-')[1]
            day = published_date.split('-')[2]

            try:
                lock.acquire()
                #print('Inserting date object into dictionary')
                date_dict[j] = date(int(year),int(month),int(day))
            except Exception as E:
                print(E)
            finally:
                lock.release()

        def create_threads(target,i,j):
            # Create the per iteration thread
            threads.append(threading.Thread(target=target,args=(i,j)))
            # Launch the thread
            print('Starting thread')
            threads[i].start()

        # MAIN PART OF find_media()
        notified = False

        # These are used to flag which side of the sorting this is gonna be on
        youtube_mode, directory_mode = False, False
        for i,j in enumerate(url_list):

            # Processes directory links by recursing into them and finding and sorting the filenames
            if url_list[i].endswith('/') and not args.disable_directory_recursion:
                if directory_mode == False:
                    print('{0} is a directory.  Entering into it'.format(i))
                if args.notify_on_enumerate:
                    subprocess.call(['notify-send','Directories passed to the media_queue_daemon.  Standby for enumeration'])
                    notified = True
                directory_mode = True
                create_threads(make_request_directories,i,j)

            # Processes youtube links to sort them by published date
            if 'youtube.com' in url_list[i]:
                if youtube_mode == False:
                    print('{0} is youtube link. Switching to youtube mode'.format(i))
                create_threads(make_request_youtube,i,j)
                youtube_mode = True

        # Waits for all threads to finish
        for i,j in enumerate(threads):
            threads[i].join()
        print('Threads rejoined...')

        if directory_mode:
            # Sorts the url_list by alphanumerical filename
            url_list.sort()
            # And print it
            print('\nNew list: ')
            for i in date_dict.keys():
                print(i,' ',date_dict[i])

        elif youtube_mode:
            # Convert to UNIX time
            print('Converting to UNIX time')
            for i in date_dict.keys():
                date_dict[i] = mktime(date_dict[i].timetuple())

            # Clar the url list variable to take the updated sorted list
            url_list = []
            print('Sorting the dictionary chronologically')

            # Sort by time.  Remove the lowest entry from the dictionary one by one
            while len(date_dict) > 0:
                try:
                    for i in date_dict.keys():
                        lowest_val = min(date_dict.values())
                        #print('Lowest value in dictionary is ',lowest_val)
                        url_list.append(i)
                        del date_dict[i]
                        #print('Current date_dict size is',len(date_dict))
                except:
                    pass

            # Now print it
            print('\nNew list:')
            for i in url_list:
                print(i)

        else:
            url_list.reverse()

    ############################
    # MAIN PART OF CALL_MPV()
    ############################

    # This is kept global because of all the stuff going on in threads
    global url_list, date_dict

    # Later used by the youtube parser/sorted in order to sort youtube videos chronologically
    date_dict = {}

    print('\nCalling mpv on the following links:')
    for i in url_list:
        print(i)
    print('')


    # MAIN PART OF call_mpv()
    # Calls the find media function to process the url list before sending it to mpv
    find_media()

    # Send the list to mpv
    urls = " ".join(url_list)
    subprocess_string = "i3 exec \"mpv --no-terminal --title='gPodder mpv video stream' -af acompressor=threshold=-27dB:ratio=4:attack=10:release=100:makeup=4 --player-operation-mode=pseudo-gui -- " + urls + "\""
    print(subprocess_string)
    subprocess.call(subprocess_string,shell=True)


# This just binds the UDP socket
def bind_socket():
    # Create a UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((listen_ip,listen_port))
    return s


if __name__ == main():
    main()
