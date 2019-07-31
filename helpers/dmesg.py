""" Helper for Tempesta system log operations."""

from __future__ import print_function
from contextlib import contextmanager
import re
import time
from . import error, remote, tf_cfg

__author__ = 'Tempesta Technologies, Inc.'
__copyright__ = 'Copyright (C) 2018-2019 Tempesta Technologies, Inc.'
__license__ = 'GPL2'


class DmesgFinder(object):
    """dmesg helper class. """

    def __init__(self):
        self.node = remote.tempesta
        self.log = ''
        self.start_time = float(self.node.run_cmd("date +%s.%N")[0])
        # Suppress net ratelimiter to have all the messages in dmesg.
        self.msg_cost = self.node.run_cmd("sysctl net.core.message_cost")[0]
        self.node.run_cmd("sysctl -w net.core.message_cost=0")

    def __del__(self):
        """ Restore net.core.message_cost to not to flood the log on
        performance tests.
        """
        self.node.run_cmd("sysctl -w " + self.msg_cost.replace(' ', ''))

    def update(self):
        """Get log from the last run."""
        cmd = "journalctl -k -o cat --since=@{:.6f}".format(self.start_time)
        self.log, _ = self.node.run_cmd(cmd)

    def show(self):
        """Show tempesta system log."""
        print(self.log)

    def _warn_count(self, warn_str):
        match = re.findall(warn_str, self.log)
        return len(match)

    def warn_count(self, warn_str):
        """Count occurrences of given string in system log. Normally used to
        count warnings during test.
        """
        self.update()
        return self._warn_count(warn_str)

    def msg_ratelimited(self, msg):
        """ Like previos, but returns binary found/not-found status and takes
        care about ratelimited messages. Returns 0 on success, -1 if msg wasn't
        found and 1 if there are no msg and the log is ratelimited.
        """
        self.update()
        ratelimited = False
        for line in self.log.split('\n'):
            if line.find(msg) >= 0:
                return 0
            if re.findall('net_ratelimit: [\d]+ callbacks suppressed', line):
                ratelimited = True
        return 1 if ratelimited else -1


WARN_GENERIC = 'Warning: '
WARN_SPLIT_ATTACK = 'Warning: Paired request missing, HTTP Response Splitting attack?'


@contextmanager
def wait_for_msg(msg, timeout, permissive):
    """ Execute a code and waith for the messages in dmesg with the timeout.
    Dmesg may rate limit some messages and our message might be skipped in the
    log. Permissive mode assumes that if msg wasn't found and the log was
    rate limited, then the message was one of the skipped records.
    """
    dmesg = DmesgFinder()

    yield

    dmesg.update()
    ratelimited = False
    t_start = time.time()
    while t_start + timeout >= time.time():
        res = dmesg.msg_ratelimited(msg)
        if res == 0:
            return
        elif res == 1:
            ratelimited = True
        time.sleep(0.01)
    if not permissive:
        raise error.Error("dmesg wait for message timeout")
    if not ratelimited:
        # Ratelimiting messages appear only on next logging operation if
        # previous records were suppressed. This means that if some operation
        # produces a lot of logging and last log records are dropped, then we
        # learn it only with next log record, i.e. next operation.
        # The only good way to fix this is to properly setup system logger,
        # otherwise we either spend too much time on timeouts or observe
        # spurious exceptions.
        tf_cfg.dbg(2, 'No "%s" log record and no ratelimiting' % msg)
