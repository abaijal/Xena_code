#!/usr/bin/python
import os
xena_ip = os.environ.get('XENA_IP_ADDRESS', '10.252.0.52')
password = os.environ.get('XENA_PASSWORD', 'VectaStar')
xena_port_1 = os.environ.get('XENA_PORT_1', '10/0')
xena_port_2 = os.environ.get('XENA_PORT_2', '10/1')
#xena_port_3 = os.environ.get('XENA_PORT_3', '0/5')
xena_socket_port = os.environ.get('XENA_SOCKET', '22611')
