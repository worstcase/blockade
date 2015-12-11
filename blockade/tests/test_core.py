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

import mock

from blockade.tests import unittest
from blockade.core import Blockade, Container, ContainerState, expand_partitions
from blockade.errors import BlockadeError
from blockade.config import BlockadeContainerConfig, BlockadeConfig
from blockade.state import BlockadeState


class BlockadeCoreTests(unittest.TestCase):

    def setUp(self):
        self.network = mock.Mock()

        self.state_factory = mock.Mock()
        self.docker_client = mock.Mock()

    def test_create(self):
        containers = {'c1': BlockadeContainerConfig("c1", "image"),
                      'c2': BlockadeContainerConfig("c2", "image"),
                      'c3': BlockadeContainerConfig("c3", "image")}
        config = BlockadeConfig(containers)

        self.network.get_container_device.side_effect = lambda dc, x, y: "veth"+y

        initialize = lambda x, y: BlockadeState("ourblockadeid", x)
        self.state_factory.initialize.side_effect = initialize
        self.docker_client.create_container.side_effect = [
            {"Id": "container1"},
            {"Id": "container2"},
            {"Id": "container3"}]

        b = Blockade(config, self.state_factory, self.network,
                     self.docker_client)

        b.create()

        self.assertEqual(self.state_factory.initialize.call_count, 1)
        self.assertEqual(self.docker_client.create_container.call_count, 3)

    def test_expand_partitions(self):
        def normal(name):
            return Container(name, 'id-'+name, ContainerState.UP)
        containers = [normal(name) for name in ["c1", "c2", "c3", "c4", "c5"]]

        # add a holy container as well
        containers.append(Container('c6', 'id-c6', ContainerState.UP, holy=True))

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
