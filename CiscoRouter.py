from dataclasses import dataclass, field
from CiscoConnection import CiscoConnection
from CiscoModels import *
from CiscoBase import CiscoBase
from SSHConnectionError import *
from ipaddress import IPv4Address
import re

class CiscoRouter(CiscoBase):

    def __init__(self, host, discover=True):
        super().__init__(host, discover) 

        if discover:
            self.Connection.connect()
            
            self.OSPFNeighbors = []
            self._discover_ospf()

            self.Connection.close()

    def _discover_ospf(self):
        for i in self.Connection.command('sh ip ospf neigh | i Gi*').split('\r\n'):
            if len(i.split(' ')) > 1:
                res = []
                for s in i.split(' '):
                    if s != '':
                        res.append(s)
                NeighborID, Priority, State, DeadTime, IPv4Address, Interface = res
                self.OSPFNeighbors.append(OSPFNeighbor(self.Hostname, NeighborID, Priority, State, DeadTime, IPv4Address, Interface))
