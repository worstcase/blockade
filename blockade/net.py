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
import docker

import collections
import itertools
import re
import logging

from .errors import BlockadeError, HostExecError


_logger = logging.getLogger(__name__)


BLOCKADE_CHAIN_PREFIX = "blockade-"
# iptables chain names are a max of 29 characters so we truncate the prefix
MAX_CHAIN_PREFIX_LENGTH = 25
IPTABLES_DOCKER_IMAGE = "vimagick/iptables:latest"

_ERROR_NET_IFACE = "Failed to find container network interface"


class NetworkState(object):
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    FLAKY = "FLAKY"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class BlockadeNetwork(object):
    def __init__(self, config, host_exec):
        self.config = config
        self.host_exec = host_exec
        self.iptables = _IPTables(host_exec)
        self.traffic_control = _TrafficControl(host_exec)

    def network_state(self, device):
        return self.traffic_control.network_state(device)

    def flaky(self, device):
        flaky_config = self.config.network['flaky'].split()
        self.traffic_control.netem(device, ["loss"] + flaky_config)

    def slow(self, device):
        slow_config = self.config.network['slow'].split()
        self.traffic_control.netem(device, ["delay"] + slow_config)

    def duplicate(self, device):
        duplicate_config = self.config.network['duplicate'].split()
        self.traffic_control.netem(device, ["duplicate"] + duplicate_config)

    def fast(self, device):
        self.traffic_control.restore(device)

    def restore(self, blockade_id):
        self.iptables.clear(blockade_id)

    def partition_containers(self, blockade_id, partitions):
        self.iptables.clear(blockade_id)
        self._partition_containers(blockade_id, partitions)

    def get_ip_partitions(self, blockade_id):
        return self.iptables.get_source_chains(blockade_id)

    def get_container_device(self, docker_client, container_id):
        container_idx = get_container_device_index(docker_client, container_id)

        # all my experiments showed the host device index was
        # one greater than its associated container device index
        host_idx = container_idx + 1

        cmd = 'ip link'
        try:
            host_res = self.host_exec.run(cmd)
        except Exception as e:
            _logger.error("error listing host network interfaces", exc_info=True)

            raise BlockadeError(
                "%s:\nerror listing host network interfaces with: "
                "'docker run --network=host %s %s':\n%s" %
                (_ERROR_NET_IFACE, IPTABLES_DOCKER_IMAGE, cmd, str(e)))

        host_rgx = '^%d: ([^:@]+)[:@]' % host_idx
        host_match = re.search(host_rgx, host_res, re.M)
        if host_match:
            return host_match.group(1)

        raise BlockadeError(
            "%s:\ncould not find expected host link %s for container %s."
            "'ip link' output:\n %s\n\nThis may be a Blockade bug, or "
            "there may be something unusual about your container network."
            % (_ERROR_NET_IFACE, host_idx, container_id, host_res))

    def _partition_containers(self, blockade_id, partitions):
        if not partitions or len(partitions) == 1:
            return

        # partitions without IP addresses can't be part of any
        # iptables rule anyway
        ip_partitions = [[c for c in parts if c.ip_address] for parts in partitions]

        all_nodes = frozenset(itertools.chain(*ip_partitions))

        for idx, chain_group in enumerate(_get_chain_groups(ip_partitions)):
            # create a new chain
            chain_name = partition_chain_name(blockade_id, idx+1)
            self.iptables.create_chain(chain_name)

            # direct all traffic of the chain group members to this chain
            for container in chain_group:
                self.iptables.insert_rule("FORWARD", src=container.ip_address, target=chain_name)

            def in_group(container):
                return any(container.name == x.name for x in chain_group)

            # block all transfer of partitions the containers of this chain group  are NOT part of
            chain_partition_members = set(itertools.chain(*[parts for parts in ip_partitions
                                                            if any(in_group(c) for c in parts)]))
            to_block = all_nodes - chain_partition_members

            for container in to_block:
                self.iptables.insert_rule(chain_name, dest=container.ip_address, target="DROP")


