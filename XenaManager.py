import os
import time
import threading
import sys
import socket

sys.path.append('Autotest/lib')
sys.path.append('Autotest/config')
from Autotest.config import xena_chassis_config
from debug import *
import logging

log = logging.getLogger()
#from LabUtils.Drivers.SocketDrivers import SimpleSocket
from SocketDrivers import SimpleSocket
class KeepAliveThread(threading.Thread):
    __name__ = 'KeepAliveThread'
    message = ''
    def __init__(self, connection, interval = 10):
        threading.Thread.__init__(self)
        self.connection = connection
        self.interval = interval
        self.finished = threading.Event()
        self.setDaemon(True)
        print '[KeepAliveThread] Thread initiated, interval %d seconds' % (self.interval)

    def stop (self):
        debug(self,"Debug: before finished")
        print self.finished.set()
        debug(self,"Debug: after finished")
        #print self.join()

    def run (self):
        while not self.finished.isSet():
            self.finished.wait(self.interval)
            try:
                self.connection.Ask(self.message)
            except:
                print 'Exception occured! Retrying in 10 seconds'
                time.sleep(10)
                self.connection.Ask(self.message)


class XenaSocketDriver(SimpleSocket):
    reply_ok = '<OK>'
    __name__ = 'XenaSocketDriver'

    def __init__(self, hostname, port = int(xena_chassis_config.xena_socket_port)):
        SimpleSocket.__init__(self, hostname = hostname, port = port)
        SimpleSocket.set_keepalives(self)
        self.access_semaphor = threading.Semaphore(1)

    def ask_verify(self, cmd):
        resp = self.Ask(cmd).strip('\n')
        debug(self,'[ask_verify] for command %s Resopnse  %s' % (cmd, resp))
        if resp == self.reply_ok:
            return True
        return False

    def SendCommand(self, cmd):
        self.access_semaphor.acquire()
        SimpleSocket.SendCommand(self, cmd)
        self.access_semaphor.release()

    def Ask(self, cmd):
        self.access_semaphor.acquire()
        try:
            reply = SimpleSocket.Ask(self, cmd)
        except:
            print 'Exception occured! Retrying in 10 seconds',time.sleep(10)
            reply = SimpleSocket.Ask(self, cmd)
        
        self.access_semaphor.release()
        debug(self,'[Ask] for command %s Resopnse  %s' % (cmd, reply))
        return reply

