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

from flask.ext.testing import LiveServerTestCase

from blockade.api.rest import app
from blockade.tests import unittest
from blockade.tests.test_integration import INT_SKIP

import random
import requests


class RestIntegrationTests(LiveServerTestCase):

    headers = {'Content-Type': 'application/json'}

    def create_app(self):
        app.config['TESTING'] = True
        return app

    def setUp(self):
        data = '''
            {
                "containers": {
                    "c1": {
                        "image": "ubuntu:trusty",
                        "hostname": "c1",
                        "command": "/bin/sleep 300"
                    },
                    "c2": {
                        "image": "ubuntu:trusty",
                        "hostname": "c2",
                        "command": "/bin/sleep 300"
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
        status = result_data.get('containers').get(container_name).get('status')
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
