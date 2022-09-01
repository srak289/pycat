import re
from dataclasses import dataclass, field
from ipaddress import IPv4Address

from .models import *
from .base import CiscoBase
from ..ssh.error import *

class CiscoSwitch(CiscoBase):

    def __init__(self, host, discover=True, rescue=False):
        super().__init__(host, discover, rescue) 

        self.Vlans = []
        self.AAASessions = []

        if discover:
            self._connection.connect()

            self._discover_vlans()
            self._discover_auth_sess()

            self._connection.close()

    def _discover_auth_sess(self):
            # This is so that the switches without dot1x don't crash the discovery
            # We'll make this better..maybe
        s = 'dot1x system-auth-control'
        if not re.search(s,self._connection.command(f'sh run | i {s}')):
            return

        for i in self._connection.command('sh auth sess | i Gi*').split('\r\n'):
            if len(i.split()) == 6:
                Interface, MACAddress, Method, Domain, Status, SessionID = i.split()
                self.AAASessions.append(AAASession(self.hostname, Interface, MACAddress, Method, Domain, Status, SessionID))

    def _discover_vlans(self):
        res = []
        for i in self._connection.command('sh vlan br').split('VLAN Name                             Status    Ports\r\n---- -------------------------------- --------- -------------------------------'):
            for k in i.split('\r\n'):
                for x in k.split(','):
                    for s in x.split(' '): 
                        if s != '':
                            res.append(s)                        
        vlans = []
        vlan = []
        tmp = ''
        concat = False
        construct = False
        for i in res:
            # Find the vlan number, it is the first item that can be cast to integer
            if self._is_integer(i):
                if construct:
                    vlans.append(vlan)
                    vlan = []
                    
                vlan.append(i)
                construct = True
                concat = True
            # Reconstruct the vlan name if it has spaces in it
            elif concat:
                if i == 'active':
                    concat = False
                    vlan.append(tmp)
                    tmp = ''
                    vlan.append(i)
                else:
                    tmp += f'{i} '
            # Add interfaces
            else:
                vlan.append(i)

        for vlan in vlans:
            if len(vlan) == 1:
                break;
            elif len(vlan) < 4:   
                vlan.append('')
            Name, ID, Status, Interfaces = vlan[0], vlan[1], vlan[2], vlan[3:]

            self.Vlans.append(Vlan(self.hostname, Name, ID, Status, Interfaces))

    def _discover_mac_addrs(self):
        for i in self.Interfaces:
            if i is not Trunk and i.Status == 'up':
                for x in self._connection.command(f'sh mac add | i {i.Name} ').split('\r\n'):
                    print(x)

    def _is_integer(self, n):
        '''
            Function to test if it is possible to cast 'n' to an integer.
        '''
        try:
            int(n)
        except ValueError:
                return False
        return True
