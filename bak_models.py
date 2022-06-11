from sqlalchemy import Column, Enum, Float, ForeignKey, Index, Integer, String, Table, Text, Boolean, DateTime, Binary, select, BigInteger, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship, backref, object_session, aliased
from sqlalchemy.orm import sessionmaker, subqueryload_all, subqueryload, joinedload, joinedload_all

from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy import create_engine

from sqlalchemy.ext.declarative import declarative_base

from connection import SSHConnection, CiscoConnection

import re

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

class CiscoBase(Base):
    __tablename__ = 'ciscobase'
    id = Column(Integer, primary_key=True)
    hostname = Column(String(24)) 

    #ipaddr = Column(String(20))

    # redesign interface discovery to automatically create Trunks/AccessPorts?
    # does the base have IPs or does each interface have an IP

    interfaces = relationship("Interface", backref="ciscobase")
    # interfaces have ip addresses, function @property needed for all ip
    #ipv4addresses = relationship("IPv4Address", backref="ciscobase")
    #trunks = relationship("Trunk", backref="ciscobase")

    neighbors = relationship("CDPNeighbor", backref="ciscobase")
    device_type = Column(String(20))

    __mapper_args__ = {
        'polymorphic_on':device_type,
        'polymorphic_identity':'ciscobase'
    }
    
    def __init__(self, host, discover=True):
        '''
            Discovers basic facts about cisco unless specified false.
        '''
        if discover == True:
            # this needs a rework
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
    # connection is not a property of a base class..it is a handle to an ssh connection that should be held by the main engine
    @property
    def IPv4Address(self):
        return self.Connection._host

    @property
    def IPv4Addresses(self):
        a = []
        for i in self.Interfaces:
            if i.ipv4address != None:
                a.append(i)
        return i
        
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

