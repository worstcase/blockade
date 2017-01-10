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
import random
import threading

from blockade import errors
from blockade import state_machine
from blockade.api.manager import BlockadeManager


_logger = logging.getLogger(__file__)


def _flaky(blockade, targets, all_containers):
    _logger.debug(
        "Chaos making the network drop packets for %s" % str(targets))
    blockade.flaky([t.name for t in targets])


def _partition(blockade, targets, all_containers):
    # Every target will end up alone in its own partition.  The point of this
    # is to allow the user control over the degree of chaos.  As an example
    # a user may only want to lock off at most 1 container at a time until
    # their application becomes more stable.  A separate event should be added
    # that creates random sets of partitions.
    remaining = all_containers[:]
    parts = []
    for t in targets:
        remaining.remove(t)
        parts.append([t])
    parts.append(remaining)
    blockade.partition(parts)


def _slow(blockade, targets, all_containers):
    _logger.debug("Chaos making the network slow for %s" % str(targets))
    blockade.slow([t.name for t in targets])


def _duplicate(blockade, targets, all_containers):
    _logger.debug("Chaos adding duplicate packets for %s" % str(targets))
    blockade.duplicate([t.name for t in targets])


def _stop(blockade, targets, all_containers):
    _logger.debug("Chaos stoping %s" % str(targets))
    blockade.stop([t.name for t in targets])


_g_blockade_event_handlers = {
    'PARTITION': _partition,
    'STOP': _stop,
    'FLAKY': _flaky,
    'SLOW': _slow,
    'DUPLICATE': _duplicate,
}


def get_all_event_names():
    return list(_g_blockade_event_handlers.keys())


class ChaosStates(object):
    NEW = "NEW"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"
    FAILED_WHILE_HEALTHY = "FAILED_WHILE_HEALTHY"
    FAILED_WHILE_DEGRADED = "FAILED_WHILE_DEGRADED"
    DONE = "DONE"


class ChaosEvents(object):
    START = "START"
    STOP = "STOP"
    TIMER = "TIMER"
    DELETE = "DELETE"


