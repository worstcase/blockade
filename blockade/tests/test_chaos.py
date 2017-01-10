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
import time
import unittest

from mock import patch, MagicMock

from blockade import errors
from blockade import chaos
from blockade.api.manager import BlockadeManager


class ChaosTest(unittest.TestCase):

    def setUp(self):
        self.chaos = chaos.Chaos()

    def tearDown(self):
        block_mock = MagicMock()
        with patch.object(BlockadeManager, 'get_blockade',
                          return_value=block_mock):
            self.chaos.shutdown()

    def test_basic_start_stop_destroy(self):
        name = "aname"
        block_mock = MagicMock()
        with patch.object(BlockadeManager, 'get_blockade',
                          return_value=block_mock):
            self.chaos.new_chaos(name)
            status = self.chaos.status(name)
            self.assertIn(status['state'], ['HEALTHY', 'DEGRADED'])
            self.chaos.stop(name)
            status = self.chaos.status(name)
            self.assertEqual(status['state'], 'STOPPED')
            self.chaos.delete(name)

    def test_start_chaos_twice(self):
        name = "aname"
        block_mock = MagicMock()
        with patch.object(
                BlockadeManager, 'get_blockade', return_value=block_mock):
            self.chaos.new_chaos(name)
            with self.assertRaises(errors.BlockadeUsageError):
                self.chaos.new_chaos(name)

    def test_delete_running_chaos(self):
        name = "aname"
        block_mock = MagicMock()
        with patch.object(
                BlockadeManager, 'get_blockade', return_value=block_mock):
            self.chaos.new_chaos(name)
            with self.assertRaises(errors.BlockadeUsageError):
                self.chaos.delete(name)

    def _specific_event_called(self, func_name, event_name):
        name = "aname"
        block_mock = MagicMock()
        with patch.object(BlockadeManager, 'get_blockade',
                          return_value=block_mock) as mock_method:
            self.chaos.new_chaos(
                    name,
                    min_start_delay=1,
                    max_start_delay=1,
                    min_run_time=100,
                    max_run_time=100,
                    event_set=[event_name])
            time.sleep(0.3)
            self.chaos.stop(name)
        mock_method.assert_called_with(name)
        f = getattr(block_mock, func_name)
        f.assert_called()
        block_mock.fast.assert_called()

    def test_timers_and_slow_fired(self):
        self._specific_event_called('slow', 'SLOW')

    def test_timers_and_duplicate_fired(self):
        self._specific_event_called('duplicate', 'DUPLICATE')

    def test_timers_and_flaky_fired(self):
        self._specific_event_called('flaky', 'FLAKY')

    def test_timers_and_partition_fired(self):
        self._specific_event_called('partition', 'PARTITION')

    def test_timers_and_stop_fired(self):
        self._specific_event_called('stop', 'STOP')
