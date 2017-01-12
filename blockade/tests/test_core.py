#
#  Copyright (C) 2014 Dell, Inc.
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

import mock

from blockade.tests import unittest
from blockade.core import Blockade, Container, ContainerStatus, expand_partitions
from blockade.errors import BlockadeError
from blockade.config import BlockadeContainerConfig, BlockadeConfig


class BlockadeCoreTests(unittest.TestCase):

    blockade_id = None

    def setUp(self):
        self.blockade_id = "ourblockadeid"
        self.network = mock.Mock()
        self.docker_client = mock.Mock()
        self.state = mock.MagicMock()
        self.state.get_audit_file.return_value = os.devnull

    def test_create(self):
        containers = {'c1': BlockadeContainerConfig("c1", "image"),
                      'c2': BlockadeContainerConfig("c2", "image"),
                      'c3': BlockadeContainerConfig("c3", "image")}
        config = BlockadeConfig(containers)

        self.network.get_container_device.side_effect = lambda dc, y: "veth"+y

        self.state.exists.side_effect = lambda: False
        self.state.blockade_id = self.blockade_id
        self.docker_client.create_container.side_effect = [
            {"Id": "container1"},
            {"Id": "container2"},
            {"Id": "container3"}]

        b = Blockade(config,
                     state=self.state,
                     network=self.network,
                     docker_client=self.docker_client)

        b.create()

        self.assertEqual(self.state.initialize.call_count, 1)
        self.assertEqual(self.docker_client.create_container.call_count, 3)

    def test_expand_partitions(self):
        def normal(name):
            return Container(name, 'id-'+name, ContainerStatus.UP)
        containers = [normal(name) for name in ["c1", "c2", "c3", "c4", "c5"]]

        # add a holy container as well
        containers.append(Container('c6', 'id-c6', ContainerStatus.UP, holy=True))

        partitions = expand_partitions(containers, [["c1", "c3"]])
        self.assert_partitions(partitions, [["c1", "c3"], ["c2", "c4", "c5"]])

        partitions = expand_partitions(containers, [["c1", "c3"], ["c4"]])
        self.assert_partitions(partitions, [["c1", "c3"], ["c2", "c5"],
                                            ["c4"]])

        with self.assertRaisesRegexp(BlockadeError, "unknown"):
            expand_partitions(containers, [["c1"], ["c100"]])

        with self.assertRaisesRegexp(BlockadeError, "holy"):
            expand_partitions(containers, [["c1"], ["c2", "c6"]])

    def assert_partitions(self, partitions1, partitions2):
        setofsets1 = frozenset(frozenset(n) for n in partitions1)
        setofsets2 = frozenset(frozenset(n) for n in partitions2)
        self.assertEqual(setofsets1, setofsets2)

    def test_add_docker_containers(self):
        containers = ['id1', 'id2', 'id3']

        self.docker_client.inspect_container.side_effect = lambda id: {"Id": id}
        self.network.get_container_device.side_effect = lambda dc, y: "veth"+y
        self.state.exists.side_effect = lambda: False
        self.state.container_id.side_effect = lambda name: None
        self.state.containers = {}
        self.state.blockade_id = self.blockade_id

        b = Blockade(BlockadeConfig(),
                     state=self.state,
                     network=self.network,
                     docker_client=self.docker_client)

        b.add_container(containers)

        self.assertEqual(self.state.update.call_count, 1)
        self.assertEqual(len(self.state.containers), 3)

    # get_container_description should use the IP address from the network
    # if there is only one network and the top-level IP address is empty
    def test_get_container_description_ip_address_info(self):
        expected_ip = "1.2.3.4"
        self.docker_client.inspect_container.side_effect = lambda id: {
            "Id": id,
            "IPAddress": "",
            "NetworkSettings": {
                "Networks": {"TheOnlyNetwork": {"IPAddress": expected_ip}}
            }
        }

        b = Blockade(BlockadeConfig(),
                     state=self.state,
                     network=self.network,
                     docker_client=self.docker_client)

        container = b._get_container_description("c1")

        self.assertEqual(expected_ip, container.ip_address)
