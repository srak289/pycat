from sqlalchemy import Column, Enum, Float, ForeignKey, Index, Integer, String, Table, Text, Boolean, DateTime, Binary, select, BigInteger, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship, backref, object_session, aliased
from sqlalchemy.orm import sessionmaker, subqueryload_all, subqueryload, joinedload, joinedload_all

from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy import create_engine

from sqlalchemy.ext.declarative import declarative_base

from .connection import SSHConnection, CiscoConnection

import re
import pdb

class DeclarativeBase(object):
    def to_dict(self):
        return { k: v for k, v in self.__dict__.items() if k[0] != '_' }

    def to_json(self):
        ret = {}
        for k, v in self.__dict__.items():
            if hasattr(v, 'to_json'):
                ret[k] = v.to_json()
            elif type(v) == bytes and len(v) == 16:
                ret[k] = uuid.UUID(bytes=v).urn
            elif type(v).__name__ in dir(builtins):
                ret[k] = v
            elif v is None:
                # 'None' does not match the builtin test above.
                pass
            else:
                raise ValueError(v)
        return ret
    
Base = declarative_base(cls=DeclarativeBase)
metadata = Base.metadata

interface_vlan = Table('association', Base.metadata,
    Column('vlan_id', Integer, ForeignKey('vlan.id')),
    Column('interface_id', Integer, ForeignKey('interface.id'))
)

class CiscoBase(Base):
    __tablename__ = 'ciscobase'
    id = Column(Integer, primary_key=True)
    hostname = Column(String(24)) 
    #ipaddr = Column(String(24))
    interfaces = relationship("Interface", backref="ciscobase", cascade="all, delete-orphan")
    ipv4addresses = relationship("IPv4Address", backref="ciscobase", cascade="all, delete-orphan")
    # trunks = relationship("Trunk", backref="ciscobase", cascade="all, delete-orphan")
    # trunks are interfaces and we already built the relationship for them
    neighbors = relationship("CDPNeighbor", backref="ciscobase", cascade="all, delete-orphan")
    device_type = Column(String(24))

    __mapper_args__ = {
        'polymorphic_on':device_type,
        'polymorphic_identity':'ciscobase'
    }
    
    def __init__(self, host, discover=True, **kwargs):
        super().__init__(**kwargs)
        '''
            Discovers basic facts about cisco unless specified false.
        '''
        if discover == True:
            # this needs a rework
            self.Connection = CiscoConnection(host)
            
            self.interfaces = self._discover_interfaces()
            self.trunks = self._discover_trunks()
            self.neighbors = self._discover_cdp()

            self.Connection.close()

        elif discover == 'Neighbors':
            self.Connection = CiscoConnection(host)
            self.neighbors = self._discover_cdp()
            self.Connection.close()

        else:
            self.Connection = CiscoConnection(host)
            self.Connection.close()

    @property
    def Hostname(self):
        return self.Connection._hostname.decode('ASCII').replace('#','')
    @Hostname.setter
    def Hostname(self, o):
        if type(o) is str:
            self.__hostname = o
    @property
    def IPv4Address(self):
        return self.Connection._host
    @IPv4Address.setter
    def IPv4Address(self, o):
        try:
            IPv4Address(o)
        except Exception:
            raise Exception(f'IPv4Assignment failed on CiscoBase load for {o}')

    @property
    def IPv4Addresses(self):
        a = []
        for i in self.interfaces:
            if i.ipv4address != None:
                a.append(i)
        return a
        
    def _discover_cdp(self):
        cdp = []
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
                name = kv['DeviceID']
                try:
                    ipv4address = kv['IPaddress']
                except KeyError as e:
                    self.Connection._log.write_log(f'No ip address for CDPNeighbor {name}', 3)
                    ipv4address = ''
                interface = kv['Interface']
                index = 0
                for j in interface:
                    if not j.isdecimal():
                        index += 1
                    else:
                        break
                interface = interface[:2]+interface[index:]
                for i in self.interfaces:
                    if i.name == interface:
                        interface = i
                platform = kv['Platform']
                capabilities = kv['Capabilities']
                cdp.append(
                    CDPNeighbor(
                        name = name,
                        ipaddress = ipv4address,
                        interface = interface,
                        platform = platform,
                        capabilities = capabilities
                    )
                )
        return cdp

    def _discover_interfaces(self):
        interfaces = []
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
                        name, ipv4address, ok, method, status, protocol = a
                        ipv4address = IPv4Address(
                            ipaddr = ipv4address
                        )
                        if ipv4address != 'unassigned':
                            self.IPv4Addresses.append(ipv4address)
                        id = name[x:]
                        name = name[:2]+name[x:]
                        interfaces.append(
                            Interface(
                                name = name,
                                ipv4address = ipv4address,
                                ok = ok,
                                method = method,
                                status = status,
                                protocol = protocol,
                                num_id = id
                            )
                        )
        return interfaces

    def _discover_trunks(self):
        trunks = []
        t = []
        for i in self.Connection.command('sh int trunk').split():        
            for p in Interface.prefixes:
                if re.match(str(p)+'.*\d.*$', i) and i not in t:
                    t.append(i)
        for i in range(len(self.interfaces)):
            x = self.interfaces[i]
            trunk = []
            if x.name in t:
                for d in self.Connection.command(f'sh int trunk | i ^{x.name} .*$').split(x.name):
                    for j in d.split('\r\n'):
                        if len(j) > 1:
                            for w in j.split():
                                trunk.append(w)
                        elif len(j) > 0:
                            trunk.append(j)
                mode, encapsulation, trunkstatus, natvlan, allvlan, actvlan, fowvlan = trunk
                # for now we keep the vlan info but just as a string not a relationship
                #for i in acctvlan.split(','):
                #    if '-' in i:
                #            for j in range(int(i.split('-')[0]), int(i.split('-')[1])):
                #                    vlans.append(j)
                #    else:
                #            vlans.append(i)
                self.interfaces[i] = Trunk(
                    name = self.interfaces[i].name,
                    ipv4address = self.interfaces[i].ipv4address,
                    ok = self.interfaces[i].ok,
                    method = self.interfaces[i].method,
                    status = self.interfaces[i].status,
                    protocol =self.interfaces[i].protocol,
                    num_id = self.interfaces[i].num_id,
                    mode = mode,
                    encapsulation = encapsulation,
                    trunkstatus = trunkstatus,
                    natvlan = natvlan,
                    allvlan = allvlan,
                    actvlan = actvlan,
                    fowvlan = fowvlan)
                trunks.append(self.interfaces[i])
        return trunks

