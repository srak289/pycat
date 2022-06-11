from SSHConnection import *
from SSHConnectionError import *
from pexpect import TIMEOUT
import os

class CiscoConnection(SSHConnection):
    def __init__(self, host):
        self._pw = None

        path = os.path.abspath(os.path.dirname(__file__))
        
        #with open(os.path.join(path, '.ciscopw'),'r') as f:
        #    self._pw = f.read()[1:-2]
 
        super().__init__(host, "cisco", "cisco", '^.*#.*$', True, 4)
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

    # do we care
#                    for i in self._get_before().split('\r\n'):
#                        if re.search('Invalid', i):
#                            raise CommandError(self._host, c)
                    pass
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
