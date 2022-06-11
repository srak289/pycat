from pexpect import *
from base64 import b64decode
from ipaddress import *
from socket import *
from pycat.logger import Logger
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
                self.IPv4Address = ip_address(socket.gethostbyname_ex(self._host)[2][0])
            except socket.gaierror:
                raise UnreachableError("No host with name {self._host}")
        self._user = user
        self._passwd = b64decode(passwd).decode('ASCII')
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
        self._child.sendline("exit")
        self._child.expect(EOF)
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

    def connect(self):
        if self._log:
            self._log.open_log()
            self._log.write_log(f'Spawning child ssh {self._user}@{self._host}', 4)
        self._child = spawn(f'ssh -o UserKnownHostsFile={self._known_hosts} {self._user}@{self._host}')

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

class CiscoConnection(SSHConnection):
    def __init__(self, host):
        self._pw = None
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ciscopw')
        with open(path, 'r') as f:
            self._pw = f.read()[1:-2]
 
        super().__init__(host, "svc.nccsw.ngnh", self._pw, '^.*#.*$', True, 4)
        self._more = " --More-- "
        self._error = "% Invalid Command at '^' marker"
        self._hostname = b''

        # This is nasty but we didn't want the hostname showing up in output anymore
        self._hostname = bytes(self.command('sh run | i hostname').split()[1]+'#', 'ASCII')

        # This will prevent the switch from locking the ssh connection after rapid logins
        # Possibly needs to be set for every new ssh session so it's here for now
        self.configure(
            "conf t",
            "no login block-for 300 attempts 5 within 50",
            "end"
        )

    def command(self, cmd):
        '''
            This method is for retreiving information from the connection. It will automatically page
            the terminal until the prompt returns and strip unnessary lines/symbols from the data returned.
        '''
        stripped = lambda s: "".join(i for i in s if ord(i) != 8)
        globbing = False
        glob = b''

        if self._child is None:
            try:
                self.connect()
            except LoginError as e:
                raise e

        self._child.sendline(cmd)
        while True:
            try:
                i = self._child.expect([self._prompt, self._more, EOF])
                if i == 0:
                    # if we are globbing we need to append child.after
                    # to get the rest of the data
                    if globbing:
                        glob += self._child.after
                    break;
                elif i == 1:
                    globbing = True
                    self._child.send(" ")
                    glob += self._child.before
                elif i == 2:
                    # We should not arrive here because cisco returns to a prompt
                    raise TerminatedError(self._host)
                    break; 
            except TIMEOUT:
                raise TimeoutError(self._host)
        if globbing:
            self._child.before = glob

        # The glob is not returned until the last command is sent, for most sub menu configuration this does not matter

        # This is also kind of nasty but we didn't want the sent command showing up in the output anymore
        self._before = self._child.before.strip(bytes(cmd, 'ASCII')).strip(self._hostname)
        self._after = self._child.after.strip(bytes(cmd, 'ASCII')).strip(self._hostname)

#        if globbing:
#            if re.search('Invalid input', self._get_before()):
#                raise CommandError(self._host, cmd) 
#
#            return self._get_before()
#    
#        else:
#            if re.search('Invalid input', self._get_after()):
#                raise CommandError(self._host, cmd) 
#
#            return self._get_after()

        return self._get_before() if globbing else self._get_after()

    def configure(self, *cmd):
        '''
            This method will run a series of commands given as a list of strings to '*cmd'.
            It will automatically spawn a child connection if none exists but it will not
            close on its own.
        '''
        if self._child is None:
            try:
                self.connect()
            except LoginError as e:
                raise e

        for c in cmd:
            self._child.sendline(c)
            try:
                i = self._child.expect([self._prompt, self._error, EOF])
                if i == 0:
                        #
                        # This will still not catch command errors..we need to inspect 
                        # child.before or after will contain the Invalid indicator
                        # Cisco will still return to the prompt as normal even if the command is rejected
                        # We will need to add this to self.command as well
                        #
                    for i in self._get_before().split('\r\n'):
                        if re.search('Invalid', i):
                            raise CommandError(self._host, c)
                elif i == 1:
                    raise CommandError(host, cmd)
                elif i == 2:
                    # We should not arrive here because cisco returns to a prompt
                    raise TerminatedError(self._host)
                    break; 
            except TIMEOUT:
                raise TimeoutError(self._host)

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

    def _get_before(self):
        '''
            This method returns an ASCII version of the child's 'before' binary stream after stripping all 
            BACKSPACE characters from the data.
        '''
        return "".join( s for s in self._before.decode('ASCII') if ord(s) != 8 )

    def _get_after(self):
        '''
            This method returns an ASCII version of the child's 'after' binary stream'
        '''
        return self._after.decode('ASCII')

    def __repr__(self):
        return f'CiscoConnection("{self._host}")'

class ESXConnection(SSHConnection):
    def __init__(self, host):
        self._pw = None
        with open('.esxpw', 'r') as f:
            self._pw = f.read()[1:-2]

        super().__init__(host, '^.*]', "root", self._pw, False)

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

class ConnectionError(Exception):
    def __init__(self, msg):
        super(ConnectionError, self).__init__(f'{msg}')

class TerminatedError(ConnectionError):
    def __init__(self, msg):
        super(ConnectionError, self).__init__(f'Connection unexpectedly closed by host {msg}')

class ConnectedError(ConnectionError):
    def __init__(self, host):
        super(ConnectedError, self).__init__(f'You are already connected to {host}')

class HostKeyError(ConnectionError):
    def __init__(self, host):
        super(HostKeyError, self).__init__(f'Host key verification failed for {host}')

class LoginError(ConnectionError):
    def __init__(self, host):
        super(LoginError, self).__init__(f'Bad credentials for {host}')

class UnreachableError(ConnectionError):
    def __init__(self, host):
        super(UnreachableError, self).__init__(f'Unable to reach {host}')

class TimeoutError(ConnectionError):
    def __init__(self, host):
        super(TimeoutError, self).__init__(f'Connection timed out for {host}')

class BackupError(Exception):
    def __init__(self, msg):
        super(BackupError, self).__init__(f'{msg}')

class BackupFailure(BackupError):
    def __init__(self, host):
        super(BackupFailure, self).__init__(f'Backup failed for {host}')

class CiscoError(Exception):
    def __init__(self, msg):
        super(CiscoError, self).__init__(f'{msg}')

class CommandError(CiscoError):
    def __init__(self, host, cmd):
        super(CommandError, self).__init__(f'{host} refused command "{cmd}"')
