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

import argparse
import logging as log
import os
import queue
import select
import socket
import sys
import threading
import time
import tldextract

DOMAIN="sviks"
IP="localhost"
PORT="53"

DATA_QUEUE = queue.Queue()
USER_QUEUE = queue.Queue()

class ReceiverThreadConfig():
    """
    Config for ReceiverThread class
    """
    def __init__(self):
        self.global_client_queue = {}
        self.global_threads = {}
        self.server_id = ''
        self.client_ids = {}


    def append_thread(self, addr, client_thread):
        """
        Append client thread to queue
        """
        self.global_threads[addr] = client_thread


    def get_thread(self, addr):
        """
        Check if thread already exists for client (addr)
        """
        try:
            return self.global_threads[addr]
        except KeyError as e_k:
            return None


    def remove_thread(self, addr):
        """
        Remove client thread
        """
        try:
            del self.global_threads[addr]
        except KeyError as e_k:
            log.warning(f"Could not remove thread for {addr}: {e_k}")


    def add_data(self, mac_addr, data):
        """
        Add data for client to process
        """
        try:
            self.global_client_queue[mac_addr].put(data)
        except KeyError as e_k:
            self.global_client_queue[mac_addr] = queue.Queue()
            log.info(f"Creating Queue for {mac_addr}: {e_k}")
        except queue.Full as e_full:
            log.error(f"Could not add data for client {mac_addr}: {e_full}")


    def get_data(self, addr):
        """
        Get data from client queue
        """
        try:
            data = self.global_client_queue[addr].get()
        except KeyError as e_k:
            log.warning(f"No queue for {addr} available: {e_k}")
            return None
        except queue.Empty as e_e:
            log.error(f"Queue for {addr} is empty {e_e}")
            return None

        try:
            self.global_client_queue[addr].task_done()
        except ValueError as e_v:
            log.warning(f"Queue contains no task to finish: {e_v}")

        return data


    def has_no_data(self, addr):
        """
        Check if queue is empty
        """
        return self.global_client_queue[addr].empty()


class ReceiverThread(threading.Thread):
    """
    Thread for receiving audio data per client
    """

    def __init__(self, group=None, target=None, name=None, args=(),
                 kwargs=None, *, daemon=None):
        super().__init__(group=group, target=target, name=name,
                         daemon=daemon)
        self.address = args['address']
        self.config = kwargs['config']
        self.mqtt_cli = kwargs['mqtt_client']


    def run(self):
        self.receiver_thread(self.address)


    def retreive_data(self, address: tuple):
        """
        retreive data from client queue

        Arguments:
            address: client tuple of ip and port

        Returns:
            udp_data: client queue data, None on failure
        """
        udp_data = self.config.get_data(address)
        return udp_data


    def receiver_thread(self, mac: str):
        """
        Thread per client to receive and store UPD data

        Arguments:
            mac (string): MAC address of client
        """
        count = 0
        empty_count = 0
        storage_path = self._create_path(mac)
        storage_hour = 35
        topic = 'anomaly_detection/' + self.config.server_id

        if not storage_path:
            log.error(f" Storage path creation failed aborting for {mac}")
            del self.config.global_threads[mac]
            return

        log.info(f"Started receiver_thread for {mac}")

        while True:
            # check if data is in queue for client
            if self.config.has_no_data(mac):
                time.sleep(0.1)
                empty_count += 1

                if empty_count == 30:
                    log.info(f"Queue for {mac} has been empty for 3 seconds")
                    log.warning(f"Closing {wav_file_name} due to inactivity")
                    self.close_file(wav_file, wav_file_name)
                    self.config.remove_thread(mac)
                    empty_count = 0
                    log.info(f"removed {mac} from thread queue")
                    mqtt.send_message(self.mqtt_cli, topic,
                                      f"Removed client: {mac}")
                    return
                else:
                    continue


            udp_data = self.retreive_data(mac)
            if mac == self.config.live_host:
                self.config.live_queue.put(udp_data)

            if not udp_data:
                log.warning("No data received")
                continue

            empty_count = 0
            wav_file.writeframesraw(udp_data)
            count += self.config.step_size

            if count == self.config.sample_rate * self.config.duration:
                count = 0
                self.close_file(wav_file, wav_file_name)
                mqtt.send_message(self.mqtt_cli, topic,
                                  f"File written: {mac}: {wav_file_name}")

class user_data():

    def __init__(self, uid, msg_total):
        self.id = uid
        self.msg_total = msg_total
        self.data = {}

    def append_msg(self, msg_nr, msg_string):
        self.data[msg_nr] = msg_string


class data_proc():
    """
    Data processing Thread
    """

    def __init__(self):
        self.users = []


    def start_server(self):
        """
        Start listening and start a thread per client
        """
        while True:
            if not DATA_QUEUE.empty():
                data = DATA_QUEUE.get()
                uid, msg_nr, msg_total = data[-5].split('-')
                msg_string = ''.join(data[1:-5])

                if not self.users


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


def init_listener():
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
            exit()



if __name__ == '__main__':
    server = Server()
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

    server.start_server()
    init_listener()
