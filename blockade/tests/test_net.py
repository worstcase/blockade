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

from blockade.net import BlockadeNetwork
from blockade.net import NetworkState
from blockade.net import parse_partition_index
from blockade.net import partition_chain_name
from blockade.tests import unittest

import blockade.net

import mock


NORMAL_QDISC_SHOW = "qdisc pfifo_fast 0: root refcnt 2 bands 3 priomap\n"
SLOW_QDISC_SHOW = "qdisc netem 8011: root refcnt 2 limit 1000 delay 50.0ms\n"
FLAKY_QDISC_SHOW = "qdisc netem 8011: root refcnt 2 limit 1000 loss 50%\n"

QDISC_DEL_NOENT = "RTNETLINK answers: No such file or directory"


_IPTABLES_LIST_FORWARD_1 = """Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
blockade-aa43racd2-p1  all  --  172.17.0.16         anywhere
blockade-4eraffr-p1  all  --  172.17.0.17         anywhere
blockade-e5dcf85cd2-p1  all  --  172.17.0.162         anywhere
blockade-e5dcf85cd2-p1  all  --  172.17.0.164         anywhere
ACCEPT     tcp  --  172.17.0.162         172.17.0.164         tcp spt:8000
ACCEPT     tcp  --  172.17.0.164         172.17.0.162         tcp dpt:8000
ACCEPT     tcp  --  172.17.0.162         172.17.0.163         tcp spt:8000
ACCEPT     tcp  --  172.17.0.163         172.17.0.162         tcp dpt:8000
ACCEPT     all  --  anywhere             anywhere
ACCEPT     all  --  anywhere             anywhere
"""

_IPTABLES_LIST_FORWARD_2 = """Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
"""

_IPTABLES_LIST_1 = """Chain INPUT (policy ACCEPT)
target     prot opt source               destination

Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
blockade-e5dcf85cd2-p1  all  --  172.17.0.162         anywhere
blockade-e5dcf85cd2-p1  all  --  172.17.0.164         anywhere
ACCEPT     tcp  --  172.17.0.162         172.17.0.164         tcp spt:8000
ACCEPT     tcp  --  172.17.0.164         172.17.0.162         tcp dpt:8000
ACCEPT     tcp  --  172.17.0.162         172.17.0.163         tcp spt:8000
ACCEPT     tcp  --  172.17.0.163         172.17.0.162         tcp dpt:8000
ACCEPT     all  --  anywhere             anywhere
ACCEPT     all  --  anywhere             anywhere

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination

Chain blockade-e5dcf85cd2-p1 (2 references)
target     prot opt source               destination
DROP       all  --  anywhere             172.17.0.163

Chain blockade-e5dcf85cd2-p2 (0 references)
target     prot opt source               destination
DROP       all  --  anywhere             172.17.0.162
DROP       all  --  anywhere             172.17.0.164
"""

_IPTABLES_LIST_2 = """Chain INPUT (policy ACCEPT)
target     prot opt source               destination

Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
ACCEPT     tcp  --  172.17.0.162         172.17.0.164         tcp spt:8000
ACCEPT     tcp  --  172.17.0.164         172.17.0.162         tcp dpt:8000
ACCEPT     tcp  --  172.17.0.162         172.17.0.163         tcp spt:8000
ACCEPT     tcp  --  172.17.0.163         172.17.0.162         tcp dpt:8000
ACCEPT     all  --  anywhere             anywhere
ACCEPT     all  --  anywhere             anywhere

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
"""


