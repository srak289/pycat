import re
from dataclasses import dataclass, field
from ipaddress import IPv4Address

from .models import *
from .base import CiscoBase
from .utils import attr_name
from ..ssh.error import *

class CiscoSwitch(CiscoBase):

    def __init__(self, host, **kwargs):
        super().__init__(host, **kwargs) 

        self.vlans = mock()
        self.aaasessions = mock()

        if discover:
            self._connection.connect()

            self._discover_vlans()
            self._discover_auth_sess()

            self._connection.close()

    def _discover_auth_sess(self):
        # This is so that the switches without dot1x don't crash the discovery
        # We'll make this better..maybe
        s = 'dot1x system-auth-control'
        if not re.search(s, self._connection.command(f'sh run | i {s}')):
            return

        for i in self._connection.command('sh auth sess | i Gi*').split('\r\n'):
            t = i.split()
            if len(t) == 6:
                setattr(self.aaasessions, attr_name(t[0]), AAASession(self.hostname, *[ x for x in t ]))

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
            # TODO: Optimize
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
            ID, Name, Status, Interfaces = vlan[0], vlan[1].strip(), vlan[2], vlan[3:]

            xx = mock()
            for i in Interfaces:
                i = attr_name(i)
                if hasattr(self.interfaces, i):
                    setattr(xx, i, getattr(self.interfaces, i))
            setattr(self.vlans, attr_name(Name), Vlan(self.hostname, Name, ID, Status, xx))

            for k in self.vlans.__dict__.keys():
                for i in self.vlans.__dict__[k].interfaces.__dict__.keys():
                    self.interfaces.__dict__[i].vlan = self.vlans.__dict__[k]

    def _discover_mac_addrs(self):
        for i in self.interfaces:
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