class XenaManager:
    __name__ = 'XenaManager'
    cmd_logon                   = 'c_logon'
    cmd_logoff                  = 'c_logoff'
    cmd_owner                   = 'c_owner'
    cmd_reserve                 = 'p_reservation reserve'
    cmd_release                 = 'p_reservation release'
    cmd_relinquish              = 'p_reservation relinquish'
    cmd_reset                   = 'p_reset'
    cmd_port                    = ';Port:'
    cmd_start_traffic           = 'p_traffic on'
    cmd_stop_traffic            = 'p_traffic off'
    cmd_clear_tx_stats          = 'pt_clear'
    cmd_clear_rx_stats          = 'pr_clear'
    cmd_get_tx_stats            = 'pt_total ?'
    cmd_get_rx_stats            = 'pr_total ?'
    cmd_get_tx_stats_per_stream = 'pt_stream'
    cmd_get_rx_stats_per_tid    = 'pr_tpldtraffic'
    cmd_get_streams_per_port    = 'PS_INDICES'
    cmd_get_tid_per_stream      = 'ps_tpldid'
    cmd_comment                 = ';'
    def __init__(self, driver, password = xena_chassis_config.password):
        self.driver = driver
        self.ports = []
        self.stream_indices = []
        if self.logon(password):
            log.info('[XenaManager] Connected to %s' % self.driver.hostname)
        else:
            log.info('[XenaManager] Failed to establish connection')
            return
            #raise
        self.set_owner()

        self.keep_alive_thread = KeepAliveThread(self.driver)
        self.keep_alive_thread.start()

    def end_test(self):
        #self.driver = driver
        for module_port in self.ports:
            self.delete_streams(module_port)
        for module_port in self.ports:
            self.release(module_port)
        self.ports = []
        debug(self,"Debug : Before __del__ Ask 1")
        self.keep_alive_thread.stop()
        debug(self,"Debug : Before __del__ Ask 2")
        self.driver.ask_verify(self.cmd_logoff)
        #del self.keep_alive_thread

    def _compose_str_command(self, cmd, argument):
        command = cmd + ' \"' + argument + '\"'
        return command

    def logon(self, password):
        command = self._compose_str_command(self.cmd_logon, password)
        return self.driver.ask_verify(command)

    def set_owner(self):
        """
        set ports owner, trancated to 8 characters
        """
        #computer_name = os.uname()[1]
        computer_name = socket.gethostname()
        command = self._compose_str_command(self.cmd_owner, computer_name)
        return self.driver.ask_verify(command)

    def reserve(self, module_port):
        cmd = module_port + ' ' + self.cmd_reserve
        return self.driver.ask_verify(cmd)

    def flush_port_streams(xm , module_port):
        #module_port = xena_chassis_config.xena_port_1
        xm.release(module_port)
        xm.set_module_port(module_port)
        if not xm.reserve(module_port):
               log.info(' Cannot reserve port %s' % module_port)
        else:
               log.info(' Port %s reserved' % module_port)
        xm.remove_module_port(module_port)
        if not xm.reset():
               log.info(' Cannot reset port %s' % module_port)
        xm.remove_module_port(module_port)
        xm.add_module_port(module_port)

        if not xm.reset():
               log.info(' Cannot reset port %s' % module_port)
        xm.remove_module_port(module_port)
        xm.add_module_port(module_port)

    ##Create VLAN with ethernet frame
    def create_vlan_stream(self, src_port, dest_port, index=0, vlan=100, delete_existing=True, IP=False):
        vlan_end=None
        if '-' in str(vlan):
           vlan_end = int(vlan.split('-')[1])
           vlan = int(vlan.split('-')[0])
        vlan = int(vlan)
        if delete_existing:
           self.delete_streams(src_port)
        if not self.driver.Ask("%s ps_create [%s]" %(src_port, index)):
           print "[XenaManager] failed to create stream index %s on %s port" %(index, src_port)
           return False
        stream_command ="%s PS_HEADERPROTOCOL [%s] ETHERNET VLAN" % (src_port, index)
        stream_command += " IP" if IP else ""
        if not self.driver.ask_verify(stream_command):
           print "[XenaManager] failed to set header protocol vlan on create stream index %s on %s port" %(index, src_port)
           return False
        temp = []
        x=''
        y=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %dest_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x
        output = y
        temp = []
        x=''
        y=''
        bit=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %src_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x[2:]
        output += y
        output += '8100'
        for i in range(4-len('%x' %vlan)):
            output+='0'
            #print output
        output += '%x' %vlan
        output += "FFFF"

        if not self.driver.ask_verify("%s PS_PACKETHEADER [%s] %s" %(src_port, index, output)):
           print "[XenaManager] failed to set packet header on create stream index %s on %s port" %(index, src_port)
           return False
        if not self.driver.ask_verify("%s PS_ENABLE [%s] ON" %(src_port, index)):
           print "[XenaManager] failed to enable stream index %s on %s port" %(index, src_port)
           return False

    def create_vlan_stream_udp(self, src_port, dest_port, index=0, vlan=100, delete_existing=True):
        vlan_end = None
        if '-' in str(vlan):
            vlan_end = int(vlan.split('-')[1])
            vlan = int(vlan.split('-')[0])
        vlan = int(vlan)
        if delete_existing:
            self.delete_streams(src_port)
        if not self.driver.Ask("%s ps_create [%s]" % (src_port, index)):
            print "[XenaManager] failed to create stream index %s on %s port" % (index, src_port)
            return False
        stream_command = "%s PS_HEADERPROTOCOL [%s] ETHERNET VLAN IP UDP" % (src_port, index)
        #stream_command += " IP" if IP else ""
        if not self.driver.ask_verify(stream_command):
            print "[XenaManager] failed to set header protocol vlan on create stream index %s on %s port" % (
            index, src_port)
            return False
        temp = []
        x = ''
        y = ''
        temp = self.driver.Ask("%s P_MACADDRESS ?" % dest_port).strip('\n').split()
        for x in temp:
            if 'x' in x:
                y = x
        output = y
        temp = []
        x = ''
        y = ''
        bit = ''
        temp = self.driver.Ask("%s P_MACADDRESS ?" % src_port).strip('\n').split()
        for x in temp:
            if 'x' in x:
                y = x[2:]
        output += y
        output += '8100'
        for i in range(4 - len('%x' % vlan)):
            output += '0'
            # print output
        output += '%x' % vlan
        output += "0800450005D8000000007F11ECC0C0A86401C0A864020000000005C40000"

        if not self.driver.ask_verify("%s PS_PACKETHEADER [%s] %s" % (src_port, index, output)):
            print "[XenaManager] failed to set packet header on create stream index %s on %s port" % (index, src_port)
            return False
        if not self.driver.ask_verify("%s PS_ENABLE [%s] ON" % (src_port, index)):
            print "[XenaManager] failed to enable stream index %s on %s port" % (index, src_port)
            return False
    ##Ankit code

    def create_vlan_stream_diffserv(self, src_port, dest_port, diffserv_bit=False, index=0, vlan=100, pbit=False, delete_existing=True):
        vlan_end=None
        if '-' in str(vlan):
           vlan_end = int(vlan.split('-')[1])
           vlan = int(vlan.split('-')[0])
        vlan = int(vlan)
        if delete_existing:
           self.delete_streams(src_port)
        if not self.driver.Ask("%s ps_create [%s]" %(src_port, index)):
           print "[XenaManager] failed to create stream index %s on %s port" %(index, src_port)
           return False
        if not self.driver.ask_verify("%s PS_HEADERPROTOCOL [%s] ETHERNET VLAN IP" %(src_port, index)):
           print "[XenaManager] failed to set header protocol vlan on create stream index %s on %s port" %(index, src_port)
           return False
        temp = []
        x=''
        y=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %dest_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x
        output = y
        temp = []
        x=''
        y=''
        bit=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %src_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x[2:]
        output += y
        output += '8100'
        for i in range(4-len('%x' %vlan)):
            output+='0'
            #print output
        output += '%x' %vlan
        output += '080045'
        diffserv_bit *= 32
        bit = '%x' %diffserv_bit
        if bit == '0':
            output+='0'
        output += str(bit)
        output += '0014000000007FFF'

        if not self.driver.ask_verify("%s PS_PACKETHEADER [%s] %s" %(src_port, index, output)):
           print "[XenaManager] failed to set packet header on create stream index %s on %s port" %(index, src_port)
           return False
        if not self.driver.ask_verify("%s PS_ENABLE [%s] ON" %(src_port, index)):
           print "[XenaManager] failed to enable stream index %s on %s port" %(index, src_port)
           return False
        if pbit:
           if not vlan_end:
               if not self.driver.ask_verify("%s PS_MODIFIERCOUNT [%s] 1" %(src_port, index)):
                  return False
           else:
               if not self.driver.ask_verify("%s PS_MODIFIERCOUNT [%s] 2" %(src_port, index)):
                  return False
           if not self.driver.ask_verify("%s PS_MODIFIER [%s,0]  14 0xE0000000 INC 1" %(src_port, index)):
                  return False
           if not self.driver.ask_verify("%s PS_MODIFIERRANGE [%s,0] 0 1 7" %(src_port, index)):
                  return False
           if vlan_end:
               if not self.driver.ask_verify("%s PS_MODIFIER  [%s,1]  14 0x0FFF0000 INC 1" %(src_port, index)):
                  return False
               if not self.driver.ask_verify("%s PS_MODIFIERRANGE  [%s,1] %s 1 %s" %(src_port, index, vlan, vlan_end)):
                  return False
        return True


    ## To be enhanced
    def create_pbit_vlan_stream(self, src_port, dest_port, pbit, index=0, vlan=100, delete_existing=True):
        vlan_end=None
        if '-' in str(vlan):
           vlan_end = int(vlan.split('-')[1])
           vlan = int(vlan.split('-')[0])
        vlan = int(vlan)
        if delete_existing:
           self.delete_streams(src_port)
        if not self.driver.Ask("%s ps_create [%s]" %(src_port, index)):
           print "[XenaManager] failed to create stream index %s on %s port" %(index, src_port)
           return False
        if not self.driver.ask_verify("%s PS_HEADERPROTOCOL [%s] ETHERNET VLAN IP" %(src_port, index)):
           print "[XenaManager] failed to set header protocol vlan on create stream index %s on %s port" %(index, src_port)
           return False
        temp = []
        x=''
        y=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %dest_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x
        output = y
        temp = []
        x=''
        y=''
        bit=''
        temp = self.driver.Ask("%s P_MACADDRESS ?" %src_port).strip('\n').split()
        for x in temp:
           if 'x' in x:
               y=x[2:]
        output += y
        output += '8100'
        a = 2
        c = a*pbit
        output += '%x' %c
        for i in range(3-len('%x' %vlan)):
            output+='0'
        output += '%x' %vlan
        #output += '0800'
        #output += 'ffff'
        if not self.driver.ask_verify("%s PS_PACKETHEADER [%s] %s" %(src_port, index, output)):
           print "[XenaManager] failed to set packet header on create stream index %s on %s port" %(index, src_port)
           return False
        if not self.driver.ask_verify("%s PS_ENABLE [%s] ON" %(src_port, index)):
           print "[XenaManager] failed to enable stream index %s on %s port" %(index, src_port)
           return False
        return True
