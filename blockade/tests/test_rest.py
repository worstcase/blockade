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

from blockade.api.manager import BlockadeManager
from blockade.api.rest import app
from blockade.core import Blockade
from blockade.tests import unittest

import json
import mock


class RestTests(unittest.TestCase):

    name = "BlockadeRestTests"
    headers = {'Content-Type': 'application/json'}

    def setUp(self):
        self.client = app.test_client()
        self.blockade = mock.MagicMock()

    def test_network_state_missing_state(self):
        data = '''
            {
                "wrong_key": "fast",
                "container_names": "c1"
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/network_state' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(400, result.status_code)

    def test_network_state_missing_container_names(self):
        data = '''
            {
                "network_state": "fast",
                "wrong_key": "c1"
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/network_state' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(400, result.status_code)

    def test_network_state(self):
        data = '''
            {
                "network_state": "fast",
                "container_names": ["c1"]
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/network_state' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.fast.call_count)

    def test_action_missing_command(self):
        data = '''
            {
                "wrong_key": "start",
                "container_names": "c1"
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/action' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(400, result.status_code)

    def test_action_missing_container_names(self):
        data = '''
            {
                "command": "start",
                "wrong_key": "c1"
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/action' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(400, result.status_code)

    def test_action(self):
        data = '''
            {
                "command": "start",
                "container_names": ["c1"]
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/action' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.start.call_count)

    def test_delete_partition(self):
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.delete('/blockade/%s/partitions' % self.name,
                                        headers=self.headers)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.join.call_count)

    def test_random_partition(self):
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/partitions' % self.name,
                                      headers=self.headers,
                                      query_string={'random': 'True'})

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.random_partition.call_count)

    def test_partitions(self):
        data = '''
            {
                "partitions": [["c1"], ["c2"]]
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.post('/blockade/%s/partitions' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.partition.call_count)


    def test_delete_blockade(self):
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.delete('/blockade/%s' % self.name)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.destroy.call_count)

    def test_get_blockade(self):
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.get('/blockade/%s' % self.name)

            result_data = json.loads(result.get_data(as_text=True))
            self.assertEqual(200, result.status_code)
            self.assertTrue('containers' in result_data)

    def test_get_all_blockades(self):
        blockades = {
            'blockade1': 'abc',
            'blockade2': 'def',
            'blockade3': 'xyz'
        }
        with mock.patch.object(BlockadeManager,
                               'get_all_blockade_names',
                               return_value=list(blockades.keys())):
            result = self.client.get('/blockade', headers=self.headers)
            result_data = json.loads(result.get_data(as_text=True))
            self.assertEqual(200, result.status_code)
            self.assertTrue('blockades' in result_data)
            for key in blockades.keys():
                self.assertTrue(key in result_data.get('blockades'))

    def test_create_blockade(self):
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
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade):

            result = self.client.post('/blockade/%s' % self.name,
                                      headers=self.headers,
                                      data=data)

            self.assertEqual(1, self.blockade.create.call_count)
            self.assertEqual(204, result.status_code)


    def test_add_docker_container(self):
        data = '''
            {
                "container_ids": ["docker_container_id"]
            }
        '''
        with mock.patch.object(BlockadeManager,
                               'get_blockade',
                               return_value=self.blockade), \
             mock.patch.object(BlockadeManager,
                               'blockade_exists',
                               return_value=True):

            result = self.client.put('/blockade/%s' % self.name,
                                     headers=self.headers,
                                     data=data)

            self.assertEqual(204, result.status_code)
            self.assertEqual(1, self.blockade.add_container.call_count)
