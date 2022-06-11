#!/usr/bin/env python3

from CiscoSwitch import CiscoSwitch
from CiscoModels import Trunk
from sys import argv

def _help():
    print('''
        USAGE: ./dot1x.py <ip_of_switch> <enable|disable>
    ''')

c = None

try:
    print(f'Trying ip {argv[1]}')
    c = CiscoSwitch(argv[1])
    print(c.Connection.command('sh run int Gi1/0/1'))

    if argv[2] == 'disable':
        for i in c.Interfaces:
            if type(i) is not Trunk:
                print(f'Operating on {c.Hostname} interface {i.Name}')
                c.Connection.configure(
                    'conf t',
                    f'int {i.Name}',
                    'no authentication event fail action next-method',
                    'no authentication host-mode multi-domain',
                    'no authentication order dot1x mab',
                    'no authentication priority dot1x mab',
                    'no authentication port-control auto',
                    'no authentication periodic',
                    'no authentication violation replace',
                    'no mab',
                    'no snmp trap mac-notification change added',
                    'no dot1x pae authenticator',
                    'no dot1x timeout tx-period 1',
                    'no dot1x max-reauth-req 1',
                    'end'
                )
        c.Connection.command('wr')
        c.Connection.close()
        print(c.Connection.command('sh run int Gi1/0/1'))

    elif argv[2] == 'enable':
        for i in c.Interfaces:
            if type(i) is not Trunk:
                print(f'Operating on {c.Hostname} interface {i.Name}')
                c.Connection.configure(
                    'conf t',
                    f'int {i.Name}',
                    'authentication event fail action next-method',
                    'authentication host-mode multi-domain',
                    'authentication order dot1x mab',
                    'authentication priority dot1x mab',
                    'authentication port-control auto',
                    'authentication periodic',
                    'authentication violation replace',
                    'mab',
                    'snmp trap mac-notification change added',
                    'dot1x pae authenticator',
                    'dot1x timeout tx-period 1',
                    'dot1x max-reauth-req 1',
                    'end'
                )
        c.Connection.commands('wr')
        c.Connection.close()

    else:
        _help()

except Exception as e:
    print(e)
    _help()