#

    def release(self, module_port):
        cmd = module_port + ' ' + self.cmd_relinquish
        try:
           if not self.isReserved(module_port):
               self.driver.ask_verify(cmd) 
               log.info("[XenaManager] " +module_port + " relinquished successfully")
               #print "[XenaManager] " +module_port + " relinquished successfully"
        except :
            log.info("[XenaManager] Warning : " + module_port + " relinquish failed")
            #print "[XenaManager] Warning : " + module_port + " relinquish failed"
        cmd = module_port + ' ' + self.cmd_release
        try:
            self.driver.ask_verify(cmd)
            debug(self,"Debug : Before __del__ 1")
        except :
            log.info("[XenaManager] Warning : " + module_port + " release failed")
        return 

    def delete_streams(self, module_port):
        streams = []
        cmd = module_port + " PS_INDICES ?"
        response = self.driver.Ask(cmd).strip('\n').split()
        if response[0] == module_port :
            streams = response[2:]
        for stream in streams:
            if not self.driver.ask_verify(module_port + " PS_DELETE " + stream):
                log.info("Unable to delete %s stream on %s port" %(stream, module_port))
                return False
        return True  

    def reset(self):
        return self.driver.ask_verify(self.cmd_reset)

    def isReserved(self, module_port):
        cmd = module_port + ' P_RESERVATION ?'
        resp = self.driver.Ask(cmd)
        if 'OTHER' in resp:
            return False
        return True

    def getPortSpeed(self, module_port):
        cmd = module_port + ' p_speed ?'
        resp = self.driver.Ask(cmd).strip('\n').split()
        return resp[-1]

    def getStreamLatency(self, module_port, stream_id):
        cmd = module_port + ' PR_TPLDLATENCY [' + stream_id + '] ?'
        resp = self.driver.Ask(cmd).strip('\n').split()
        latency = ','.join(resp[3:6])
        if '-2147483648' in resp[3]:
            cmd = module_port + ' PR_TPLDLATENCY [1] ?'
            resp = self.driver.Ask(cmd).strip('\n').split()
            latency = ','.join(resp[3:6])
        return latency

    def add_module_port(self, module_port):
        if module_port not in self.ports:
            self.ports.append(module_port)

    def remove_module_port(self, module_port):
        if module_port in self.ports:
            self.ports.remove(module_port)

    def set_module_port(self, module_port):
        self.driver.SendCommand(module_port)

    def load_script(self, filename):
        line_number = 0
        for line in open(filename, 'r'):
            command = line.strip('\n')
            line_number += 1

            if command.startswith(self.cmd_port):
                t = command.split()
                module_port = t[-1]

                self.release(module_port)
                self.set_module_port(module_port)

                if not self.reserve(module_port):
                    log.info('[XenaManager] Cannot reserve port %s' % module_port)
                else:
                    log.info('[XenaManager] Port %s reserved' % module_port)
                    self.remove_module_port(module_port)
                if not self.reset():
                    log.info('[XenaManager] Cannot reset port %s' % module_port)
                    self.remove_module_port(module_port)
                self.add_module_port(module_port)

            if command.startswith(self.cmd_comment):
                continue
            
            if command.startswith(self.cmd_get_streams_per_port):
                self.stream_indices.append(command.split()[-1])
                

            if not self.driver.ask_verify(command.strip('\n')):
                log.info('[XenaManager] Error in script in line: %d, [%s]' % (line_number, command))
                log.info('[XenaManager] Load interrupted!')
                break

        log.info('[XenaManager] Script [%s]' % filename)
        log.info('Stream Loaded successfully')
        #print '[XenaManager] Script [%s] loaded succesfully.' % filename
        
    def set_stream(self, port, pkt_size, rate=10, index=0):
        #command1 = "%s PS_INDICES  %s" % (port, index)
        command2 = "%s PS_PACKETLENGTH  [%s]  FIXED %s 1518" % (port, index, pkt_size)

        # To avoid confusion, 10G ports will also be configured according to 1Gig ports
        speed = float(self.getPortSpeed(port))
        multiplier = 10000
        if (speed == 10000) :
            multiplier /= 10
        rate_array = str(rate*multiplier).split('.')
        ratefraction = rate_array[0]
        command3 = "%s PS_RATEFRACTION [%s] %s" % (port, index, ratefraction)
        #if not self.driver.ask_verify(command1):
            #print "Stream index configuration failed"
            #return False
        if not self.driver.ask_verify(command3):
            print "Stream rate configuration failed"
            return False
        return self.driver.ask_verify(command2)


    def clear_stats_per_port(self, module_port):
        cmd = module_port + ' ' + self.cmd_clear_rx_stats
        resp = self.driver.ask_verify(cmd)
        cmd = module_port + ' ' + self.cmd_clear_tx_stats
        resp = self.driver.ask_verify(cmd)

    def _parse_stats_str(self, s):
        t = s.strip('\n').split()
        return {'packets':int(t[-1]), 'bytes':int(t[-2]), 'pps':int(t[-3]), 'bps':int(t[-4])}

    def get_stats_per_port(self, module_port):
        stats = {}
        cmd = module_port + ' ' + self.cmd_get_rx_stats
        stats['rx'] = self._parse_stats_str(self.driver.Ask(cmd))
        cmd = module_port + ' ' + self.cmd_get_tx_stats
        stats['tx'] = self._parse_stats_str(self.driver.Ask(cmd))
        return stats

    def get_stats_per_stream(self, source_module_port, dest_module_port, stream):
        stats = {}
        if isinstance(stream, (int, long)):
            cmd = '%s %s [%d] ?' % (source_module_port, self.cmd_get_tx_stats_per_stream, stream)
            stats['tx'] = self._parse_stats_str(self.driver.Ask(cmd))

            tid = self.get_tid_per_stream(source_module_port, stream)
            cmd = '%s %s [%d] ?' % (dest_module_port, self.cmd_get_rx_stats_per_tid, tid)
        else:
            cmd = '%s %s [%s] ?' % (source_module_port, self.cmd_get_tx_stats_per_stream, self.stream_indices[0])
            stats['tx'] = self._parse_stats_str(self.driver.Ask(cmd))

            tid = self.get_tid_per_stream(source_module_port, self.stream_indices[0])
            cmd = '%s %s [%s] ?' % (dest_module_port, self.cmd_get_rx_stats_per_tid, tid)
        stats['rx'] = self._parse_stats_str(self.driver.Ask(cmd))
        return stats
        
    def start_traffic_per_port(self, module_port):
        cmd = module_port + ' ' + self.cmd_start_traffic
        return self.driver.ask_verify(cmd)

    def stop_traffic_per_port(self, module_port):
        cmd = module_port + ' ' + self.cmd_stop_traffic
        return self.driver.ask_verify(cmd)

    def get_streams_per_port(self, module_port):
        cmd = '%s %s ?' % (module_port, self.cmd_get_streams_per_port)
        resp = self.driver.Ask(cmd).strip('\n').lower().split()
        resp.reverse()
        streams = []
        for e in resp:
            if e == self.cmd_get_streams_per_port:
                return streams
            streams.append(int(e))
        return streams

    def get_tid_per_stream(self, module_port, stream):
        if isinstance(stream, (int, long)):
            cmd = '%s %s [%d] ?' % (module_port, self.cmd_get_tid_per_stream, self.stream_indices[0])
        else:
            cmd = '%s %s [%s] ?' % (module_port, self.cmd_get_tid_per_stream, stream)
        resp = self.driver.Ask(cmd).strip('\n').lower().split()
        return int(resp[-1])

    def do_traffics_test(xm):
        xm.clear_stats_per_port(xena_chassis_config.xena_port_1)
        xm.clear_stats_per_port(xena_chassis_config.xena_port_2)
        #xm.clear_stats_per_port(xena_chassis_config.xena_port_3)
        xm.start_traffic_per_port(xena_chassis_config.xena_port_1)
        xm.start_traffic_per_port(xena_chassis_config.xena_port_2)
        #xm.start_traffic_per_port(xena_chassis_config.xena_port_3)
        time.sleep(20)
        xm.stop_traffic_per_port(xena_chassis_config.xena_port_1)
        xm.stop_traffic_per_port(xena_chassis_config.xena_port_2)
        #xm.stop_traffic_per_port(xena_chassis_config.xena_port_3)
        time.sleep(5)
        xm.get_stats_per_port(xena_chassis_config.xena_port_1)
        xm.get_stats_per_port(xena_chassis_config.xena_port_2)
        #xm.get_stats_per_port(xena_chassis_config.xena_port_3)
        bistats=[]
        bistats.append(xm.get_stats_per_port(xena_chassis_config.xena_port_1))
        bistats.append(xm.get_stats_per_port(xena_chassis_config.xena_port_2))
        #bistats.append(xm.get_stats_per_port(xena_chassis_config.xena_port_3))
        print(bistats)
        a = 100*((float(bistats[0]['rx']['packets']))/(float(bistats[0]['tx']['packets'])))
        b = 100*((float(bistats[1]['rx']['packets']))/(float(bistats[1]['tx']['packets'])))
        print(a)
        print(b)
        if a >=90 and b >=90:
           log.status('Traffic Passed')
        else :
           log.status('Traffic failed')
           raise SystemExit
        time.sleep(5)
        xm.reserve(xena_chassis_config.xena_port_1)
        xm.reserve(xena_chassis_config.xena_port_2)
        #xm.reserve(xena_chassis_config.xena_port_3)
        xm.delete_streams(xena_chassis_config.xena_port_1)
        xm.delete_streams(xena_chassis_config.xena_port_2)
        #xm.delete_streams(xena_chassis_config.xena_port_3)

        xm.clear_stats_per_port(xena_chassis_config.xena_port_1)
        xm.clear_stats_per_port(xena_chassis_config.xena_port_2)
        #xm.clear_stats_per_port(xena_chassis_config.xena_port_3)
        time.sleep(10)
        return
	

