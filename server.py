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
from subprocess import check_output

import argparse
import base64
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

class UserHandlerException(Exception):
    """
    Exception, that is thrown, if something fails during User data processing
    to enforce a graceful handling

    Attributes:
        message: message that is provided on error
    """

    def __init__(self, message=""):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Something went wrong in UserDataHandler: {self.message}'



class UserData():

    def __init__(self, uid, msg_total):
        self.id = uid
        self.msg_total = msg_total
        self.data = {}
        self.last_transmitt = 0


class UserProcServer(threading.Thread):
    """
    User processing thread
    """

    def __init__(self, group=None, target=None, name=None, args=(),
                 kwargs=None, *, daemon=None):
        super().__init__(group=group, target=target, name=name,
                         daemon=daemon)
        self.keyfile = args['key']
        self._stop = threading.Event()


    def stop(self):
        """Set stop event"""
        self._stop.set()


    def stopped(self):
        """Checks if stop event is set"""
        return self._stop.isSet()


    def run(self):
        """Process user data if available"""

        tmp_crypt_file='/tmp/crypt.data'
        rm_table = {34: ''} # 34 -> '"' for removal from final string

        while True:

            if self.stopped():
                return

            if not USER_QUEUE.empty():
                try:
                    user = USER_QUEUE.get(timeout=0.01)
                except:
                    continue

                try:
                    uid = user.id
                    data = user.data
                    msg_total = user.msg_total
                    encoded_msg = ''

                    for i in range(1, int(msg_total) + 1):
                        encoded_msg = encoded_msg + data[str(i)]

                    try:
                        b64_msg = bytes.fromhex(encoded_msg.strip()).decode('ascii')
                    except ValueError as ve:
                        print(f"Value Error occured on transmitted data: {ve}")
                        raise UserHandlerException("Could not decode msg from Hex")

                    try:
                        decoded_bytes = base64.b64decode(b64_msg)
                    except Exception as e:
                        print(f"Something went wrong decoding raw message: {e}\n"
                              f"Message was: {raw_msg}")
                        raise UserHandlerException("Could not decode Base64")

                    try:
                        with open(tmp_crypt_file, 'wb') as f:
                            f.write(decoded_bytes)
                    except Exception as e:
                        print(f"Error occured while writing crypt data to"
                              f"{tmp_crypt_file}: {e}")
                        raise UserHandlerException("Could not open temporary file")

                    try:
                        decrypted = check_output(['openssl', 'rsautl', '-decrypt', '-inkey',
                                                  self.keyfile, '-in', '/tmp/crypt.data']
                                                ).decode('utf-8').strip().translate(rm_table)
                    except Exception as e:
                        print(f"Error occured, while decrypt")
                        raise UserHandlerException("Could not Decrypt msg with openssl")

                    print(f"clear text: {decrypted}")
                    try:
                        os.remove(tmp_crypt_file)
                    except Exception as e:
                        print(f"Couldn't delete {tmp_crypt_file}: {e}")
                        raise UserHandlerException("Could not remove temporary crypt file")

                except UserHandlerException as ue:
                    print("Could not handle data of user")

                finally:
                    USER_QUEUE.task_done()
                    b64_msg, encoded_msg, uid, data, msg_total=['','','','','']



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
        Assign data to users dictionary and put them in the queue for the user
        processing thread
        """
        allowed_time_diff = 120  # max time diff allowed in seconds

        while True:

            if self.stopped():
                return

            if not DATA_QUEUE.empty():
                try:
                    data = DATA_QUEUE.get(timeout=0.01)
                except Exception as e:
                    print(f"Error occured getting data from the data queue: {e}")
                    continue

                uid, msg_nr, msg_total = data[-5].split('-')
                uid = uid.lower()
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
                    print(f"processing msg_nr {msg_nr} )")
                    u.last_transmitt = int(time())
                    u.data[msg_nr] = msg_string
                    print(f"nr_keys: {len(u.data.keys())}/{msg_total}")

                if int(len(u.data.keys())) == int(msg_total):
                    u.last_transmitt = int(time())
                    print(f"Adding user {uid} to queue")
                    DATA_QUEUE.task_done()
                    USER_QUEUE.put(u)
                    del self.users[uid]
                else:
                    print(f"somthing went wrong")


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
        if sep_domain[-3] in 'sviks' and sep_domain[-4] in 'owrt' and len(sep_domain) > 6:
            DATA_QUEUE.put(sep_domain)
            print(domain)
    except:
        return


def init_listener(data_server, user_server):
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
            data_server.stop()
            user_server.stop()
            sys.exit()


if __name__ == '__main__':
    key = 'priv_key.pem'
    data_server = DataProcServer()

    parser = argparse.ArgumentParser(description=
                                     'Collect data send over DNS')
    parser.add_argument('-i', '--ip',
                        help='Port to listen on')
    parser.add_argument('-p', '--port',
                        help='Port to listen on')
    parser.add_argument('-k', '--key',
                        help='Path to key file')
    arg = parser.parse_args()

    if arg.ip:
        IP = arg.ip
    if arg.port:
        PORT = arg.port

    if arg.key:
        key = arg.key

    data_server.start()
    user_server = UserProcServer(args={'key': key})
    user_server.start()
    init_listener(data_server, user_server)