class _IPTables(object):

    def __init__(self, host_exec):
        self.host_exec = host_exec

    def call_output(self, *args):
        cmd = ["iptables", "-n"] + list(args)
        output = self.host_exec.run(cmd)
        return output.split('\n')

    def call(self, *args):
        cmd = ["iptables"] + list(args)
        return self.host_exec.run(cmd)

    def get_chain_rules(self, chain):
        if not chain:
            raise ValueError("invalid chain")
        lines = self.call_output("-L", chain)
        if len(lines) < 2:
            raise BlockadeError("Can't understand iptables output: \n%s" %
                                "\n".join(lines))

        chain_line, header_line = lines[:2]
        if not (chain_line.startswith("Chain " + chain) and
                header_line.startswith("target")):
            raise BlockadeError("Can't understand iptables output: \n%s" %
                                "\n".join(lines))
        return lines[2:]

    def get_source_chains(self, blockade_id):
        """Get a map of blockade chains IDs -> list of IPs targeted at them

        For figuring out which container is in which partition
        """
        result = {}
        if not blockade_id:
            raise ValueError("invalid blockade_id")
        lines = self.get_chain_rules("FORWARD")

        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                partition_index = parse_partition_index(blockade_id, parts[0])
            except ValueError:
                continue  # not a rule targetting a blockade chain

            source = parts[3]
            if source:
                result[source] = partition_index
        return result

    def delete_rules(self, chain, predicate):
        if not chain:
            raise ValueError("invalid chain")
        if not isinstance(predicate, collections.Callable):
            raise ValueError("invalid predicate")

        lines = self.get_chain_rules(chain)

        # TODO this is susceptible to check-then-act races.
        # better to ultimately switch to python-iptables if it becomes less buggy
        for index, line in reversed(list(enumerate(lines, 1))):
            line = line.strip()
            if line and predicate(line):
                self.call("-D", chain, str(index))

    def delete_blockade_rules(self, blockade_id):
        def predicate(rule):
            target = rule.split()[0]
            try:
                parse_partition_index(blockade_id, target)
            except ValueError:
                return False
            return True
        self.delete_rules("FORWARD", predicate)

    def delete_blockade_chains(self, blockade_id):
        if not blockade_id:
            raise ValueError("invalid blockade_id")

        lines = self.call_output("-L")
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "Chain":
                chain = parts[1]
                try:
                    parse_partition_index(blockade_id, chain)
                except ValueError:
                    continue
                # if we are a valid blockade chain, flush and delete
                self.call("-F", chain)
                self.call("-X", chain)

    def insert_rule(self, chain, src=None, dest=None, target=None):
        """Insert a new rule in the chain
        """
        if not chain:
            raise ValueError("Invalid chain")
        if not target:
            raise ValueError("Invalid target")
        if not (src or dest):
            raise ValueError("Need src, dest, or both")

        args = ["-I", chain]
        if src:
            args += ["-s", src]
        if dest:
            args += ["-d", dest]
        args += ["-j", target]
        self.call(*args)

    def create_chain(self, chain):
        """Create a new chain
        """
        if not chain:
            raise ValueError("Invalid chain")
        self.call("-N", chain)

    def clear(self, blockade_id):
        """Remove all iptables rules and chains related to this blockade
        """
        # first remove refererences to our custom chains
        self.delete_blockade_rules(blockade_id)

        # then remove the chains themselves
        self.delete_blockade_chains(blockade_id)


class _TrafficControl(object):
    def __init__(self, host_exec):
        self.host_exec = host_exec

    def restore(self, device):
        cmd = ["tc", "qdisc", "del", "dev", device, "root"]
        try:
            self.host_exec.run(cmd)
        except HostExecError as e:
            if e.exit_code == 2 and 'No such file or directory' in e.output:
                pass  # this is an expected condition
            else:
                raise


    def netem(self, device, params):
        cmd = ["tc", "qdisc", "replace", "dev", device,
               "root", "netem"] + params
        self.host_exec.run(cmd)

    def network_state(self, device):
        cmd = ["tc", "qdisc", "show", "dev", device]
        try:
            output = self.host_exec.run(cmd)
            # sloppy but good enough for now
            if " delay " in output:
                return NetworkState.SLOW
            if " loss " in output:
                return NetworkState.FLAKY
            if " duplicate " in output:
                return NetworkState.DUPLICATE
            return NetworkState.NORMAL
        except Exception:
            return NetworkState.UNKNOWN


def get_container_device_index(docker_client, container_id):
    cmd_args = ['cat', '/sys/class/net/eth0/ifindex']
    res = None
    try:
        exec_handle = docker_client.exec_create(container_id, cmd_args)
        res = docker_client.exec_start(exec_handle).decode('utf-8').strip()
    except Exception as e:
        if (isinstance(e, docker.errors.APIError) or
                isinstance(e, docker.errors.DockerException)):
            error_type = "Docker"
        else:
            error_type = "Unknown"
        raise BlockadeError(
            "%s:\n%s error attempting to exec '%s' in container %s:\n%s"
            % (_ERROR_NET_IFACE, error_type, ' '.join(cmd_args),
                container_id, str(e)))

    try:
        return int(res)
    except (ValueError, TypeError):
        raise BlockadeError(
            "%s:\nexec '%s' in container %s returned:\n%s\n\n"
            "Ensure the container is alive and supports this exec command."
            % (_ERROR_NET_IFACE, ' '.join(cmd_args),
                container_id, res))


def parse_partition_index(blockade_id, chain):
    prefix = "%s-p" % partition_chain_prefix(blockade_id)
    if chain and chain.startswith(prefix):
        try:
            return int(chain[len(prefix):])
        except ValueError:
            pass
    raise ValueError("chain %s is not a blockade partition" % (chain,))


def partition_chain_name(blockade_id, partition_index):
    return "%s-p%s" % (partition_chain_prefix(blockade_id), partition_index)


def partition_chain_prefix(blockade_id):
    prefix = "%s%s" % (BLOCKADE_CHAIN_PREFIX, blockade_id)
    return prefix[:MAX_CHAIN_PREFIX_LENGTH]


def _get_chain_groups(partitions):
    chains = []

    def find_partition(name):
        for idx, parts in enumerate(chains):
            in_partition = any(c.name == name for c in parts)
            if in_partition:
                return idx
        return None

    for partition in partitions:
        new_part = []
        for part in partition:
            in_partition = find_partition(part.name)
            if not in_partition is None:
                chains[in_partition].remove(part)
                chains.append(set([part]))
            else:
                new_part.append(part)
        if new_part:
            chains.append(set(new_part))

    # prune empty partitions
    return [x for x in chains if len(x) > 0]
