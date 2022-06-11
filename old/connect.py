#!/usr/bin/python3

from CiscoConnection import CiscoConnection
import sys

c = CiscoConnection(sys.argv[1])
c.control()
