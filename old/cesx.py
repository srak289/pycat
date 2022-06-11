#!/usr/bin/python3

from ESXConnection import ESXConnection
from sys import argv

ESXConnection(argv[1]).control()
