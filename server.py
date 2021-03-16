from dnslib.server import DNSRecord
from dnslib.dns import DNSQuestion
from dnslib.label import DNSBuffer

import socket
import sys


def parse_data(data):
    try:
        d = DNSRecord.parse(data)
    except (dnslib.buffer.BufferError, dnslib.dns.DNSError) as e:
        print("Error occurred: {e}")
        return

    q = d.get_q()
    print(d)

    print(f"'Question: {q}")


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

    data = None

