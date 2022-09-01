import time, os

class Logger:
    def __init__(self, host, verbosity, binary=True, fg=False):
        self._prefix = [
            "   OFF:     ",
            "   FATAL:   ",
            "   ERROR:   ",
            "   WARNING: ",
            "   INFO:    ",
            "   DEBUG:   ",
            "   TRACE:   ",
            "   ALL:     "
        ]

        self.OFF = 0
        self.FATAL = 1
        self.ERROR = 2
        self.WARNING = 3
        self.INFO = 4
        self.DEBUG = 5
        self.TRACE = 6
        self.ALL = 7

        self._host = host
        Y, M, D, H, m, s, _, _, _ = time.localtime()
        self._date = '_'+str(Y)+'-'+str(M)+'-'+str(D)+'R'+str(H)+':'+str(m)+':'+str(s)
        self._log_ext = '.log'
        self._log_name = f'{self._host}{self._date}{self._log_ext}'
        self._log_dir = os.getcwd()+'/log'
        self._lv = verbosity
        self._log = None
        self._binary = binary
        self._fg = fg

    def is_open(self):
        '''
            Returns whether or not the log file is open for writing.
        '''
        if self._log == None:
            return False
        return self._log.closed

    def open_log(self):
        '''
            Checks for logging directory (currently ./log) creates it.
            Changes directory. Opens log file for appending or creates it.
        '''
        # This is nasty but for now we check if the current directory
        # has the word 'log' in it.
        if os.getcwd() != self._log_dir and os.getcwd().find('log') == -1:
            if not os.path.exists(self._log_dir):
                os.mkdir(self._log_dir)
            os.chdir(self._log_dir)
        if os.path.exists(self._log_name):
            self._log = open(self._log_name,'ab' if self._binary else 'a')
        else:
            self._log = open(self._log_name,'wb' if self._binary else 'w')

    def close_log(self):
        '''
            Closes the logfile.
        '''
        self._log.close()

    def get_log_handle(self):
        '''
            Returns the logfile handle for the pexpect child to write to.
        '''
        if self._log:
            return self._log

    def write_log(self, m, v):
        '''
            Writes log messages and data to log files with prefixes depending on the verbosity specified.
        '''
        if self._lv >= v:
            t = f'{self._prefix[v]}{m}'
            if self._fg:
                print(t.encode() if self._binary else t)
            else:
                self._log.write(t.encode() if self._binary else t)

