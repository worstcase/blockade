##############################################################################
#
# Copyright Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import time


class Wait(object):

    class TimeOutWaitingFor(Exception):
        "A test condition timed out"

    timeout = 9
    wait = .01

    def __init__(self, timeout=None, wait=None, exception=None,
                 getnow=(lambda: time.time), getsleep=(lambda: time.sleep)):

        if timeout is not None:
            self.timeout = timeout

        if wait is not None:
            self.wait = wait

        if exception is not None:
            self.TimeOutWaitingFor = exception

        self.getnow = getnow
        self.getsleep = getsleep

    def __call__(self, func=None, timeout=None, wait=None, message=None):
        if func is None:
            return lambda func: self(func, timeout, wait, message)

        if func():
            return

        now = self.getnow()
        sleep = self.getsleep()
        if timeout is None:
            timeout = self.timeout
        if wait is None:
            wait = self.wait
        wait = float(wait)

        deadline = now() + timeout
        while 1:
            sleep(wait)
            if func():
                return
            if now() > deadline:
                raise self.TimeOutWaitingFor(
                    message or
                    getattr(func, '__doc__') or
                    getattr(func, '__name__')
                )

wait = Wait()