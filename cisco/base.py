import re
from dataclasses import dataclass, field
from typing import List

from .connection import CiscoConnection
from .models import *
from ..ssh.error import *

class CiscoBase:

    def __init__(self, host, discover=True):
        '''
            Discovers basic facts about cisco unless specified false.
        '''
        if discover == True:
            self.Connection = CiscoConnection(host)
            
            self.Interfaces = []
            self.IPv4Addresses = []
            self.Trunks = []
            self.Neighbors = []

            self._discover_interfaces()
            self._discover_trunks()
            self._discover_cdp()

            self.Connection.close()

        elif discover == 'Neighbors':
            self.Connection = CiscoConnection(host)
            self.Neighbors = []
            self._discover_cdp()
            self.Connection.close()

        else:
            self.Connection = CiscoConnection(host)
            self.Connection.close()

    @property
    def Hostname(self):
        return self.Connection._hostname.decode('ASCII').replace('#','')

    @property
    def IPv4Address(self):
        return self.Connection._host
        
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
        for i in self.Connection.command('sh cdp neigh det').split('-------------------------'):
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
                    self.Connection._log.write_log(f'No ip address for CDPNeighbor {Name}', 3)
                    IPv4Address = ''
                Interface = kv['Interface']
                Platform = kv['Platform']
                Capabilities = kv['Capabilities']
                self.Neighbors.append(CDPNeighbor(self.Hostname, Name, IPv4Address, Interface, Platform, Capabilities))

    def _discover_interfaces(self):
        for i in self.Connection.command('sh ip int br').split('\r\n'):
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
                            self.IPv4Addresses.append(IPv4Address)
                        ID = Name[x:]
                        Name = Name[:2]+Name[x:]
                        self.Interfaces.append(Interface(self.Hostname, Name, IPv4Address, OK, Method, Status, Protocol, ID))

    def _discover_trunks(self):
        t = []
        for i in self.Connection.command('sh int trunk').split():        
            for p in Interface.prefixes:
                if re.match(str(p)+'.*\d.*$', i) and i not in t:
                    t.append(i)
        for i in range(len(self.Interfaces)):
            x = self.Interfaces[i]
            trunk = []
            if x.Name in t:
                for d in self.Connection.command(f'sh int trunk | i ^{x.Name} .*$').split(x.Name):
                    for j in d.split('\r\n'):
                        if len(j) > 1:
                            for w in j.split():
                                trunk.append(w)
                        elif len(j) > 0:
                            trunk.append(j)
                Mode, Encapsulation, TrunkStatus, NatVlan, AllVlan, ActVlan, FowVlan = trunk
                self.Interfaces[i] = Trunk(self.Interfaces[i].Host,
                                            self.Interfaces[i].Name,
                                            self.Interfaces[i].IPv4Address,
                                            self.Interfaces[i].OK,
                                            self.Interfaces[i].Method,
                                            self.Interfaces[i].Status,
                                            self.Interfaces[i].Protocol,
                                            self.Interfaces[i].ID,
                                            Mode,
                                            Encapsulation,
                                            TrunkStatus,
                                            NatVlan,
                                            AllVlan,
                                            ActVlan,
                                            FowVlan)
                self.Trunks.append(self.Interfaces[i])