# This class represents any one blockades
class _BlockadeChaos(object):
    def __init__(self, blockade_name,
                 min_start_delay, max_start_delay,
                 min_run_time, max_run_time,
                 min_containers_at_once, max_containers_at_once,
                 min_events_at_once, max_events_at_once,
                 event_set):
        self._blockade_name = blockade_name
        self._start_min_delay = min_start_delay
        self._start_max_delay = max_start_delay
        self._run_min_time = min_run_time
        self._run_max_time = max_run_time
        self._min_containers_at_once = min_containers_at_once
        self._max_containers_at_once = max_containers_at_once
        self._min_events_at_once = min_events_at_once
        self._max_events_at_once = max_events_at_once
        self._chaos_events = event_set[:]
        self._timer = None
        self._mutex = threading.Lock()
        self._create_state_machine()
        self._mutex.acquire()
        try:
            self._sm.event_occurred(ChaosEvents.START)
        finally:
            self._mutex.release()

    def change_events(self,
                      min_start_delay=None, max_start_delay=None,
                      min_run_time=None, max_run_time=None,
                      min_containers_at_once=None, max_containers_at_once=None,
                      min_events_at_once=None, max_events_at_once=None,
                      event_set=None):
        self._mutex.acquire()
        try:
            if min_start_delay is not None:
                self._start_min_delay = min_start_delay
            if max_start_delay is not None:
                self._start_max_delay = max_start_delay
            if min_run_time is not None:
                self._run_min_time = min_run_time
            if max_run_time is not None:
                self._run_max_time = max_run_time
            if min_containers_at_once is not None:
                self._min_containers_at_once = min_containers_at_once
            if max_containers_at_once is not None:
                self._max_containers_at_once = max_containers_at_once
            if min_events_at_once is not None:
                self._min_events_at_once = min_events_at_once
            if max_events_at_once is not None:
                self._max_events_at_once = max_events_at_once
            if event_set is not None:
                self._chaos_events = event_set
        finally:
            self._mutex.release()

    def _do_reset_all(self):
        blockade = BlockadeManager.get_blockade(self._blockade_name)
        container_list = blockade.status()
        container_names = [t.name for t in container_list]
        # greedily set everything to a happy state
        blockade.start(container_names)
        blockade.fast(container_names)
        blockade.join()

    def _do_blockade_event(self):
        blockade = BlockadeManager.get_blockade(self._blockade_name)

        container_list = blockade.status()
        random.shuffle(container_list)
        count = random.randint(self._min_containers_at_once,
                               self._max_containers_at_once)
        targets = container_list[:count]
        events_at_once = random.randint(self._min_events_at_once,
                                        self._max_events_at_once)
        random.shuffle(self._chaos_events)
        events = self._chaos_events[:events_at_once]
        for e in events:
            try:
                _g_blockade_event_handlers[e](
                        blockade, targets, container_list)
            except KeyError:
                raise errors.BlockadeUsageError("Invalid event %s" % e)

    def print_state_machine(self):
        self._sm.draw_mapping()

    # state machine logic
    def _create_state_machine(self):
        self._sm = state_machine.StateMachine(ChaosStates.NEW)
        self._sm.add_transition(
            ChaosStates.NEW, ChaosEvents.START, ChaosStates.HEALTHY,
            self._sm_start, ChaosStates.FAILED_WHILE_HEALTHY)

        self._sm.add_transition(
                ChaosStates.HEALTHY, ChaosEvents.TIMER,
                ChaosStates.DEGRADED,
                self._sm_to_pain, ChaosStates.FAILED_WHILE_HEALTHY,
                error_trans_func=self._sm_panic_handler_stop_timer)
        self._sm.add_transition(
                ChaosStates.HEALTHY, ChaosEvents.STOP,
                ChaosStates.STOPPED,
                self._sm_stop_from_no_pain, ChaosStates.FAILED_WHILE_HEALTHY,
                error_trans_func=self._sm_panic_handler_stop_timer)

        self._sm.add_transition(
                ChaosStates.DEGRADED, ChaosEvents.TIMER,
                ChaosStates.HEALTHY,
                self._sm_relieve_pain, ChaosStates.FAILED_WHILE_DEGRADED,
                error_trans_func=self._sm_panic_handler_stop_timer)
        self._sm.add_transition(
                ChaosStates.DEGRADED, ChaosEvents.STOP,
                ChaosStates.STOPPED,
                self._sm_stop_from_pain, ChaosStates.FAILED_WHILE_DEGRADED,
                error_trans_func=self._sm_panic_handler_stop_timer)

        self._sm.add_transition(
                ChaosStates.STOPPED, ChaosEvents.START,
                ChaosStates.HEALTHY,
                self._sm_start, ChaosStates.FAILED_WHILE_HEALTHY)
        self._sm.add_transition(
                ChaosStates.STOPPED, ChaosEvents.DELETE,
                ChaosStates.DONE,
                self._sm_cleanup, ChaosStates.FAILED_WHILE_HEALTHY)

        # places where a stale time is possible
        self._sm.add_transition(
                ChaosStates.STOPPED, ChaosEvents.TIMER,
                ChaosStates.STOPPED,
                self._sm_stale_timer, ChaosStates.STOPPED)
        self._sm.add_transition(
                ChaosStates.FAILED_WHILE_DEGRADED, ChaosEvents.TIMER,
                ChaosStates.FAILED_WHILE_DEGRADED,
                self._sm_stale_timer, ChaosStates.FAILED_WHILE_DEGRADED)
        self._sm.add_transition(
                ChaosStates.FAILED_WHILE_DEGRADED, ChaosEvents.DELETE,
                ChaosStates.DONE,
                self._sm_cleanup, ChaosStates.FAILED_WHILE_DEGRADED)

        self._sm.add_transition(
                ChaosStates.FAILED_WHILE_HEALTHY, ChaosEvents.TIMER,
                ChaosStates.FAILED_WHILE_HEALTHY,
                self._sm_stale_timer, ChaosStates.FAILED_WHILE_HEALTHY)
        self._sm.add_transition(
                ChaosStates.FAILED_WHILE_HEALTHY, ChaosEvents.DELETE,
                ChaosStates.DONE,
                self._sm_cleanup, ChaosStates.FAILED_WHILE_HEALTHY)

    def status(self):
        self._mutex.acquire()
        try:
            return {"state": self._sm.get_state()}
        finally:
            self._mutex.release()

    def event_timeout(self):
        self._mutex.acquire()
        try:
            self._sm.event_occurred(ChaosEvents.TIMER)
        finally:
            self._mutex.release()

    def start(self):
        self._mutex.acquire()
        try:
            self._sm.event_occurred(ChaosEvents.START)
        finally:
            self._mutex.release()

    def stop(self):
        self._mutex.acquire()
        try:
            self._sm.event_occurred(ChaosEvents.STOP)
        finally:
            self._mutex.release()

    def delete(self):
        self._mutex.acquire()
        try:
            self._sm.event_occurred(ChaosEvents.DELETE)
        finally:
            self._mutex.release()

    def _sm_start(self, *args, **kwargs):
        """
        Start the timer waiting for pain
        """
        millisec = random.randint(self._start_min_delay, self._start_max_delay)
        self._timer = threading.Timer(millisec / 1000.0, self.event_timeout)
        self._timer.start()

    def _sm_to_pain(self, *args, **kwargs):
        """
        Start the blockade event
        """
        _logger.info("Starting chaos for blockade %s" % self._blockade_name)
        self._do_blockade_event()
        # start the timer to end the pain
        millisec = random.randint(self._run_min_time, self._run_max_time)
        self._timer = threading.Timer(millisec / 1000.0, self.event_timeout)
        self._timer.start()

    def _sm_stop_from_no_pain(self, *args, **kwargs):
        """
        Stop chaos when there is no current blockade operation
        """
        # Just stop the timer.  It is possible that it was too late and the
        # timer is about to run
        _logger.info("Stopping chaos for blockade %s" % self._blockade_name)
        self._timer.cancel()

    def _sm_relieve_pain(self, *args, **kwargs):
        """
        End the blockade event and return to a steady state
        """
        _logger.info(
                "Ending the degration for blockade %s" % self._blockade_name)
        self._do_reset_all()
        # set a timer for the next pain event
        millisec = random.randint(self._start_min_delay, self._start_max_delay)
        self._timer = threading.Timer(millisec/1000.0, self.event_timeout)
        self._timer.start()

    def _sm_stop_from_pain(self, *args, **kwargs):
        """
        Stop chaos while there is a blockade event in progress
        """
        _logger.info("Stopping chaos for blockade %s" % self._blockade_name)
        self._do_reset_all()

    def _sm_cleanup(self, *args, **kwargs):
        """
        Delete all state associated with the chaos session
        """
        self._timer.cancel()

    def _sm_stale_timer(self, *args, **kwargs):
        """
         This is used when a cancel was called right before the timer fired but
         after it was too late to cancel the timer.
        """
        _logger.debug("Stale timer event.  Interesting but ignorable.")

    def _sm_panic_handler_stop_timer(self):
        try:
            self._timer.cancel()
        except BaseException as base_ex:
            _logger.warning("Failed to stop the timer %s" % base_ex.message)


