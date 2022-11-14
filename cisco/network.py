import re

from .models import *
from .base import CiscoBase
from .switch import CiscoSwitch
from .router import CiscoRouter
from ..ssh.error import *
from ..ssh.log import Logger

class CiscoNetwork:

    def __init__(self, host, discover=True):

        self._queue = []

        self.Switches = []
        self.Routers = []
        self.Phones = []
        self.Waps = []
        self.Atas = []
        self.Wlanc = []
        self.bad = []

        self._log = Logger('CiscoNetwork', 4, binary=False, fg=True)
        self._log.open_log()

        if discover:
            self._discover_network(host)

    def _discover_one(self):
        raise NotImplementedError

    def _discover_network(self, i):
            # This should only catch the first call to _discover_network because after
            # we are only passing objects
        if type(i) is str:
            try:
                c = CiscoBase(i, discover='Neighbors')

                for n in c.Neighbors:
                    self._discover_network(n)
            except LoginError as e:
                self._log.write_log(e, 2)
                self.bad.append(i)
            except TimeoutError as e:
                self._log.write_log(e, 2)

        elif i.IPv4Address == '':
                # We should still add an entry for it if we can figure out it's an ATA, for example
            self._log.write_log(f'Neighbor {i.Name} has no IPv4Address, cannot discover', 2)
            return

        elif i.IPv4Address in self._queue:
            self._log.write_log(f'{i.IPv4Address} already exists in queue', 3)
            return

        else:
            self._log.write_log(f'Discovering device {i.__repr__()}', 5)
                
            if type(i) is CDPNeighbor:

                    # For now we are skipping the 9Ks
                    # and the FICs

                if re.match('N9K-C93180YC-FX', i.Platform):
                    self._log.write_log(f'Skipping {i.IPv4Address} for platform type', 3)
                    self._queue.append(i.IPv4Address)
                    pass

                    # Here we discover basic devices first
                    # This stops WAPs being discovered as routers
                    # ATAs go before phones because phone regex catches ATA Capabilities string 'HostPhone'
                    # This could be more specific but should work for now

                elif re.match('^.*(AIR|CAP).*$', i.Platform):
                    self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoWAP', 5)
                    self.Waps.append(CiscoWAP(i.Host, i.Name, i.IPv4Address, i.Interface, i.Platform, i.Capabilities))
                    self._queue.append(i.IPv4Address)

                elif re.match('^.*ATA.*$', i.Platform):
                    self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoATA', 5)
                    self.Atas.append(CiscoATA(i.Host, i.Name, i.IPv4Address, i.Interface, i.Platform, i.Capabilities))
                    self._queue.append(i.IPv4Address)

                elif re.match('^.*AIR.*$', i.Platform):
                    self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoWLANController', 5)
                    self.Wlanc.append(CiscoWLANController(i.Host, i.Name, i.IPv4Address, i.Interface, i.Platform, i.Capabilities))
                    self._queue.append(i.IPv4Address)

                elif re.match('^.*Phone.*$', i.Capabilities):
                    self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoPhone', 5)
                    self.Phones.append(CiscoPhone(i.Host, i.Name, i.IPv4Address, i.Interface, i.Platform, i.Capabilities))
                    self._queue.append(i.IPv4Address)

                elif re.match('^.*C(\d){4}.*$', i.Platform):
                    try:
                        self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoSwitch', 5)
                        self.Switches.append(CiscoSwitch(i.IPv4Address))
                        for ip in self.Switches[-1].IPv4Addresses:
                            self._queue.append(ip)
                        for n in self.Switches[-1].Neighbors:
                            self._log.write_log(f'Recursing for {n.IPv4Address} from host {self.Switches[-1].Hostname}', 4)
                            self._discover_network(n)
                    except LoginError as e:
                        self._log.write_log(e, 2)
                        self.bad.append(i)
                    except TimeoutError as e:
                        self._log.write_log(e, 2)
                    except CommandError as e:
                        self._log.write_log(e, 2)
                    finally:
                        self._queue.append(i.IPv4Address)

                elif re.match('^.*Router.*$', i.Capabilities):
                    try:
                        self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoRouter', 5)
                        self.Routers.append(CiscoRouter(i.IPv4Address))
                        for ip in self.Routers[-1].IPv4Addresses:
                            self._queue.append(ip)
                        for n in self.Routers[-1].OSPFNeighbors:
                            self._log.write_log(f'Descending into recursion for {n.IPv4Address} from host {self.Routers[-1].Hostname}', 4)
                            for m in self.Routers[-1].Neighbors:
                                self._log.write_log(f'Descending into recursion for {m.IPv4Address} from host {self.Routers[-1].Hostname}', 4)
                                self._discover_network(m)
                            self._discover_network(n)
                    except LoginError as e:
                        self._log.write_log(e, 2)
                        self.bad.append(i)
                    except TimeoutError as e:
                        self._log.write_log(e, 2)
                    except CommandError as e:
                        self._log.write_log(e, 2)
                    finally:
                        self._queue.append(i.IPv4Address)

                else:
                    raise UnclassifiedError(f'Device {i.__repr__()} did not match any device filters', 2)

            elif type(i) is OSPFNeighbor:
                self._log.write_log(f'Appending {i.IPv4Address} to queue as CiscoRouter', 5)
                try:
                    self.Routers.append(CiscoRouter(i.IPv4Address))
                    for ip in self.Routers[-1].IPv4Addresses:
                        self._queue.append(ip)
                    for n in self.Routers[-1].OSPFNeighbors:
                        self._log.write_log(f'Descending into recursion for {n.IPv4Address} from host {self.Routers[-1].Hostname}', 4)
                        for m in self.Routers[-1].Neighbors:
                            self._log.write_log(f'Descending into recursion for {m.IPv4Address} from host {self.Routers[-1].Hostname}', 4)
                            self._discover_network(m)
                        self._discover_network(n)
                except LoginError as e:
                    self._log.write_log(e, 2)
                    self.bad.append(i)
                except TimeoutError as e:
                    self._log.write_log(e, 2)
                except CommandError as e:
                    self._log.write_log(e, 2)
                finally:
                    self._queue.append(i.IPv4Address)

    def connect(self, pat):
        for i in self.Switches:
            if re.search(pat, i.Hostname):
                i.Connection.control()

    def _generate_graph(self):
        raise NotImplementedError
