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
import subprocess

from blockade.tests import unittest
import blockade.net
from blockade.net import NetworkState, BlockadeNetwork, \
    parse_partition_index, partition_chain_name

# NOTE these values are "byte strings" -- to depict output we would see
# from subprocess calls. We need to make sure we properly decode them
# in Python3.

NORMAL_QDISC_SHOW = b"qdisc pfifo_fast 0: root refcnt 2 bands 3 priomap\n"
SLOW_QDISC_SHOW = b"qdisc netem 8011: root refcnt 2 limit 1000 delay 50.0ms\n"
FLAKY_QDISC_SHOW = b"qdisc netem 8011: root refcnt 2 limit 1000 loss 50%\n"

QDISC_DEL_NOENT = b"RTNETLINK answers: No such file or directory"


_IPTABLES_LIST_FORWARD_1 = b"""Chain FORWARD (policy ACCEPT)
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

_IPTABLES_LIST_FORWARD_2 = b"""Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
"""

_IPTABLES_LIST_1 = b"""Chain INPUT (policy ACCEPT)
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

_IPTABLES_LIST_2 = b"""Chain INPUT (policy ACCEPT)
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
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_check_output = mock_subprocess.check_output
            mock_check_output.return_value = _IPTABLES_LIST_FORWARD_1
            result = blockade.net.iptables_get_source_chains(blockade_id)

            self.assertEqual(mock_subprocess.check_output.call_count, 1)
            self.assertEqual(result, {"172.17.0.162": 1, "172.17.0.164": 1})

    def test_iptables_delete_blockade_rules_1(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_check_output = mock_subprocess.check_output
            mock_check_output.return_value = _IPTABLES_LIST_FORWARD_1
            blockade.net.iptables_delete_blockade_rules(blockade_id)

            self.assertEqual(mock_subprocess.check_output.call_count, 1)

            # rules should be removed in reverse order
            expected_calls = [mock.call(["iptables", "-D", "FORWARD", "4"]),
                              mock.call(["iptables", "-D", "FORWARD", "3"])]
            self.assertEqual(mock_subprocess.check_call.call_args_list,
                             expected_calls)

    def test_iptables_delete_blockade_rules_2(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_check_output = mock_subprocess.check_output
            mock_check_output.return_value = _IPTABLES_LIST_FORWARD_2
            blockade.net.iptables_delete_blockade_rules(blockade_id)

            self.assertEqual(mock_subprocess.check_output.call_count, 1)
            self.assertEqual(mock_subprocess.check_call.call_count, 0)

    def test_iptables_delete_blockade_chains_1(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_subprocess.check_output.return_value = _IPTABLES_LIST_1
            blockade.net.iptables_delete_blockade_chains(blockade_id)

            self.assertEqual(mock_subprocess.check_output.call_count, 1)

            expected_calls = [
                mock.call(["iptables", "-F", "blockade-e5dcf85cd2-p1"]),
                mock.call(["iptables", "-X", "blockade-e5dcf85cd2-p1"]),
                mock.call(["iptables", "-F", "blockade-e5dcf85cd2-p2"]),
                mock.call(["iptables", "-X", "blockade-e5dcf85cd2-p2"])]
            self.assertEqual(mock_subprocess.check_call.call_args_list,
                             expected_calls)

    def test_iptables_delete_blockade_chains_2(self):
        blockade_id = "e5dcf85cd2"
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_subprocess.check_output.return_value = _IPTABLES_LIST_2
            blockade.net.iptables_delete_blockade_chains(blockade_id)

            self.assertEqual(mock_subprocess.check_output.call_count, 1)
            self.assertEqual(mock_subprocess.check_call.call_count, 0)

    def test_iptables_insert_rule_1(self):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            blockade.net.iptables_insert_rule("FORWARD", src="192.168.0.1",
                                              target="DROP")
            mock_subprocess.check_call.assert_called_once_with(
                ["iptables", "-I", "FORWARD", "-s", "192.168.0.1",
                 "-j", "DROP"])

    def test_iptables_insert_rule_2(self):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            blockade.net.iptables_insert_rule("FORWARD", src="192.168.0.1",
                                              dest="192.168.0.2",
                                              target="DROP")
            mock_subprocess.check_call.assert_called_once_with(
                ["iptables", "-I", "FORWARD", "-s", "192.168.0.1", "-d",
                 "192.168.0.2", "-j", "DROP"])

    def test_iptables_insert_rule_3(self):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            blockade.net.iptables_insert_rule("FORWARD", dest="192.168.0.2",
                                              target="DROP")
            mock_subprocess.check_call.assert_called_once_with(
                ["iptables", "-I", "FORWARD", "-d", "192.168.0.2",
                 "-j", "DROP"])

    def test_iptables_create_chain(self):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            blockade.net.iptables_create_chain("hats")
            mock_subprocess.check_call.assert_called_once_with(
                ["iptables", "-N", "hats"])

    def test_partition_chain_parse(self):
        blockade_id = "abc123"
        self.assertEqual(partition_chain_name(blockade_id, 1), "blockade-abc123-p1")
        self.assertEqual(partition_chain_name(blockade_id, 2), "blockade-abc123-p2")

        index = parse_partition_index(blockade_id,
                                      partition_chain_name(blockade_id, 1))
        self.assertEqual(index, 1)

        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "notablockade")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-1")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-p")
        with self.assertRaises(ValueError):
            parse_partition_index(blockade_id, "abc123-notanumber")

    def test_network_already_normal(self):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_process = mock_subprocess.Popen.return_value = mock.Mock()
            mock_process.communicate.return_value = "", QDISC_DEL_NOENT
            mock_process.returncode = 2

            net = BlockadeNetwork(mock.Mock())

            # ensure we don't raise an error
            net.fast('somedevice')
            self.assertIn('somedevice',
                          mock_subprocess.Popen.call_args[0][0])

    def test_network_state_slow(self):
        self._network_state(NetworkState.SLOW, SLOW_QDISC_SHOW)

    def test_network_state_normal(self):
        self._network_state(NetworkState.NORMAL, NORMAL_QDISC_SHOW)

    def test_network_state_flaky(self):
        self._network_state(NetworkState.FLAKY, FLAKY_QDISC_SHOW)

    def _network_state(self, state, output):
        with mock.patch('blockade.net.subprocess') as mock_subprocess:
            mock_subprocess.CalledProcessError = subprocess.CalledProcessError
            mock_subprocess.check_output.return_value = output

            net = BlockadeNetwork(mock.Mock())
            self.assertEqual(net.network_state('somedevice'), state)
            self.assertIn('somedevice',
                          mock_subprocess.check_output.call_args[0][0])