class CiscoSwitch(CiscoBase):
    __tablename__ = 'ciscoswitch'
    hostname = Column(String(20), ForeignKey('ciscobase.hostname'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscoswitch'
    }

    vlans = relationship("Vlan", backref="CiscoSwitch")
    aaasessions = relationship("AAASession", backref="CiscoSwitch")

    def __init__(self, host, discover=True):
        super().__init__(host, discover) 

        if discover:
            self.Connection.connect()

            self.Vlans = []
            self.AAASessions = []

            self._discover_vlans()
            self._discover_auth_sess()

            self.Connection.close()

    def _discover_auth_sess(self):
        sessions = []

            # This is so that the switches without dot1x don't crash the discovery
            # We'll make this better..maybe
        s = 'dot1x system-auth-control'
        if s not in self.Connection.command('sh run | i {s}'):
            return

        for i in self.Connection.command('sh auth sess | i Gi*').split('\r\n'):
            sess = []
            for x in i.split(' '):
                if x != '':
                    sess.append(x)
            if len(sess) != 0:
                Interface, MACAddress, Method, Domain, Status, SessionID = sess
                self.AAASessions.append(AAASession(self.Hostname, Interface, MACAddress, Method, Domain, Status, SessionID))

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

        for vlan in vlans:
            if len(vlan) == 1:
                break;
            elif len(vlan) < 4:   
                vlan.append('')
            Name, ID, Status, Interfaces = vlan[0], vlan[1], vlan[2], vlan[3:]

            self.Vlans.append(Vlan(self.Hostname, Name, ID, Status, Interfaces))

    def _discover_mac_addrs(self):
        for i in self.Interfaces:
            if i is not Trunk and i.Status == 'up':
                for x in self.Connection.command(f'sh mac add | i {i.Name} ').split('\r\n'):
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

class CiscoRouter(CiscoBase):
    __tablename__ = 'ciscorouter'
    hostname = Column(String(20), ForeignKey('ciscobase.hostname'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscorouter'
    }

    ospfneighbors = relationship("OSPFNeighbor", backref="CiscoRouter")

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

class AAASession(Base):
    __tablename__ = 'aaasession'
    id = Column(Integer, primary_key=True)
    mac = Column(String(12))
    host = Column(String(20), ForeignKey('ciscoswitch.hostname'))
    interface = Column(String(20), ForeignKey('interface.name'))
    method = Column(String(20))
    domain = Column(String(20))
    status = Column(String(20))
    session_id = Column(String(20))

class CDPNeighbor(Base):
    __tablename__ = 'cdpneighbor'
    id = Column(Integer, primary_key=True)
    host = Column(String(20), ForeignKey('ciscobase.hostname'))
    name = Column(String(20))
    ipaddress = Column(String(20))
    interface = Column(String(20), ForeignKey('interface.name'))
    platform = Column(String(20))
    capabilities = Column(String(20))
    neighbor_type = Column(String(20))

    __mapper_args__ = {
        'polymorphic_identity':'cdpneighbor',
        'polymorphic_on':neighbor_type
    }

class OSPFNeighbor(Base):
    __tablename__ = 'ospfneighbor'
    id = Column(Integer, primary_key=True)
    host = Column(String(20), ForeignKey('ciscorouter.hostname'))
    neighbor_id = Column(String(20), primary_key=True)
    priority = Column(String(20))
    state = Column(String(20))
    dead_time = Column(String(20))
    ipaddress = Column(String(20))
    interface = Column(String(20), ForeignKey('interface.name'))

class CiscoPhone(CDPNeighbor):
    __tablename__ = 'ciscophone'
    host = Column(String(20), ForeignKey('cdpneighbor.host'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscophone'
    }

class CiscoWAP(CDPNeighbor):
    __tablename__ = 'ciscowap'
    host = Column(String(20), ForeignKey('cdpneighbor.host'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscowap'
    }

class CiscoATA(CDPNeighbor):
    __tablename__ = 'ciscoata'
    host = Column(String(20), ForeignKey('cdpneighbor.host'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscoata'
    }

class CiscoWLANController(CDPNeighbor):
    __tablename__ = 'ciscowlancontroller'
    host = Column(String(20), ForeignKey('cdpneighbor.host'))

    __mapper_args__ = {
        'polymorphic_identity':'ciscowlancontroller'
    }

class IPv4Address(Base):
    __tablename__ = 'ipv4address'
    id = Column(Integer, primary_key=True)
    host = Column(String(24), ForeignKey('interface.host'))
    interface = Column(String(20), ForeignKey('interface.name'))
    ipv4address = Column(String(20), primary_key=True)

class Interface(Base):
    __tablename__ = 'interface'
    id = Column(Integer, primary_key=True)
    host = Column(String(24), ForeignKey('ciscobase.hostname'))
    name = Column(String(20))
    ipv4address = relationship("IPv4Address", backref="ipv4address", nullable=True)
    ok = Column(String(20))
    method = Column(String(20))
    status = Column(String(20))
    protocol = Column(String(20))
    type = Column(String(20))

    __mapper_args__ = {
        'polymorphic_identity':'interface',
        'polymorphic_on':type
    }
    # Should vlan be considered an interface child?
    prefixes = [
            '^Vl.*',
            '^Fa.*',
            '^Gi.*',
            '^Te.*',
            '^Tw.*',
            '^Fo.*',
            '^Hu.*'
        ]

#class AccessPort(Interface):
#    __tablename__ = 'access_port'
#    pass

class Trunk(Interface):
    __tablename__ = 'trunk'
    host = Column(String(24), ForeignKey('interface.host'))
    mode = Column(String(20))
    encapsulation = Column(String(20))
    trunkstatus = Column(String(20))
    natvlan = Column(String(20))
    allvlan = Column(String(20))
    actvlan = Column(String(20))
    fowvlan = Column(String(20))

class Vlan(Base):
    __tablename__ = 'vlan'
    # vlan child of Interface?
    id = Column(Integer, primary_key=True)
    host = Column(String(24), ForeignKey('ciscoswitch.hostname'))
    name = Column(String(20))
    id = Column(String(20))
    status = Column(String(20))
    interfaces = relationship('Interface', backref='interfaces')
