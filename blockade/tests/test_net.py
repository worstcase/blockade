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

import shlex

import mock

from blockade.net import BlockadeNetwork
from blockade.net import NetworkState
from blockade.net import parse_partition_index
from blockade.net import partition_chain_name
from blockade.tests import unittest
from blockade.errors import HostExecError

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
    def test_get_ip_partitions(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        blockade_id = "e5dcf85cd2"
        mock_run.return_value = _IPTABLES_LIST_FORWARD_1

        net = BlockadeNetwork(None, mock_host_exec)
        result = net.get_ip_partitions(blockade_id)

        self.assertEqual(1, mock_run.call_count)
        self.assertEqual({"172.17.0.162": 1, "172.17.0.164": 1}, result)

    def test_iptables_delete_blockade_rules_1(self):
        blockade_id = "e5dcf85cd2"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.return_value = _IPTABLES_LIST_FORWARD_1

        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.delete_blockade_rules(blockade_id)

        self.assertEqual(3, mock_run.call_count)

        # rules should be removed in reverse order
        expected_calls = [
            mock.call(["iptables", "-n", "-L", "FORWARD"]),
            mock.call(["iptables", "-D", "FORWARD", "4"]),
            mock.call(["iptables", "-D", "FORWARD", "3"])
        ]
        self.assertEqual(expected_calls, mock_run.call_args_list)

    def test_iptables_delete_blockade_rules_2(self):
        blockade_id = "e5dcf85cd2"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.return_value = _IPTABLES_LIST_FORWARD_2
        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.delete_blockade_rules(blockade_id)
        self.assertEqual(1, mock_run.call_count)

    def test_iptables_delete_blockade_chains_1(self):
        blockade_id = "e5dcf85cd2"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.return_value = _IPTABLES_LIST_1
        net = BlockadeNetwork(None, mock_host_exec)

        net.iptables.delete_blockade_chains(blockade_id)

        self.assertEqual(5, mock_run.call_count)

        expected_calls = [
            mock.call(shlex.split("iptables -n -L")),
            mock.call(shlex.split("iptables -F blockade-e5dcf85cd2-p1")),
            mock.call(shlex.split("iptables -X blockade-e5dcf85cd2-p1")),
            mock.call(shlex.split("iptables -F blockade-e5dcf85cd2-p2")),
            mock.call(shlex.split("iptables -X blockade-e5dcf85cd2-p2"))]
        self.assertEqual(expected_calls, mock_run.call_args_list)

    def test_iptables_delete_blockade_chains_2(self):
        blockade_id = "e5dcf85cd2"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.return_value = _IPTABLES_LIST_2
        net = BlockadeNetwork(None, mock_host_exec)

        net.iptables.delete_blockade_chains(blockade_id)

        self.assertEqual(1, mock_run.call_count)

    def test_iptables_insert_rule_1(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.insert_rule("FORWARD", src="192.168.0.1", target="DROP")
        cmd = ["iptables", "-I", "FORWARD", "-s", "192.168.0.1", "-j", "DROP"]
        mock_run.assert_called_once_with(cmd)

    def test_iptables_insert_rule_2(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.insert_rule("FORWARD", src="192.168.0.1",
            dest="192.168.0.2", target="DROP")

        cmd = ["iptables", "-I", "FORWARD", "-s", "192.168.0.1", "-d",
            "192.168.0.2", "-j", "DROP"]
        mock_run.assert_called_once_with(cmd)

    def test_iptables_insert_rule_3(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.insert_rule("FORWARD", dest="192.168.0.2", target="DROP")
        cmd = ["iptables", "-I", "FORWARD", "-d", "192.168.0.2", "-j", "DROP"]
        mock_run.assert_called_once_with(cmd)

    def test_iptables_create_chain(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        net = BlockadeNetwork(None, mock_host_exec)
        net.iptables.create_chain("hats")
        cmd = ["iptables", "-N", "hats"]
        mock_run.assert_called_once_with(cmd)

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

    def test_partition_long_chain_parse(self):
        blockade_id = "abc123awhopbopaloobopalopbamboom"
        self.assertEqual(
            "blockade-abc123awhopbopal-p1", partition_chain_name(blockade_id, 1)
        )
        self.assertEqual(
            "blockade-abc123awhopbopal-p2", partition_chain_name(blockade_id, 2)
        )

        index = parse_partition_index(blockade_id,
                                      partition_chain_name(blockade_id, 1))
        self.assertEqual(1, index)

        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123")

    def test_partition_1(self):

        def iptables(args):
            if args == ["iptables", "-n", "-L"]:
                return _IPTABLES_LIST_2
            if args == ["iptables", "-n", "-L", "FORWARD"]:
                return _IPTABLES_LIST_FORWARD_2
            return ""

        blockade_id = "e5dcf85cd2"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.side_effect = iptables
        net = BlockadeNetwork(None, mock_host_exec)

        net.partition_containers(blockade_id, [
            # partition 1
            [mock.Mock(name="c1", ip_address="10.0.1.1"),
             mock.Mock(name="c2", ip_address="10.0.1.2")],
            # partition 2
            [mock.Mock(name="c3", ip_address="10.0.1.3")]
        ])

        mock_run.assert_has_calls([
            # create a chain for each partition
            mock.call(shlex.split("iptables -N blockade-e5dcf85cd2-p1")),
            # forward traffic from each node in p1 to its new chain
            mock.call(shlex.split(
                "iptables -I FORWARD -s 10.0.1.1 -j blockade-e5dcf85cd2-p1")),
            mock.call(shlex.split(
                "iptables -I FORWARD -s 10.0.1.2 -j blockade-e5dcf85cd2-p1")),
            # and drop any traffic from this partition directed
            # at any container not in this partition
            mock.call(shlex.split(
                "iptables -I blockade-e5dcf85cd2-p1 -d 10.0.1.3 -j DROP")),
        ], any_order=True)

        mock_run.assert_has_calls([
            # now repeat the process for the second partition
            mock.call(shlex.split("iptables -N blockade-e5dcf85cd2-p2")),
            mock.call(shlex.split(
                "iptables -I FORWARD -s 10.0.1.3 -j blockade-e5dcf85cd2-p2")),
            mock.call(shlex.split(
                "iptables -I blockade-e5dcf85cd2-p2 -d 10.0.1.1 -j DROP")),
            mock.call(shlex.split(
                "iptables -I blockade-e5dcf85cd2-p2 -d 10.0.1.2 -j DROP")),
        ], any_order=True)

    def test_network_already_normal(self):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        net = BlockadeNetwork(None, mock_host_exec)
        mock_run.side_effect = HostExecError("", exit_code=2,
            output=QDISC_DEL_NOENT)

        # ensure we don't raise an error
        net.fast('somedevice')
        self.assertIn('somedevice', mock_run.call_args[0][0])

    def test_slow(self):
        slow_config = "75ms 100ms distribution normal"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_config = mock.Mock()
        mock_config.network = {"slow": slow_config}
        net = BlockadeNetwork(mock_config, mock_host_exec)
        net.slow("mydevice")
        cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
               "root", "netem", "delay"] + slow_config.split()
        mock_run.assert_called_once_with(cmd)

    def test_flaky(self):
        flaky_config = "30%"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_config = mock.Mock()
        mock_config.network = {"flaky": flaky_config}
        net = BlockadeNetwork(mock_config, mock_host_exec)
        net.flaky("mydevice")
        cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
               "root", "netem", "loss"] + flaky_config.split()
        mock_run.assert_called_once_with(cmd)

    def test_duplicate(self):
        duplicate_config = "5%"
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_config = mock.Mock()
        mock_config.network = {"duplicate": duplicate_config}
        net = BlockadeNetwork(mock_config, mock_host_exec)
        net.duplicate("mydevice")
        cmd = ["tc", "qdisc", "replace", "dev", "mydevice",
               "root", "netem", "duplicate"] + duplicate_config.split()
        mock_run.assert_called_once_with(cmd)

    def test_network_state_slow(self):
        self._network_state(NetworkState.SLOW, SLOW_QDISC_SHOW)

    def test_network_state_normal(self):
        self._network_state(NetworkState.NORMAL, NORMAL_QDISC_SHOW)

    def test_network_state_flaky(self):
        self._network_state(NetworkState.FLAKY, FLAKY_QDISC_SHOW)

    def _network_state(self, state, output):
        mock_host_exec = mock.Mock()
        mock_run = mock_host_exec.run
        mock_run.return_value = output

        net = BlockadeNetwork(mock.Mock(), mock_host_exec)
        self.assertEqual(net.network_state('somedevice'), state)
        self.assertIn('somedevice', mock_run.call_args[0][0])
