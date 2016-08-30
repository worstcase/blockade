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

from .errors import BlockadeError, InsufficientPermissionsError
from .utils import docker_run

import collections
import itertools
import re

BLOCKADE_CHAIN_PREFIX = "blockade-"
IPTABLES_DOCKER_IMAGE = "vimagick/iptables:latest"


class NetworkState(object):
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    FLAKY = "FLAKY"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class BlockadeNetwork(object):
    def __init__(self, config):
        self.config = config

    def network_state(self, device):
        return network_state(device)

    def flaky(self, device):
        flaky_config = self.config.network['flaky'].split()
        traffic_control_netem(device, ["loss"] + flaky_config)

    def slow(self, device):
        slow_config = self.config.network['slow'].split()
        traffic_control_netem(device, ["delay"] + slow_config)

    def duplicate(self, device):
        duplicate_config = self.config.network['duplicate'].split()
        traffic_control_netem(device, ["duplicate"] + duplicate_config)

    def fast(self, device):
        traffic_control_restore(device)

    def restore(self, blockade_id):
        clear_iptables(blockade_id)

    def partition_containers(self, blockade_id, partitions):
        clear_iptables(blockade_id)
        partition_containers(blockade_id, partitions)

    def get_ip_partitions(self, blockade_id):
        return iptables_get_source_chains(blockade_id)

    def get_container_device(self, docker_client, container_id):
        exec_handle = docker_client.exec_create(container_id, ['ip', 'link', 'show', 'eth0'])
        res = docker_client.exec_start(exec_handle).decode('utf-8')
        device = re.search('^([0-9]+):', res)
        if not device:
            raise BlockadeError(
                "Problem determining host network device for container '%s'" %
                (container_id))

        peer_idx = int(device.group(1))

        # all my experiments showed the host device index was
        # one greater than its associated container device index
        host_idx = peer_idx + 1
        host_res = docker_run('ip link', image=IPTABLES_DOCKER_IMAGE)

        host_rgx = '^%d: ([^:@]+)[:@]' % host_idx
        host_match = re.search(host_rgx, host_res, re.M)
        if not host_match:
            raise BlockadeError(
                "Problem determining host network device for container '%s'" %
                (container_id))

        host_device = host_match.group(1)

        return host_device


def parse_partition_index(blockade_id, chain):
    prefix = "%s%s-p" % (BLOCKADE_CHAIN_PREFIX, blockade_id)
    if chain and chain.startswith(prefix):
        try:
            return int(chain[len(prefix):])
        except ValueError:
            pass
    raise ValueError("chain %s is not a blockade partition" % (chain,))


def partition_chain_name(blockade_id, partition_index):
    return "%s%s-p%s" % (BLOCKADE_CHAIN_PREFIX, blockade_id, partition_index)


def iptables_call_output(*args):
    cmd = ["iptables", "-n"] + list(args)
    output = docker_run(' '.join(cmd), image=IPTABLES_DOCKER_IMAGE)
    return output.split('\n')


def iptables_call(*args):
    cmd = ["iptables"] + list(args)
    return docker_run(' '.join(cmd), image=IPTABLES_DOCKER_IMAGE)


def iptables_get_chain_rules(chain):
    if not chain:
        raise ValueError("invalid chain")
    lines = iptables_call_output("-L", chain)
    if len(lines) < 2:
        raise BlockadeError("Can't understand iptables output: \n%s" %
                            "\n".join(lines))

    chain_line, header_line = lines[:2]
    if not (chain_line.startswith("Chain " + chain) and
            header_line.startswith("target")):
        raise BlockadeError("Can't understand iptables output: \n%s" %
                            "\n".join(lines))
    return lines[2:]


def iptables_get_source_chains(blockade_id):
    """Get a map of blockade chains IDs -> list of IPs targeted at them

    For figuring out which container is in which partition
    """
    result = {}
    if not blockade_id:
        raise ValueError("invalid blockade_id")
    lines = iptables_get_chain_rules("FORWARD")

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


def iptables_delete_rules(chain, predicate):
    if not chain:
        raise ValueError("invalid chain")
    if not isinstance(predicate, collections.Callable):
        raise ValueError("invalid predicate")

    lines = iptables_get_chain_rules(chain)

    # TODO this is susceptible to check-then-act races.
    # better to ultimately switch to python-iptables if it becomes less buggy
    for index, line in reversed(list(enumerate(lines, 1))):
        line = line.strip()
        if line and predicate(line):
            iptables_call("-D", chain, str(index))


def iptables_delete_blockade_rules(blockade_id):
    def predicate(rule):
        target = rule.split()[0]
        try:
            parse_partition_index(blockade_id, target)
        except ValueError:
            return False
        return True
    iptables_delete_rules("FORWARD", predicate)


def iptables_delete_blockade_chains(blockade_id):
    if not blockade_id:
        raise ValueError("invalid blockade_id")

    lines = iptables_call_output("-L")
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "Chain":
            chain = parts[1]
            try:
                parse_partition_index(blockade_id, chain)
            except ValueError:
                continue
            # if we are a valid blockade chain, flush and delete
            iptables_call("-F", chain)
            iptables_call("-X", chain)


def iptables_insert_rule(chain, src=None, dest=None, target=None):
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
    iptables_call(*args)


def iptables_create_chain(chain):
    """Create a new chain
    """
    if not chain:
        raise ValueError("Invalid chain")
    iptables_call("-N", chain)


def clear_iptables(blockade_id):
    """Remove all iptables rules and chains related to this blockade
    """
    # first remove refererences to our custom chains
    iptables_delete_blockade_rules(blockade_id)

    # then remove the chains themselves
    iptables_delete_blockade_chains(blockade_id)


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


def partition_containers(blockade_id, partitions):
    if not partitions or len(partitions) == 1:
        return

    # partitions without IP addresses can't be part of any
    # iptables rule anyway
    ip_partitions = [[c for c in parts if c.ip_address] for parts in partitions]

    all_nodes = frozenset(itertools.chain(*ip_partitions))

    for idx, chain_group in enumerate(_get_chain_groups(ip_partitions)):
        # create a new chain
        chain_name = partition_chain_name(blockade_id, idx+1)
        iptables_create_chain(chain_name)

        # direct all traffic of the chain group members to this chain
        for container in chain_group:
            iptables_insert_rule("FORWARD", src=container.ip_address, target=chain_name)

        def in_group(container):
            return any(container.name == x.name for x in chain_group)

        # block all transfer of partitions the containers of this chain group  are NOT part of
        chain_partition_members = set(itertools.chain(*[parts for parts in ip_partitions
                                                        if any(in_group(c) for c in parts)]))
        to_block = all_nodes - chain_partition_members

        for container in to_block:
            iptables_insert_rule(chain_name, dest=container.ip_address, target="DROP")


def traffic_control_restore(device):
    cmd = ["tc", "qdisc", "del", "dev", device, "root"]
    docker_run(' '.join(cmd), image=IPTABLES_DOCKER_IMAGE)


def traffic_control_netem(device, params):
    cmd = ["tc", "qdisc", "replace", "dev", device,
           "root", "netem"] + params
    docker_run(' '.join(cmd), image=IPTABLES_DOCKER_IMAGE)


def network_state(device):
    cmd = ["tc", "qdisc", "show", "dev", device]
    try:
        output = docker_run(' '.join(cmd), image=IPTABLES_DOCKER_IMAGE)
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
