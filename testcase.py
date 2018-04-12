from __future__ import print_function

import sys
import time
import pytest
import logging
sys.path.append('config')
from Autotest.lib.vsxena import XenaManager
from Autotest.config import xena_chassis_config
from Autotest.config import xena_chassis_config
import Autotest.lib.vectastar_logging as vectastar_logging
vectastar_logging.setup_logging()
vectastar_logging.set_context(phase='service_test')
log = logging.getLogger()




log.info("****************************** Traffic generation *************************")
xm = XenaManager.XenaManager(XenaManager.XenaSocketDriver(xena_chassis_config.xena_ip))

#Releasing port details if any before pushing any configuration
xm.flush_port_streams(module_port=xena_chassis_config.xena_port_1)
xm.flush_port_streams(module_port=xena_chassis_config.xena_port_2)

##Ethernet frame with VLAN

xm.create_vlan_stream(src_port=xena_chassis_config.xena_port_1, dest_port=xena_chassis_config.xena_port_2,index=0, vlan=54, delete_existing=True)
xm.create_vlan_stream(src_port=xena_chassis_config.xena_port_2, dest_port=xena_chassis_config.xena_port_1,index=0, vlan=54, delete_existing=True)
xm.set_stream(port=xena_chassis_config.xena_port_1, pkt_size=128, rate=50, index=0)
xm.set_stream(port=xena_chassis_config.xena_port_2, pkt_size=128, rate=50, index=0)



##Diffserv stream
xm.create_vlan_stream_diffserv(src_port=xena_chassis_config.xena_port_1, dest_port=xena_chassis_config.xena_port_2,diffserv_bit=5, index=1, vlan=100)
xm.create_vlan_stream_diffserv(src_port=xena_chassis_config.xena_port_2, dest_port=xena_chassis_config.xena_port_1,diffserv_bit=5, index=1, vlan=100)
xm.set_stream(port=xena_chassis_config.xena_port_1, pkt_size=128, rate=50, index=1)
xm.set_stream(port=xena_chassis_config.xena_port_2, pkt_size=128, rate=50, index=1)


##TCP based stream usually used for channel bonding
xm.create_vlan_stream_udp(src_port=xena_chassis_config.xena_port_1, dest_port=xena_chassis_config.xena_port_2,index=2, vlan=100)
xm.create_vlan_stream_udp(src_port=xena_chassis_config.xena_port_2, dest_port=xena_chassis_config.xena_port_1,index=2, vlan=100)
xm.set_stream(port=xena_chassis_config.xena_port_1, pkt_size=1518, rate=50, index=2)
xm.set_stream(port=xena_chassis_config.xena_port_2, pkt_size=1518, rate=50, index=2)

#xm.do_traffics_test()
'''
def test_cb_test_1(vsr):
    """
       +---------+-------------+---------+
       | **ep1** | **Vbridge** | **ep2** |
       +---------+-------------+---------+
       | eth1.10 |     10/10   | eth1.10 |
       +---------+-------------+---------+

    """

    # Interface configuration of an endpoint
    iface_conf = {'.10': 'auto'}

    # VectaStar vbridges configurations
    vbridges = [[10, 10], [10, 10]]

    # rtb is not existing (example: topology 111)
    rta_vbridge = [vbridges[0]]
    rtb_vbridge = [vbridges[1]]
    vsr.service_generator_with_cb(ep1_iface=iface_conf,
                          ep2_iface=iface_conf,
                          rta_vbridge=rta_vbridge,
                          rtb_vbridge=rtb_vbridge)

'''