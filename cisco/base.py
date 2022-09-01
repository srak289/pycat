import re
from dataclasses import dataclass, field
from typing import List

from .connection import CiscoConnection
from .models import *
from ..ssh.error import *

class mock(): pass

class CiscoBase:

    def __init__(self, host, discover=True):
        '''
            Discovers basic facts about cisco unless specified false.
        '''
        if discover == True:
            self._connection = CiscoConnection(host)
            
            self.interfaces = mock()
            self.ipv4addresses = []
            self.trunks = mock()
            self.neighbors = mock()

            self._discover_interfaces()
            self._discover_trunks()
            self._discover_cdp()

            self._connection.close()

        elif discover == 'Neighbors':
            self._connection = CiscoConnection(host)
            self.neighbors = mock()
            self._discover_cdp()
            self._connection.close()

        else:
            self._connection = CiscoConnection(host)
            self._connection.close()

    def command(self, *args, **kwargs):
        return self._connection.command(*args, **kwargs)

    def configure(self, *args, **kwargs):
        return self._connection.configure(*args, **kwargs)

    def control(self):
        return self._connection.control()

    @property
    def hostname(self):
        return self._connection._hostname.decode('ASCII').replace('#','')

    @property
    def ipv4address(self):
        return self._connection._host
        
    def backup(self):
        '''
            Backs up configuration to disk.
        '''
        raise NotImplementedError
        # backupdirectory determied by the stats of host platform ?
        os.setcwd(self._backupdir)
        if os.path.exist(f"{self._host}.bak"):
            pass
            # roll backups and new backup
        else:
            pass
            # new backup

    def restore(self):
        '''
            Restores configuration from disk.
        '''
        raise NotImplementedError
        if os.path.exist(f'{self._host}.bak'):
            print("Backup exists")
        else:
            raise NoBackupError(self._host)

    def _discover_cdp(self):
        for i in self._connection.command('sh cdp neigh det').split('-------------------------'):
            kv = {}
            for j in i.split('\r\n'):
                # need to split on commas here
                for k in j.split(','):
                    r = k.replace(' ','').split(':')
                    if len(r) > 1:
                        kv.update({r[0]:r[1]})
            if len(kv.items()) > 1:
                # For now we are discarding information but in the future we might make it dynamic
                Name = kv['DeviceID']
                try:
                    IPv4Address = kv['IPaddress']
                except KeyError as e:
                    self._connection._log.write_log(f'No ip address for CDPNeighbor {Name}', 3)
                    IPv4Address = ''
                Interface = kv['Interface']
                Platform = kv['Platform']
                Capabilities = kv['Capabilities']
                self.neighbors.__dict__.update({Name.lower().replace('-','_'):CDPNeighbor(self.hostname, Name, IPv4Address, Interface, Platform, Capabilities)})

    def _discover_interfaces(self):
        for i in self._connection.command('sh ip int br').split('\r\n'):
            a = i.split()
            for p in Interface.prefixes:
                if len(a) > 0:
                    if re.match(str(p), a[0]):
                        if a[4] == 'administratively':
                            a[4] = 'administratively down'
                            _ = a.pop(5)
                        x = 0
                        for c in a[0]:
                            if not c.isdecimal():
                                x += 1
                            else:
                                break
                        Name, IPv4Address, OK, Method, Status, Protocol = a
                        if IPv4Address != 'unassigned':
                            self.ipv4addresses.append(IPv4Address)
                        ID = Name[x:]
                        Name = Name[:2]+Name[x:]
                        self.interfaces.__dict__.update({Name.lower().replace('/','_'):Interface(self.hostname, Name, IPv4Address, OK, Method, Status, Protocol, ID)})

    def _discover_trunks(self):
        t = []
        for i in self._connection.command('sh int trunk').split():        
            for p in Interface.prefixes:
                if re.match(str(p)+'.*\d.*$', i) and i not in t:
                    t.append(i)
        for k, v in self.interfaces.__dict__.items():
            x = v
            trunk = []
            if x.Name in t:
                for d in self._connection.command(f'sh int trunk | i ^{x.Name} .*$').split(x.Name):
                    for j in d.split('\r\n'):
                        if len(j) > 1:
                            for w in j.split():
                                trunk.append(w)
                        elif len(j) > 0:
                            trunk.append(j)
                Mode, Encapsulation, TrunkStatus, NatVlan, AllVlan, ActVlan, FowVlan = trunk
                self.interfaces.__dict__.update({k:Trunk(*[o for y,o in v.__dict__.items()], Mode, Encapsulation, TrunkStatus, NatVlan, AllVlan, ActVlan, FowVlan)})
                self.trunks.__dict__.update({v.Name.lower().replace('/','_'):v})
