#
#  Copyright (C) 2016 Dell, Inc.
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

import os
import time
import signal
import random
import multiprocessing

import requests
from flask.ext.testing import LiveServerTestCase

from blockade.api.rest import app, stack_trace_handler
from blockade.api.manager import BlockadeManager
from blockade.host import HostExec
from blockade.tests import unittest
from blockade.tests.test_integration import INT_SKIP
from blockade.tests.helpers import HostExecHelper
from blockade.tests.util import wait


def wait_for_children():
    """Wait for child processes to exit

    The testing system launches and terminates child processes, but
    doesn't wait for them to actually die. So in a few places we need
    this extra call"""
    wait(lambda: len(multiprocessing.active_children()) == 0)


@unittest.skipIf(*INT_SKIP)
class RestIntegrationTests(LiveServerTestCase):

    headers = {'Content-Type': 'application/json'}
    host_exec_helper = None

    @classmethod
    def setUpClass(cls):
        cls.host_exec_helper = HostExecHelper()
        # this sets up an environment variable that controls the prefix
        # used for all host exec helper containers. This env will be
        # respected by the Flask app child process, and allows us to
        # assert that containers are correctly torn down by the testing
        # rig.
        cls.host_exec_helper.setup_prefix_env()

    @classmethod
    def tearDownClass(cls):

        # LiveServerTestCase sends SIGTERM to child processes, but doesn't
        # wait for exit. So we wait up to 9 seconds for all children to be
        # gone.
        wait_for_children()

        if cls.host_exec_helper:
            cls.host_exec_helper.tearDown()

    def create_app(self):
        # HACK: wait for any previous processes to exit. We do it here because
        # this is the only opportunity LiveServerTestCase provides:
        # setUp/tearDown is too late/early.
        wait_for_children()

        app.config['TESTING'] = True
        app.config['DEBUG'] = True

        # LiveServerTestCase runs the server in a multiprocessing.Process,
        # and doesn't provide an obvious place for setup/teardown logic
        # *in* the child process. So we monkeypatch app.run to set up a
        # SIGTERM handler that runs our HostExec cleanup.

        real_run = app.run

        def _wrapped_run(*args, **kwargs):
            host_exec = HostExec()
            BlockadeManager.set_host_exec(host_exec)

            def _cleanup_host_exec(*args):
                host_exec.close()
                os._exit(0)

            signal.signal(signal.SIGTERM, _cleanup_host_exec)
            signal.signal(signal.SIGUSR2, stack_trace_handler)

            real_run(*args, **kwargs)

        app.run = _wrapped_run

        return app

    def setUp(self):

        data = '''
            {
                "containers": {
                    "c1": {
                        "image": "krallin/ubuntu-tini:trusty",
                        "hostname": "c1",
                        "command": ["/bin/sleep", "300"]
                    },
                    "c2": {
                        "image": "krallin/ubuntu-tini:trusty",
                        "hostname": "c2",
                        "command": ["/bin/sleep", "300"]
                    }
                }
            }
        '''
        # ran into issues with long names when using the class name
        # names must be less than 29 chars for iptable chains
        self.name = 'tmpRestTests' + str(random.randint(0, 10000))

        # create a blockade
        self.base_url = self.get_server_url() + "/blockade"
        self.url = self.base_url + "/%s" % self.name
        result = requests.post(self.url, headers=self.headers, data=data)
        error_msg = "failed to launch blockade: %s" % self.name
        assert result.status_code == 204, error_msg

    def tearDown(self):
        result = requests.delete(self.url)
        error_msg = "failed to destroy blockade: %s" % self.name
        assert result.status_code == 204, error_msg

    def _get_all_blockades(self):
        result = requests.get(self.base_url, headers=self.headers)
        assert result.status_code == 200
        return result.json()

    def _get_blockade(self):
        result = requests.get(self.url, headers=self.headers)
        assert result.status_code == 200
        return result.json()

    @unittest.skipIf(*INT_SKIP)
    def test_get_blockades(self):
        # get all blockades
        result_data = self._get_all_blockades()
        assert 'blockades' in result_data
        assert self.name in result_data.get('blockades')

        # get the single blockade that was created
        result_data = self._get_blockade()
        assert 'containers' in result_data
        assert len(result_data.get('containers')) == 2

    def _assert_partition(self):
        result_data = self._get_blockade()
        c1_partition = result_data.get('containers').get('c1').get('partition')
        c2_partition = result_data.get('containers').get('c2').get('partition')
        assert isinstance(c1_partition, int)
        assert isinstance(c2_partition, int)
        assert c1_partition > 0
        assert c2_partition > 0
        assert c1_partition != c2_partition

    def _assert_join(self):
        result_data = self._get_blockade()
        c1_partition = result_data.get('containers').get('c1').get('partition')
        c2_partition = result_data.get('containers').get('c2').get('partition')
        assert c1_partition is None
        assert c2_partition is None

    def _assert_event(self, event_name):
        url = self.url + '/events'
        result = requests.get(url)
        events = result.json()
        for e in events['events']:
            if e['event'] == event_name.lower():
                return
        assert False

    @unittest.skipIf(*INT_SKIP)
    def test_partition(self):
        data = '''
            {
                "partitions": [["c1"], ["c2"]]
            }
        '''
        url = self.url + '/partitions'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_partition()
        self._assert_event('partition')
        result = requests.delete(url)
        self._assert_join()

    @unittest.skipIf(*INT_SKIP)
    def test_add_docker_container_not_found(self):
        data = '''
            {
                "containers": ["not_a_real_container"]
            }
        '''
        result = requests.put(self.url, headers=self.headers, data=data)
        assert result.status_code == 400

    def _assert_container_status(self, container_name, container_status):
        result_data = self._get_blockade()
        status =\
            result_data.get('containers').get(container_name).get('status')
        assert status.upper() == container_status.upper()

    @unittest.skipIf(*INT_SKIP)
    def test_action_kill(self):
        data = '''
            {
                "command": "kill",
                "container_names": ["c1"]
            }
        '''
        url = self.url + '/action'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_status('c1', 'DOWN')
        self._assert_event('kill')

    @unittest.skipIf(*INT_SKIP)
    def test_action_start(self):
        data = '''
            {
                "command": "start",
                "container_names": ["c1"]
            }
        '''
        url = self.url + '/action'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_status('c1', 'UP')
        self._assert_event('start')

    def _assert_container_network_state(self, container_name, network_state):
        result_data = self._get_blockade()
        container = result_data.get('containers').get(container_name)
        state = container.get('network_state')
        assert state.upper() == network_state.upper()

    @unittest.skipIf(*INT_SKIP)
    def test_network_state_slow(self):
        data = '''
            {
                "network_state": "slow",
                "container_names": ["c1"]
            }
        '''
        url = self.url + '/network_state'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_network_state('c1', 'SLOW')
        self._assert_event('slow')

    def _test_basic_events(self, event):
        data = '''
            {
                "event_set": ["%s"],
                "min_start_delay": 1,
                "max_start_delay": 2,
                "min_run_time": 30000,
                "min_run_time": 300000,
                "min_containers_at_once": 2,
                "max_containers_at_once": 2
            }
        ''' % event
        url = self.url + '/chaos'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 201
        time.sleep(10.0)

    @unittest.skipIf(*INT_SKIP)
    def test_chaos_slow(self):
        self._test_basic_events("SLOW")
        self._assert_container_network_state('c1', 'SLOW')

    @unittest.skipIf(*INT_SKIP)
    def test_chaos_flaky(self):
        self._test_basic_events("FLAKY")
        self._assert_container_network_state('c1', 'FLAKY')

    @unittest.skipIf(*INT_SKIP)
    def test_chaos_duplicate(self):
        self._test_basic_events("DUPLICATE")
        self._assert_container_network_state('c1', 'DUPLICATE')

    @unittest.skipIf(*INT_SKIP)
    def test_chaos_partition(self):
        self._test_basic_events("PARTITION")
        time.sleep(10.0)
        self._assert_partition()

    @unittest.skipIf(*INT_SKIP)
    def test_chaos_start_status_update_stop(self):
        data = '''
            {
                "event_set": ["SLOW"],
                "min_start_delay": 1,
                "max_start_delay": 2,
                "min_run_time": 30000,
                "min_run_time": 300000,
                "min_containers_at_once": 2,
                "max_containers_at_once": 2
            }
        '''
        url = self.url + '/chaos'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 201
        result = requests.get(url)
        assert result.status_code == 200
        result = requests.put(url, headers=self.headers, data=data)
        assert result.status_code == 200
        result = requests.delete(url)
        assert result.status_code == 200
        result = requests.get(url)
        assert result.status_code == 500

    @unittest.skipIf(*INT_SKIP)
    def test_action_stop_start_slow(self):
        data = '''
            {
                "partitions": [["c1"], ["c2"]]
            }
        '''
        url = self.url + '/partitions'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_partition()
        self._assert_event('partition')
        result = requests.delete(url)
        self._assert_join()

        data = '''
            {
                "command": "stop",
                "container_names": ["c2"]
            }
        '''
        url = self.url + '/action'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_status('c2', 'DOWN')
        time.sleep(90)
        data = '''
            {
                "command": "start",
                "container_names": ["c2"]
            }
        '''
        url = self.url + '/action'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_status('c2', 'UP')

        data = '''
            {
                "network_state": "slow",
                "container_names": ["c1"]
            }
        '''
        url = self.url + '/network_state'
        result = requests.post(url, headers=self.headers, data=data)
        assert result.status_code == 204
        self._assert_container_network_state('c1', 'SLOW')
        url = self.url + '/events'
        result = requests.get(url, headers=self.headers, data=data)
