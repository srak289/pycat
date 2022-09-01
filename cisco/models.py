from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import List

@dataclass
class AAASession():
    Host: str
    Interface: str
    MACAddress: str
    Method: str
    Domain: str
    Status: str
    SessionID: str

@dataclass
class CDPNeighbor():
    Host: str
    Name: str
    IPv4Address: str
    Interface: str
    Platform: str
    Capabilities: str

@dataclass
class OSPFNeighbor():
    Host: str
    NeighborID: str
    Priority: str
    State: str
    DeadTime: str
    IPv4Address: str
    Interface: str

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
    Host: str
    Name: str
    IPv4Address: str
    OK: str
    Method: str
    Status: str
    Protocol: str
    ID: str
#    Vlan: List(Vlan)

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
    Mode: str
    Encapsulation: str
    TrunkStatus: str
    NatVlan: str
    AllVlan: str
    ActVlan: str
    FowVlan: str

#CDPNeighbor: CDPNeighbor

@dataclass
class Vlan():
    Host: str
    Name: str
    ID: str
    Status: str
    Interfaces: str