class NetTests(unittest.TestCase):
    def test_iptables_get_blockade_chains(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = _IPTABLES_LIST_FORWARD_1
            result = blockade.net.iptables_get_source_chains(blockade_id)

            self.assertEqual(1, mock_docker_run.call_count)
            self.assertEqual({"172.17.0.162": 1, "172.17.0.164": 1}, result)

    def test_iptables_delete_blockade_rules_1(self):
        blockade_id = "e5dcf85cd2"
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = _IPTABLES_LIST_FORWARD_1
            blockade.net.iptables_delete_blockade_rules(blockade_id)

            self.assertEqual(3, mock_docker_run.call_count)

            # rules should be removed in reverse order
            expected_calls = [
                mock.call("iptables -n -L FORWARD", image=expected_image),
                mock.call("iptables -D FORWARD 4", image=expected_image),
                mock.call("iptables -D FORWARD 3", image=expected_image)
            ]
            self.assertEqual(expected_calls, mock_docker_run.call_args_list)

    def test_iptables_delete_blockade_rules_2(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = _IPTABLES_LIST_FORWARD_2
            blockade.net.iptables_delete_blockade_rules(blockade_id)

            self.assertEqual(1, mock_docker_run.call_count)

    def test_iptables_delete_blockade_chains_1(self):
        blockade_id = "e5dcf85cd2"
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = _IPTABLES_LIST_1
            blockade.net.iptables_delete_blockade_chains(blockade_id)

            self.assertEqual(5, mock_docker_run.call_count)

            expected_calls = [
                mock.call("iptables -n -L", image=expected_image),
                mock.call("iptables -F blockade-e5dcf85cd2-p1", image=expected_image),
                mock.call("iptables -X blockade-e5dcf85cd2-p1", image=expected_image),
                mock.call("iptables -F blockade-e5dcf85cd2-p2", image=expected_image),
                mock.call("iptables -X blockade-e5dcf85cd2-p2", image=expected_image)]
            self.assertEqual(expected_calls, mock_docker_run.call_args_list)

    def test_iptables_delete_blockade_chains_2(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = _IPTABLES_LIST_2
            blockade.net.iptables_delete_blockade_chains(blockade_id)

            self.assertEqual(1, mock_docker_run.call_count)

    def test_iptables_insert_rule_1(self):
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            blockade.net.iptables_insert_rule("FORWARD",
                                              src="192.168.0.1",
                                              target="DROP")
            cmd = ["iptables", "-I", "FORWARD", "-s", "192.168.0.1",
                   "-j", "DROP"]
            mock_docker_run.assert_called_once_with(
                ' '.join(cmd), image=expected_image
            )

    def test_iptables_insert_rule_2(self):
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            blockade.net.iptables_insert_rule("FORWARD", src="192.168.0.1",
                                              dest="192.168.0.2",
                                              target="DROP")

            cmd = ["iptables", "-I", "FORWARD", "-s", "192.168.0.1",
                   "-d", "192.168.0.2", "-j", "DROP"]
            mock_docker_run.assert_called_once_with(
                ' '.join(cmd), image=expected_image
            )

    def test_iptables_insert_rule_3(self):
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            blockade.net.iptables_insert_rule("FORWARD", dest="192.168.0.2",
                                              target="DROP")
            cmd = ["iptables", "-I", "FORWARD", "-d", "192.168.0.2",
                   "-j", "DROP"]
            mock_docker_run.assert_called_once_with(
                ' '.join(cmd), image=expected_image
            )

    def test_iptables_create_chain(self):
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            blockade.net.iptables_create_chain("hats")
            cmd = ["iptables", "-N", "hats"]
            mock_docker_run.assert_called_once_with(
                ' '.join(cmd), image=expected_image
            )

    def test_partition_chain_parse(self):
        blockade_id = "abc123"
        self.assertEqual(
            "blockade-abc123-p1", partition_chain_name(blockade_id, 1)
        )
        self.assertEqual(
            "blockade-abc123-p2", partition_chain_name(blockade_id, 2)
        )

        index = parse_partition_index(blockade_id,
                                      partition_chain_name(blockade_id, 1))
        self.assertEqual(1, index)

        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "notablockade")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-1")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-p")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-notanumber")

    def test_partition_1(self):
        blockade_id = "e5dcf85cd2"
        expected_image=blockade.net.IPTABLES_DOCKER_IMAGE
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = ""

            blockade.net.partition_containers(blockade_id, [
                    # partition 1
                    [mock.Mock(name="c1", ip_address="10.0.1.1"),
                     mock.Mock(name="c2", ip_address="10.0.1.2")],
                    # partition 2
                    [mock.Mock(name="c3", ip_address="10.0.1.3")]
                ]
            )

            mock_docker_run.assert_has_calls([
                # create a chain for each partition
                mock.call(
                    "iptables -N blockade-e5dcf85cd2-p1",
                    image=expected_image
                ),
                # forward traffic from each node in p1 to its new chain
                mock.call(
                    "iptables -I FORWARD -s 10.0.1.1 -j blockade-e5dcf85cd2-p1",
                    image=expected_image
                ),
                mock.call(
                    "iptables -I FORWARD -s 10.0.1.2 -j blockade-e5dcf85cd2-p1",
                    image=expected_image
                ),
                # and drop any traffic from this partition directed
                # at any container not in this partition
                mock.call(
                    "iptables -I blockade-e5dcf85cd2-p1 -d 10.0.1.3 -j DROP",
                    image=expected_image
                ),
            ], any_order=True)

            mock_docker_run.assert_has_calls([
                # now repeat the process for the second partition
                mock.call(
                    "iptables -N blockade-e5dcf85cd2-p2",
                    image=expected_image
                ),
                mock.call(
                    "iptables -I FORWARD -s 10.0.1.3 -j blockade-e5dcf85cd2-p2",
                    image=expected_image
                ),
                mock.call(
                    "iptables -I blockade-e5dcf85cd2-p2 -d 10.0.1.1 -j DROP",
                    image=expected_image
                ),
                mock.call(
                    "iptables -I blockade-e5dcf85cd2-p2 -d 10.0.1.2 -j DROP",
                    image=expected_image
                ),
            ], any_order=True)

    def test_network_already_normal(self):
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = "", QDISC_DEL_NOENT

            net = BlockadeNetwork(mock.Mock())

            # ensure we don't raise an error
            net.fast('somedevice')
            self.assertIn('somedevice', mock_docker_run.call_args[0][0])

    def test_slow(self):
        slow_config = "75ms 100ms distribution normal"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_config = mock.Mock()
            mock_config.network = {"slow": slow_config}
            net = BlockadeNetwork(mock_config)
            net.slow("mydevice")
            cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
                   "root", "netem", "delay"] + slow_config.split()
            mock_docker_run.assert_called_once_with(' '.join(cmd), image=blockade.net.IPTABLES_DOCKER_IMAGE)

    def test_flaky(self):
        flaky_config = "30%"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_config = mock.Mock()
            mock_config.network = {"flaky": flaky_config}
            net = BlockadeNetwork(mock_config)
            net.flaky("mydevice")
            cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
                   "root", "netem", "loss"] + flaky_config.split()
            mock_docker_run.assert_called_once_with(' '.join(cmd), image=blockade.net.IPTABLES_DOCKER_IMAGE)

    def test_duplicate(self):
        duplicate_config = "5%"
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_config = mock.Mock()
            mock_config.network = {"duplicate": duplicate_config}
            net = BlockadeNetwork(mock_config)
            net.duplicate("mydevice")
            cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
                   "root", "netem", "duplicate"] + duplicate_config.split()
            mock_docker_run.assert_called_once_with(' '.join(cmd), image=blockade.net.IPTABLES_DOCKER_IMAGE)

    def test_network_state_slow(self):
        self._network_state(NetworkState.SLOW, SLOW_QDISC_SHOW)

    def test_network_state_normal(self):
        self._network_state(NetworkState.NORMAL, NORMAL_QDISC_SHOW)

    def test_network_state_flaky(self):
        self._network_state(NetworkState.FLAKY, FLAKY_QDISC_SHOW)

    def _network_state(self, state, output):
        with mock.patch('blockade.net.docker_run') as mock_docker_run:
            mock_docker_run.return_value = output

            net = BlockadeNetwork(mock.Mock())
            self.assertEqual(net.network_state('somedevice'), state)
            self.assertIn('somedevice', mock_docker_run.call_args[0][0])