# need layer 2 and layer 3 differentiation
# need to discover routing on switches for things like the 9500

class CiscoSwitch(CiscoBase):
    __tablename__ = 'ciscoswitch'
    id = Column(Integer, ForeignKey('ciscobase.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity':'ciscoswitch'
    }

    vlans = relationship("Vlan", backref="ciscoswitch", cascade="all, delete-orphan")
#    aaasessions = relationship("AAASession", backref="ciscoswitch", cascade="all, delete-orphan")

    def __init__(self, host, discover=True, **kwargs):
        super().__init__(host, discover, **kwargs) 

        if discover:
            self.Connection.connect()
            self.vlans = self._discover_vlans()
#            self.aaasessions = self._discover_auth_sess()
            self.Connection.close()

#    def _realize_access_ports(self):
#        for i in self.interfaces:
#            print(f'Checking type of {i} type is {type(i)}')
#            if i is not Trunk:
#                i = AccessPort(
#                    asdf
#                )
#            # we were here
#
#    def _discover_auth_sess(self):
#        sessions = []
#            # This is so that the switches without dot1x don't crash the discovery
#            # We'll make this better..maybe
#        s = 'dot1x system-auth-control'
#        if s not in self.Connection.command(f'sh run | i {s}'):
#            return sessions
#
#        for i in self.Connection.command('sh auth sess | i Gi*').split('\r\n'):
#            sess = []
#            for x in i.split(' '):
#                if x != '':
#                    sess.append(x)
#            if len(sess) != 0:
#                interface, macaddress, method, domain, status, session_id = sess
#                for i in self.interfaces:
#                    if i.name == interface:
#                        print(f'Found interface {i.name} for {interface}')
#                        interface = i
#                sessions.append(
#                    AAASession(
#                        interface = interface,
#                        macaddress = macaddress,
#                        method = method,
#                        domain = domain,
#                        status = status,
#                        session_id = session_id
#                    )
#                )
#        return sessions

    def _discover_vlans(self):
        res = []
        for i in self.Connection.command('sh vlan br').split('VLAN Name                             Status    Ports\r\n---- -------------------------------- --------- -------------------------------'):
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
        res = []
        for vlan in vlans:
            if len(vlan) == 1:
                break;
            elif len(vlan) < 4:   
                vlan.append('')
            num_id, name, status, interfaces = vlan[0], vlan[1], vlan[2], vlan[3:]
            # we need to build a list of interfaces out of self.interfaces to set this
            i = []
            for si in self.interfaces:
                if si in interfaces:
                    i.append(si)
            res.append(
                Vlan(
                    name = name,
                    num_id = num_id,
                    status = status,
                    interfaces = i
                )
            )
        return res

    def _discover_mac_addrs(self):
        for i in self.interfaces:
            if i is not Trunk and i.status == 'up':
                for x in self.Connection.command(f'sh mac add | i {i.name} ').split('\r\n'):
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

#class AAASession(Base):
#    __tablename__ = 'aaasession'
#    id = Column(Integer, primary_key=True)
#    macaddress = Column(String(12))
#    host_id = Column(Integer, ForeignKey('ciscoswitch.id'))
#    interface_id = Column(Integer, ForeignKey('interface.id'))
#    method = Column(String(24))
#    domain = Column(String(24))
#    status = Column(String(24))
#    session_id = Column(String(24))

class CDPNeighbor(Base):
    __tablename__ = 'cdpneighbor'
    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey('ciscobase.id'))
    name = Column(String(48))
    ipaddress = Column(String(24))
    interface_id = Column(Integer, ForeignKey('interface.id'))
    interface = relationship("Interface", back_populates="neighbor")
    platform = Column(String(32))
    capabilities = Column(String(48))
    neighbor_type = Column(String(24))

    __mapper_args__ = {
        'polymorphic_identity':'cdpneighbor',
        'polymorphic_on':neighbor_type
    }

