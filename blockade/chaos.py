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


_logger = logging.getLogger(__name__)


def _flaky(blockade, targets, all_containers):
    target_names = [t.name for t in targets]
    _logger.info(
        "Chaos making the network drop packets for %s" % str(target_names))
    blockade.flaky(target_names)


def _partition(blockade, targets, all_containers):
    # Every target will end up alone in its own partition.  The point of this
    # is to allow the user control over the degree of chaos.  As an example
    # a user may only want to lock off at most 1 container at a time until
    # their application becomes more stable.  A separate event should be added
    # that creates random sets of partitions.
    parts = []
    for t in targets:
        parts.append([t.name])
    target_names = [t.name for t in targets]
    _logger.info("Putting %s in their own partitions: %s"
                 % (str(target_names), str(parts)))
    blockade.partition(parts)


def _slow(blockade, targets, all_containers):
    target_names = [t.name for t in targets]
    _logger.info("Chaos making the network slow for %s" % str(target_names))
    blockade.slow(target_names)


def _duplicate(blockade, targets, all_containers):
    target_names = [t.name for t in targets]
    _logger.info("Chaos adding duplicate packets for %s" % str(target_names))
    blockade.duplicate(target_names)


def _stop(blockade, targets, all_containers):
    target_names = [t.name for t in targets]
    _logger.info("Chaos stopping %s" % str(target_names))
    blockade.stop(target_names)


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
class BlockadeChaos(object):
    def __init__(self, blockade, blockade_name,
                 min_start_delay, max_start_delay,
                 min_run_time, max_run_time,
                 min_containers_at_once, max_containers_at_once,
                 event_set,
                 done_notification_func=None):
        valid_events = get_all_event_names()
        if event_set is None:
            event_set = valid_events
        else:
            for e in event_set:
                if e not in valid_events:
                    raise errors.BlockadeUsageError(
                            "%s is an unknown event." % e)
        self._blockade = blockade
        self._blockade_name = blockade_name
        self._start_min_delay = min_start_delay
        self._start_max_delay = max_start_delay
        self._run_min_time = min_run_time
        self._run_max_time = max_run_time
        self._min_containers_at_once = min_containers_at_once
        self._max_containers_at_once = max_containers_at_once
        self._chaos_events = event_set[:]
        self._done_notification_func = done_notification_func
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
                      min_containers_at_once=1,
                      max_containers_at_once=1,
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
            if event_set is not None:
                self._chaos_events = event_set
        finally:
            self._mutex.release()

    def _do_reset_all(self):
        container_list = self._blockade.status()
        container_names = [t.name for t in container_list]
        # greedily set everything to a happy state
        self._blockade.start(container_names)
        self._blockade.fast(container_names)
        self._blockade.join()

    def _do_blockade_event(self):
        container_list = self._blockade.status()
        random.shuffle(container_list)
        count = random.randint(self._min_containers_at_once,
                               self._max_containers_at_once)
        targets = container_list[:count]
        partition_list = []
        for t in targets:
            e = random.choice(self._chaos_events)
            if e == 'PARTITION':
                partition_list.append(t)
            else:
                _g_blockade_event_handlers[e](
                    self._blockade, [t], container_list)
        if len(partition_list) > 0:
            _partition(self._blockade, partition_list, container_list)

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

        self._sm.add_transition(
                ChaosStates.DONE, ChaosEvents.TIMER,
                ChaosStates.DONE,
                self._sm_stale_timer, ChaosStates.DONE)

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
                "Ending the degradation for blockade %s" % self._blockade_name)
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
        if self._done_notification_func is not None:
            self._done_notification_func()
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
            if self._done_notification_func is not None:
                self._done_notification_func()
        except BaseException as base_ex:
            _logger.warning("Failed to stop the timer %s" % str(base_ex))


class Chaos(object):
    def __init__(self):
        self._active_chaos = {}

    def new_chaos(self, blockade, name,
                  min_start_delay=30000, max_start_delay=300000,
                  min_run_time=30000, max_run_time=300000,
                  min_containers_at_once=1, max_containers_at_once=1,
                  event_set=None):
        if name in self._active_chaos:
            raise errors.BlockadeUsageError(
                    "Chaos is already associated with %s" % name)
        if event_set is None:
            event_set = get_all_event_names()
        bc = BlockadeChaos(
                blockade,
                name,
                min_start_delay=min_start_delay,
                max_start_delay=max_start_delay,
                min_run_time=min_run_time,
                max_run_time=max_run_time,
                min_containers_at_once=min_containers_at_once,
                max_containers_at_once=max_containers_at_once,
                event_set=event_set)
        self._active_chaos[name] = bc
        return bc

    def update_options(self, name,
                       min_start_delay=None, max_start_delay=None,
                       min_run_time=None, max_run_time=None,
                       min_containers_at_once=None,
                       max_containers_at_once=None,
                       event_set=None):
        chaos_b = self._get_chaos_obj(name)
        chaos_b.change_events(
                min_start_delay=min_start_delay,
                max_start_delay=max_start_delay,
                min_run_time=min_run_time,
                max_run_time=max_run_time,
                min_containers_at_once=min_containers_at_once,
                max_containers_at_once=max_containers_at_once,
                event_set=event_set)

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
            except BaseException as bex:
                _logger.warn(str(bex))
            chaos_b.delete()