class Chaos(object):
    def __init__(self):
        self._active_chaos = {}

    def new_chaos(self, name,
                  min_start_delay=30000, max_start_delay=300000,
                  min_run_time=30000, max_run_time=300000,
                  min_containers_at_once=1, max_containers_at_once=1,
                  min_events_at_once=1, max_events_at_once=1,
                  event_set=None):
        if name in self._active_chaos:
            raise errors.BlockadeUsageError(
                    "Chaos is already associated with %s" % name)
        if event_set is None:
            event_set = get_all_event_names()
        bc = _BlockadeChaos(
                name,
                min_start_delay=min_start_delay,
                max_start_delay=max_start_delay,
                min_run_time=min_run_time,
                max_run_time=max_run_time,
                min_containers_at_once=min_containers_at_once,
                max_containers_at_once=max_containers_at_once,
                min_events_at_once=min_events_at_once,
                max_events_at_once=max_events_at_once,
                event_set=event_set)
        self._active_chaos[name] = bc
        return bc

    def update_options(self, name,
                       min_start_delay=None, max_start_delay=None,
                       min_run_time=None, max_run_time=None,
                       min_containers_at_once=None,
                       max_containers_at_once=None,
                       min_events_at_once=None, max_events_at_once=None,
                       event_set=None):
        try:
            if event_set is None:
                event_set = get_all_event_names()
            chaos_b = self._active_chaos[name]
            chaos_b.change_events(
                    min_start_delay=min_start_delay,
                    max_start_delay=max_start_delay,
                    min_run_time=min_run_time,
                    max_run_time=max_run_time,
                    min_containers_at_once=min_containers_at_once,
                    max_containers_at_once=max_containers_at_once,
                    min_events_at_once=min_events_at_once,
                    max_events_at_once=max_events_at_once,
                    event_set=event_set)
        except KeyError:
            raise errors.BlockadeUsageError(
                    "Chaos is not associated with %s" % name)

    def _get_chaos_obj(self, name):
        try:
            return self._active_chaos[name]
        except KeyError:
            raise errors.BlockadeUsageError(
                    "Chaos is not associated with %s" % name)

    def start(self, name):
        chaos_b = self._get_chaos_obj(name)
        try:
            chaos_b.start()
        except errors.BlockadeStateTransitionError as bste:
            raise errors.BlockadeUsageError(
                "Chaos cannot be started when in the %s state" % bste.state)

    def stop(self, name):
        chaos_b = self._get_chaos_obj(name)
        try:
            chaos_b.stop()
        except errors.BlockadeStateTransitionError as bste:
            raise errors.BlockadeUsageError(
                "Chaos cannot be stopped when in the %s state" % bste.state)

    def delete(self, name):
        chaos_b = self._get_chaos_obj(name)
        try:
            chaos_b.delete()
            del self._active_chaos[name]
        except errors.BlockadeStateTransitionError as bste:
            raise errors.BlockadeUsageError(
                "Chaos cannot be deleted when in the %s state" % bste.state)

    def status(self, name):
        chaos_b = self._get_chaos_obj(name)
        return chaos_b.status()

    def exists(self, name):
        return name in self._active_chaos

    def shutdown(self):
        for c in self._active_chaos:
            chaos_b = self._get_chaos_obj(c)
            try:
                chaos_b.stop()
            except:
                pass
            chaos_b.delete()