class IPv4Address(Base):
    __tablename__ = 'ipv4address'
    id = Column(Integer, primary_key=True)
    ipaddr = Column(String(24))
    host_id = Column(Integer, ForeignKey('ciscobase.id'))
    interface_id = Column(Integer, ForeignKey('interface.id'))
    interface = relationship("Interface", back_populates="ipv4address")

class Interface(Base):
    __tablename__ = 'interface'
    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey('ciscobase.id'))
    # eventually add array of config lines
    name = Column(String(24))
    vlans = relationship("Vlan", secondary=interface_vlan, back_populates="interfaces")
    ipv4address = relationship("IPv4Address", uselist=False, back_populates="interface", cascade="all, delete-orphan")
    neighbor = relationship("CDPNeighbor", uselist=False, back_populates='interface', cascade="all, delete-orphan")
    ok = Column(String(24))
    method = Column(String(24))
    status = Column(String(24))
    protocol = Column(String(24))
    num_id = Column(String(24))
    type = Column(String(24))

    __mapper_args__ = {
        'polymorphic_identity':'interface',
        'polymorphic_on':type
    }
    prefixes = [
            '^Vl.*',
            '^Fa.*',
            '^Gi.*',
            '^Te.*',
            '^Tw.*',
            '^Fo.*',
            '^Hu.*'
        ]

# class PortChannel(Base):

#class AccessPort(Interface):
#    __tablename__ = 'accessport'
#    id = Column(Integer, ForeignKey('interface.id'), primary_key=True)
#    aaasessions = relationship("AAASession", backref="accessport")

class Trunk(Interface):
    __tablename__ = 'trunk'
    id = Column(Integer, ForeignKey('interface.id'), primary_key=True)
    mode = Column(String(24))
    encapsulation = Column(String(24))
    trunkstatus = Column(String(24))
    natvlan = Column(String(256))
    allvlan = Column(String(256))
    actvlan = Column(String(256))
    fowvlan = Column(String(256))

class Vlan(Base):
    __tablename__ = 'vlan'
    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey('ciscoswitch.id'))
    name = Column(String(32))
    num_id = Column(Integer)
    status = Column(String(24))
    interfaces = relationship("Interface", secondary=interface_vlan, back_populates="vlans")
