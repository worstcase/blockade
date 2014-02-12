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

from copy import deepcopy

import docker

from .errors import BlockadeError
from .net import NetworkState, BlockadeNetwork
from .state import BlockadeStateFactory


class Blockade(object):
    def __init__(self, config, state_factory=None, network=None,
                 docker_client=None):
        self.config = config
        self.state_factory = state_factory or BlockadeStateFactory()
        self.network = network or BlockadeNetwork(config)
        self.docker_client = docker_client or docker.Client()

    def create(self):
        container_state = {}
        for container in self.config.sorted_containers:
            veth_device = self.network.new_veth_device_name()
            container_state[container.name] = {"veth_device": veth_device}

        # generate blockade ID and persist
        state = self.state_factory.initialize(container_state)

        container_descriptions = []
        for container in self.config.sorted_containers:
            veth_device = container_state[container.name]['veth_device']
            container_id = self._start_container(state.blockade_id, container,
                                                 veth_device)
            description = self._get_container_description(
                state, container.name, container_id)
            container_descriptions.append(description)

        return container_descriptions

    def _start_container(self, blockade_id, container, veth_device):
        container_name = docker_container_name(blockade_id, container.name)
        volumes = list(container.volumes.values()) or None
        response = self.docker_client.create_container(
            container.image, command=container.command, name=container_name,
            ports=container.ports, volumes=volumes, hostname=container.name,
            environment=container.environment)
        container_id = response['Id']

        links = dict((docker_container_name(blockade_id, link), alias)
                     for link, alias in container.links.items())

        lxc_conf = deepcopy(container.lxc_conf)
        lxc_conf['lxc.network.veth.pair'] = veth_device
        self.docker_client.start(container_id, lxc_conf=lxc_conf, links=links,
                                 binds=container.volumes)
        return container_id

    def _get_container_description(self, state, name, container_id,
                                   network_state=True, ip_partitions=None):
        try:
            container = self.docker_client.inspect_container(container_id)
        except docker.APIError as e:
            if e.response.status_code == 404:
                return Container(name, container_id, ContainerState.MISSING)
            else:
                raise

        state_dict = container.get('State')
        if state_dict and state_dict.get('Running'):
            container_state = ContainerState.UP
        else:
            container_state = ContainerState.DOWN

        extras = {}
        network = container.get('NetworkSettings')
        ip = None
        if network:
            ip = network.get('IPAddress')
            if ip:
                extras['ip_address'] = ip

        if (network_state and name in state.containers
                and container_state == ContainerState.UP):
            device = state.containers[name]['veth_device']
            extras['veth_device'] = device
            extras['network_state'] = self.network.network_state(device)

            # include partition ID if we were provided a map of them
            if ip_partitions and ip:
                extras['partition'] = ip_partitions.get(ip)
        else:
            extras['network_state'] = NetworkState.UNKNOWN
            extras['veth_device'] = None

        return Container(name, container_id, container_state, **extras)

    def destroy(self, force=False):
        state = self.state_factory.load()

        containers = self._get_docker_containers(state.blockade_id)
        for container in list(containers.values()):
            container_id = container['Id']
            self.docker_client.stop(container_id, timeout=3)
            self.docker_client.remove_container(container_id)

        self.network.restore(state.blockade_id)
        self.state_factory.destroy()

    def _get_docker_containers(self, blockade_id):
        # look for containers prefixed with our blockade ID
        prefix = "/" + blockade_id + "-"
        d = {}
        for container in self.docker_client.containers(all=True):
            for name in container['Names']:
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    d[name] = container
                    break
        return d

    def _get_all_containers(self, state):
        containers = []
        ip_partitions = self.network.get_ip_partitions(state.blockade_id)
        docker_containers = self._get_docker_containers(state.blockade_id)
        for name, container in docker_containers.items():
            containers.append(self._get_container_description(state, name,
                              container['Id'], ip_partitions=ip_partitions))
        return containers

    def status(self):
        state = self.state_factory.load()
        return self._get_all_containers(state)

    def _get_running_containers(self, container_names=None, state=None):
        state = state or self.state_factory.load()
        containers = self._get_all_containers(state)

        running = dict((c.name, c) for c in containers
                       if c.state == ContainerState.UP)
        if container_names is None:
            return list(running.values())

        found = []
        for name in container_names:
            container = running.get(name)
            if not container:
                raise BlockadeError("Container %s is not found or not running"
                                    % (name,))
            found.append(container)
        return found

    def _get_running_container(self, container_name, state=None):
        return self._get_running_containers((container_name,), state)[0]

    def flaky(self, container_names=None, include_all=False):
        if include_all:
            container_names = None
        containers = self._get_running_containers(container_names)
        for container in containers:
            self.network.flaky(container.veth_device)

    def slow(self, container_names=None, include_all=False):
        if include_all:
            container_names = None
        containers = self._get_running_containers(container_names)
        for container in containers:
            self.network.slow(container.veth_device)

    def fast(self, container_names=None, include_all=False):
        if include_all:
            container_names = None
        containers = self._get_running_containers(container_names)
        for container in containers:
            self.network.fast(container.veth_device)

    def partition(self, partitions):
        state = self.state_factory.load()
        containers = self._get_running_containers(state=state)
        container_dict = dict((c.name, c) for c in containers)
        partitions = expand_partitions(list(container_dict.keys()), partitions)

        container_partitions = []
        for partition in partitions:
            container_partitions.append([container_dict[c] for c in partition])

        self.network.partition_containers(state.blockade_id,
                                          container_partitions)

    def join(self):
        state = self.state_factory.load()
        self.network.restore(state.blockade_id)

    def logs(self, container_name):
        container = self._get_running_container(container_name)
        return self.docker_client.logs(container.container_id)


class Container(object):
    ip_address = None
    veth_device = None
    network_state = NetworkState.NORMAL
    partition = None

    def __init__(self, name, container_id, state, **kwargs):
        self.name = name
        self.container_id = container_id
        self.state = state
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return dict(name=self.name, container_id=self.container_id,
                    state=self.state, ip_address=self.ip_address,
                    veth_device=self.veth_device,
                    network_state=self.network_state,
                    partition=self.partition)


class ContainerState(object):
    UP = "UP"
    DOWN = "DOWN"
    MISSING = "MISSING"


def docker_container_name(blockade_id, name):
    return '-'.join((blockade_id, name))


def expand_partitions(containers, partitions):
    """Validate the partitions of containers. If there are any containers
    not in any partition, place them in an new partition.
    """
    all_names = frozenset(containers)
    partitions = [frozenset(p) for p in partitions]

    unknown = set()
    overlap = set()
    union = set()

    for index, partition in enumerate(partitions):
        unknown.update(partition - all_names)
        union.update(partition)

        for other in partitions[index+1:]:
            overlap.update(partition.intersection(other))

    if unknown:
        raise BlockadeError("Partitions have unknown containers: %s" %
                            list(unknown))

    if overlap:
        raise BlockadeError("Partitions have overlapping containers: %s" %
                            list(overlap))

    # put any leftover containers in an implicit partition
    leftover = all_names.difference(union)
    if leftover:
        partitions.append(leftover)

    return partitions
