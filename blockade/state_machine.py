#
#  Copyright (c) 2017, Stardog Union. <http://stardog.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import traceback
from collections import namedtuple
import os
import threading

from blockade import errors


_logger = logging.getLogger(__name__)
StateTransition = namedtuple('StateTransition', 'state func error_state '
                                                'error_func')


class StateMachine(object):
    def __init__(self, start_state):
        self._state = start_state
        self._state_map = {}
        self._mutex = threading.Lock()

    def add_transition(
            self, start_state, event, new_state, transition_func,
            error_state, error_trans_func=None):
        if start_state not in self._state_map:
            self._state_map[start_state] = {}
        self._state_map[start_state][event] = StateTransition(
                new_state, transition_func, error_state, error_trans_func)

    def event_occurred(self, event, *args, **kwargs):
        try:
            state_trans = self._state_map[self._state][event]
        except KeyError:
            raise errors.BlockadeStateTransitionError(
                self._state, event,
                "It is invalid to have event %(event)s when in state "
                "%(current_state)s" % {"event": event, "current_state":
                                       self._state})
        _logger.debug(
                "Attempting to move from %(current_state)s to %(new_state)s "
                "because of event %(event)s" %
                {"event": event, "current_state": self._state,
                 "new_state": state_trans.state})
        self._mutex.acquire()
        try:
            _logger.debug(
                "Calling state transition function %(func_name)s" %
                {"func_name": state_trans.func.__name__})
            if state_trans.func is not None:
                try:
                    rc = state_trans.func(*args, **kwargs)
                    self._state = state_trans.state
                    return rc
                except BaseException as base_ex:
                    _logger.exception(
                        "Received an exception, going directly to state %s " %
                        state_trans.error_state)
                    if state_trans.error_func is not None:
                        try:
                            state_trans.error_func()
                        except BaseException as error_ex:
                            # there is nothing we can do here.  This is an
                            # exception coming from the users panic function
                            _logger.exception(
                                "Received an exception from the panic "
                                "handler %s" % state_trans.error_func.__name__)
                    self._state = state_trans.error_state
            else:
                self._state = state_trans.state
        finally:
            self._mutex.release()

    def get_state(self):
        return self._state

    def draw_mapping(self):
        print('digraph {' + os.linesep)
        print('node [shape=circle, style=filled fixedsize=true, fontsize=10, '
              'width=1.5];')
        for state in self._state_map:
            for e in self._state_map[state]:
                state_trans = self._state_map[state][e]
                if state_trans is not None:
                    print('    %(state)s  -> %(new_state)s [label=" %(event)s '
                          '", '
                          'fontsize=9];' %
                          {'state': state, 'event': e,
                           'new_state': state_trans.state})
                    print('    %(state)s  -> %(error_state)s '
                          '[label="ERROR", fontsize=9];' %
                          {'state': state,
                           'error_state': state_trans.error_state})
        print('}' + os.linesep)
