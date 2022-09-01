from pexpect import *
from base64 import b64decode
from ipaddress import *
from socket import *
from SSHConnectionError import *
from Logger import Logger
import re, os

class SSHConnection:
    def __init__(self, host, user, passwd, prompt, log=False, verbosity=0):
        self._host = host
        if self._host == '':
            raise ValueError('self._host cannot be ""')
        self._verbosity = verbosity
        try:
            # We should check to make sure we can communicate with the ip address
            self.IPv4Address = ip_address(self._host)
        except ValueError as e:
            try:
                self.IPv4Address = ip_address(gethostbyname_ex(self._host)[2][0])
            except gaierror:
                raise UnreachableError("No host with name {self._host}")
        self._user = user
        self._passwd = b64decode(bytes(passwd, 'ascii')).decode('ASCII')
        self._prompt = prompt
        if log:
            self._log = Logger(self._host, self._verbosity)
        else:
            self._log = None
        self._known_hosts = './known_hosts'
        self._child = None
        self._before = None
        self._after = None
        
    def close(self):
        try:
            self._child.sendline("exit")
            self._child.expect(EOF)
        except TIMEOUT as e:
            self._log.write_log(f'Connection timed out for host {self._host}', 2)
            raise TimeoutError(self._host)
        self._child = None
        if self._log is not None:
            self._log.close_log()
        
    def command(self, cmd):
        if self._child is not None:
            self._log.write_log(f'Sending command {cmd}', 4)
            self._child.sendline(cmd)
            self._child.expect([self._prompt, EOF])
        else:
            raise ConnectionError("Child is None")
        return self._get_after()

    def connect(self):
        if self._log:
            self._log.open_log()
            self._log.write_log(f'Spawning child ssh {self._user}@{self._host}', 4)
        # this should be a dict of ops...this will make ESX sad
        self._child = spawn(f'ssh -oKexAlgorithms=diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1 -oUserKnownHostsFile={self._known_hosts} {self._user}@{self._host}')

        if self._log:
            #fout = open(f"{self._host}.txt","ab")
            self._child.logfile_read = self._log.get_log_handle()

        while True:
            self._log.write_log(f'Trying login as {self._user}@{self._host}', 4)
            try:
                i = self._child.expect(['Host key verification failed.',
                                    'Are you sure you want to continue connecting (yes/no)?',
                                    'Password:',
                                    '^.*Password:',
                                    '^.*password:',
                                    self._prompt,
                                    EOF])
                if i == 0:
                    self._log.write_log(f'Host key verification failed for {self._host}', 3)
                    #raise HostKeyError(self._host)
                    os.system(f'ssh-keygen -R {self._host} -f {self._known_hosts}')
                elif i == 1:
                    self._child.sendline("yes")
                elif i == 2 or i == 3 or i == 4:
                    self._child.sendline(self._passwd)
                    self._log.write_log(f'Sending password to host {self._host}', 4)
                elif i == 5:
                    self._log.write_log(f'Found prompt for host {self._host}', 4)
                    break;
                elif i == 6:
                    raise LoginError(self._host)
                else:
                    self._log.write(f'Unexpected EOF while connecting to {self._host}', 2)
                    raise TerminatedError(self._host)
            except TIMEOUT as e:
                self._log.write_log(f'Connection timed out for host {self._host}', 2)
                raise TimeoutError(self._host)

    def _get_before(self):
        return self._child.before.decode('ASCII')

    def _get_after(self):
        return self._child.after.decode('ASCII')
