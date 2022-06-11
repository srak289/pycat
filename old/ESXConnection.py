import os
from base64 import b64decode
from SSHConnection import SSHConnection
from SSHConnectionError import *

class ESXConnection(SSHConnection):
    def __init__(self, host):
        self._pw = None
        path = os.path.abspath(os.path.dirname(__file__))
        
        with open(os.path.join(path, '.esxpw'),'rb') as f:
            self._pw = f.read()[2:-2]

        super().__init__(host, "root", self._pw, '^.*]', True, 4)

    def control(self):
        '''
            This method will allow user interaction to the connection and will spawn a connection
            if none exists.
        '''
        if self._child is None:
            try:
                self.connect()
            except LoginError as e:
                raise e

        self._child.interact()
        
        if self._child is not None:
            self.close()
    

    def copy(self, src, dest="~/"):
        if self._child is None:
            self._child = spawn(f"scp {src} {self._user}@{self._host}:{dest}")
            self._passwd_loop()
        else:
            raise ConnectedError(self._host)

    def retreive(self, src, dest="."):
        if self._child is None:
            self._child = spawn(f"scp {self._user}@{self._host}:{src} {dest}")
            self._passwd_loop()
        else:
            raise ConnectedError(self._host)

