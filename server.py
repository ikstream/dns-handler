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

class Server():
    """
    Threaded UDP Server
    """

    def __init__(self):
        self.udp_port = 53
        self.udp_host = ''


    def start_server(self, config):
        """
        Start listening and start a thread per client
        """
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error as msg:
            log.error(f"Failed to create socket. Error Code: {str(msg.errno)}: "
                      f"{msg.strerror}")

        try:
            udp_sock.bind((self.udp_host, self.udp_port))
        except socket.error as msg:
            log.error(f"Bind failed. Error: {str(msg.errno)}: {msg.strerror}")
            sys.exit()

        log.info('Server listening')
#        tcp_thread = TcpThread(args={"host": self.tcp_host,
#                                     "port": self.tcp_port,
#                                     "udp_config": config})
#        tcp_thread.start()

        while True:
            udp_data = udp_sock.recvfrom(4096)[0]
            config.add_data(mac, data)

            # check if there is a thread for this client
            if not config.get_thread(mac):
                thread = ReceiverThread(args={'address': mac},
                                        kwargs={'config': config,
                                                'mqtt_client': mqtt_client}
                                        )
                thread.start()
                config.append_thread(mac, thread)
                try:
                    mqtt.send_message(mqtt_client, topic,
                                      f"New Client: {config.client_ids[mac]}/"
                                      f"{mac}")
                except KeyError as e_k:
                    log.warning(f"Client {mac} not configured. Can't notify via"
                                f" MQTT")

                log.info(f"started Thread: {thread}")
                log.info(f"current topic {topic}")

        udp_sock.close()


def parse_data(data):
    try:
        d = DNSRecord.parse(data)
    except (BufferError, DNSError) as e:
        print(f"Error occurred: {e}")
        return

    q = d.get_q()
    domain = str(q).strip(';').split()[0]
    print(domain)


# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the port
server_address = ('192.168.2.110', 10000)
print('starting up on {} port {}'.format(*server_address))
sock.bind(server_address)
print('\nwaiting to receive message')

while True:
    data, address = sock.recvfrom(4096)

    print('received {} bytes from {}'.format(
        len(data), address))
    if data:
        parse_data(data)
        sock.sendto(data, address)

    data = None


if __name__ == '__main__':
    thread_config = ReceiverThreadConfig()
    server = Server()
