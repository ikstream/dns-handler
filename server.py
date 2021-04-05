#!/usr/bin/python3
"""
This python script listens on UDP port 53
for incoming DNS request and parses the questions
"""

from dnslib.server import DNSRecord
from dnslib.dns import DNSQuestion, DNSError
from dnslib.label import DNSBuffer
from dnslib.buffer import BufferError
from datetime import datetime
from time import time

import argparse
import logging as log
import os
import queue
import select
import socket
import sys
import threading
import tldextract

DOMAIN="sviks"
IP="localhost"
PORT="53"

DATA_QUEUE = queue.Queue()
USER_QUEUE = queue.Queue()

class UserData():

    def __init__(self, uid, msg_total):
        self.id = uid
        self.msg_total = msg_total
        self.data = {}
        self.msg_cnt_received = 0
        self.all_received = 0
        self.last_transmitt = 0

    def append_msg(self, msg_nr, msg_string):
        self.data[msg_nr] = msg_string


class DataProcServer(threading.Thread):
    """
    Data processing Thread
    """

    def __init__(self, group=None, target=None, name=None, args=(),
                 kwargs=None, *, daemon=None):
        super().__init__(group=group, target=target, name=name,
                         daemon=daemon)
        self.users = {}
        self._stop = threading.Event()


    def stop(self):
        """Set stop event"""
        self._stop.set()


    def stopped(self):
        """Checks if stop event is set"""
        return self._stop.isSet()


    def run(self):
        """
        Start listening and start a thread per client
        """
        allowed_time_diff = 120  # max time diff allowed in seconds

        while True:

            if self.stopped():
                return

            if not DATA_QUEUE.empty():
                data = DATA_QUEUE.get()
                uid, msg_nr, msg_total = data[-5].split('-')
                msg_string = ''.join(data[0:-5])

                if uid in self.users:
                    print(f"user {uid} exists")
                    u = self.users[uid]

                    if (int(time()) - u.last_transmitt) > allowed_time_diff:
                        u.data = {}
                else:
                    print(f"creating user {uid}")
                    u = UserData(uid, msg_total)
                    self.users[uid] = u

                print(f"last_transmitt: {u.last_transmitt}")

                if not msg_nr in u.data:
                    print(f"processing msg_nr {msg_nr}")
                    u.last_transmitt = int(time())
                    u.data[msg_nr] = msg_string

                if len(u.data.keys()) == msg_total:
                    u.last_transmitt = int(time())
                    print(f"Adding user {uid} to queue")
                    USER_QUEUE.put(u)


def parse_data(data):
    try:
        d = DNSRecord.parse(data)
    except (BufferError, DNSError) as e:
        print(f"Error occurred: {e}")
        return

    q = d.get_q()
    domain = str(q).strip(';').split()[0]
    sep_domain = domain.split('.')
    try:
        if sep_domain[-3] in 'sviks' and sep_domain[-4] in 'owrt':
            DATA_QUEUE.put(sep_domain)
            print(domain)
    except:
        return


def init_listener(server):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind the socket to the port
    server_address = (IP, int(PORT))
    print('starting up on {} port {}'.format(*server_address))
    sock.bind(server_address)
    print('\nwaiting to receive message')

    while True:
        try:
            data, address = sock.recvfrom(4096)

            print('received {} bytes from {}'.format(
                len(data), address))
            if data:
                parse_data(data)
                try:
                    sock.sendto(data, address)
                except OSError:
                    pass

            data = None
        except KeyboardInterrupt as e:
            print(f"\nCleaning up")
            sock.close()
            server.stop()
            sys.exit()


if __name__ == '__main__':
    server = DataProcServer()
    parser = argparse.ArgumentParser(description=
                                     'Collect data send over DNS')
    parser.add_argument('-i', '--ip',
                        help='Port to listen on')
    parser.add_argument('-p', '--port',
                        help='Port to listen on')
    arg = parser.parse_args()

    if arg.ip:
        IP=arg.ip
    if arg.port:
        PORT=arg.port

    server.start()
    init_listener(server)
