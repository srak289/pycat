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
