from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import List

class mock():

    def get(self, k):
        if k in self.__dict__.keys():
            return self.__dict__[k]
        else:
            raise KeyError(f'{self} has no attribute {k}')

    def __iter__(self):
        for x in self.__dict__.values():
            yield x

    def __repr__(self):
        return f"[{', '.join([x for x in self.__dict__.keys()])}]"

@dataclass
class AAASession():
    host: str
    interface: str
    macaddress: str
    method: str
    domain: str
    status: str
    sessionid: str

@dataclass
class CDPNeighbor():
    host: str
    name: str
    ipv4address: str
    interface: str
    platform: str
    capabilities: str

@dataclass
class OSPFNeighbor():
    host: str
    neighborid: str
    priority: str
    state: str
    deadtime: str
    ipv4address: str
    interface: str

@dataclass
class CiscoPhone(CDPNeighbor):
    pass

@dataclass
class CiscoWAP(CDPNeighbor):
    pass


@dataclass
class CiscoATA(CDPNeighbor):
    pass

@dataclass
class CiscoWLANController(CDPNeighbor):
    pass

@dataclass
class Interface():
    host: str
    name: str
    ipv4address: str
    ok: str
    method: str
    status: str
    protocol: str
    id: str
    vlan: mock

    prefixes = [
            '^Vl.*',
            '^Fa.*',
            '^Gi.*',
            '^Te.*',
            '^Tw.*',
            '^Fo.*',
            '^Hu.*'
        ]

#@dataclass
#class MACAddress():
#    Address: str
#    Interface: Interface
#    Vlan: Vlan

@dataclass
class AccessPort(Interface):
    pass

@dataclass
class Trunk(Interface):
    mode: str
    encapsulation: str
    trunkstatus: str
    natvlan: str
    allvlan: str
    actvlan: str
    fowvlan: str

#CDPNeighbor: CDPNeighbor

@dataclass
class Vlan():
    host: str
    name: str
    id: str
    status: str
    interfaces: mock