#===============================================================================
def get_multistream_stats(xm):
    """ Assumes only two ports were added to XenaManager """
    stats = {}
    ports = xm.ports
    for port_index in range(len(ports)):
        streams = xm.get_streams_per_port(ports[port_index])
        stats[ports[port_index]] = []
        if len(ports) == 2:
            for stream in streams:
                tmp_stats = xm.get_stats_per_stream(ports[port_index], ports[(port_index + 1)],  stream)
                tmp_res = tmp_stats['tx']['packets'] == tmp_stats['rx']['packets']
                stats[ports[port_index]].append( (tmp_stats['tx']['packets'], tmp_stats['rx']['packets'], tmp_res) )
        else:
            for stream in streams:
                tmp_stats = xm.get_stats_per_port(ports[port_index])
                tmp_res = tmp_stats['tx']['packets'] == tmp_stats['rx']['packets']
                stats[ports[port_index]].append( (tmp_stats['tx']['packets'], tmp_stats['rx']['packets'], tmp_res) )
    return stats

def get_statistics(xm, period = 300):
    """ Get statistics from all the ports """
    for module_port in xm.ports:
        xm.stop_traffic_per_port(module_port)
        xm.clear_stats_per_port(module_port)

    time.sleep(10)

    print '[XenaManager] Traffic stopped, stats cleared'

    for module_port in xm.ports:
        xm.start_traffic_per_port(module_port)

    print '[XenaManager] Traffic started'
    time.sleep(period)

    for module_port in xm.ports:
        xm.stop_traffic_per_port(module_port)

    time.sleep(10)

    print '[XenaManager] Traffic stopped'
    print '[XenaManager] Stats'
    
    stats = get_multistream_stats(xm)

    return stats

if __name__ == '__main__':
    driver = XenaSocketDriver(xena_chassis_config.xena_ip)
    xm = XenaManager(driver)

