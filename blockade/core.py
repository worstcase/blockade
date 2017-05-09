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

from __future__ import print_function

import logging

import docker
import errno
import random
import six
import sys
import time

from blockade import audit
from .errors import AlreadyInitializedError
from .errors import BlockadeContainerConflictError
from .errors import BlockadeError
from .errors import DockerContainerNotFound
from .errors import InsufficientPermissionsError
from .net import NetworkState
from .state import BlockadeState


# TODO: configurable timeout
DEFAULT_KILL_TIMEOUT = 3

_logger = logging.getLogger(__name__)


class Blockade(object):
    def __init__(self, config, blockade_id=None, state=None,
                 network=None, docker_client=None):
        self.config = config
        self.state = state or BlockadeState(blockade_id=blockade_id)
        self.network = network
        try:
            self._audit = audit.EventAuditor(self.state.get_audit_file())
        except Exception as ex:
            _logger.exception(ex)
            raise

        default_client = docker.APIClient(
            **docker.utils.kwargs_from_env(assert_hostname=False)
        )
        self.docker_client = docker_client or default_client

    def create(self, verbose=False, force=False):
        container_state = {}

        num_containers = len(self.config.sorted_containers)

        # we can check if a state file already exists beforehand
        if self.state.exists():
            raise AlreadyInitializedError('a blockade already exists in here - '
                                          'you may want to destroy it first')

        def vprint(msg):
            if verbose:
                sys.stdout.write(msg)
                sys.stdout.flush()

        if self.config.is_udn():
            # Create custom network to allow docker resolve container hostnames
            # via built-in DNS server.
            response = self.docker_client.create_network(
                                            self.state.blockade_net_name)
            if response['Warning']:
                raise BlockadeError("Error while creating network: '%s'" %
                    (response['Warning']))

        for idx, container in enumerate(self.config.sorted_containers):
            name = container.name

            vprint("\r[%d/%d] Starting '%s' " % (idx+1, num_containers, name))

            # in case a startup delay is configured
            # we have to wait in here
            if container.start_delay > 0:
                vprint('(delaying for %s seconds)' % (container.start_delay))
                time.sleep(container.start_delay)

            container_id = self._start_container(container, force)
            container_state[name] = {'id': container_id}

        # clear progress line
        vprint('\r')

        # try to persist container states
        self.state.initialize(container_state)

        container_descriptions = []
        for container in self.config.sorted_containers:
            description = self._get_container_description(container.name)
            container_descriptions.append(description)

        return container_descriptions

    def _get_device_id(self, container_id, container_name):
        # next we have to determine the veth pair of host/container
        # that we formerly could pass in via 'lxc_conf' which is
        # deprecated since docker > 1.6
        device = None
        try:
            device = self.network.get_container_device(self.docker_client, container_id)
        except OSError as err:
            if err.errno in (errno.EACCES, errno.EPERM):
                msg = "Failed to determine network device of container '%s' [%s]" % (container_name, container_id)
                raise InsufficientPermissionsError(msg)
            raise
        return device

    def __get_container_links(self, container):
        links = {}
        for link, alias in container.links.items():
            link_container = self.config.containers.get(link, None)
            if not link_container:
                raise BlockadeError("link '%s' of container '%s' does not exist" %
                                    (link, container.name))
            name = link_container.get_name(self.state.blockade_id)
            links[name] = alias
        return links

    def _start_container(self, container, force=False):
        container_name = container.get_name(self.state.blockade_id)
        volumes = list(container.volumes.values()) or None
        links = self.__get_container_links(container)

        # the docker api for port bindings is `internal:external`
        port_bindings = dict((v, k) for k, v in container.publish_ports.items())

        if self.config.is_udn():
            network_mode = self.state.blockade_net_name
        else:
            network_mode = None

        host_config = self.docker_client.create_host_config(
            binds=container.volumes,
            dns=container.dns,
            port_bindings=port_bindings,
            network_mode=network_mode,
            ulimits=[{'name': 'core', 'soft': 3145728, 'hard': 4194304}],
            links=links,
            cap_add=container.cap_add)

        def create_container():
            # try to create container
            response = self.docker_client.create_container(
                container.image,
                command=container.command,
                name=container_name,
                ports=container.expose_ports,
                volumes=volumes,
                hostname=container.hostname,
                environment=container.environment,
                host_config=host_config,
                labels={"blockade.id": self.state.blockade_id})
            return response['Id']

        try:
            container_id = create_container()
        except docker.errors.APIError as err:
            if err.response.status_code == 409 and err.is_client_error():
                # if force is set we are retrying after removing the
                # container with that name first
                if force and self.__try_remove_container(container_name):
                    container_id = create_container()
                else:
                    raise BlockadeContainerConflictError(err)
            else:
                raise

        # start container
        self.docker_client.start(container_id)
        return container_id

    def __try_remove_container(self, name):
        try:
            self.docker_client.remove_container(name, force=True)
            return True
        except Exception:
            # TODO: log error?
            return False

    def _get_container_description(self, name, network_state=True,
                                   ip_partitions=None):
        self.state.load()
        state_container = self.state.containers[name]
        container_id = state_container['id']

        try:
            container = self._inspect_container(container_id)
        except DockerContainerNotFound:
            return Container(name, container_id, ContainerStatus.MISSING)

        state_dict = container.get('State')
        if state_dict and state_dict.get('Running'):
            container_status = ContainerStatus.UP
        else:
            container_status = ContainerStatus.DOWN

        extras = {}
        network = container.get('NetworkSettings')
        ip = None
        if network:
            ip = network.get('IPAddress')
            networks = network.get('Networks')
            if self.config.is_udn():
                ip = networks.get(
                        self.state.blockade_net_name).get('IPAddress')
            elif networks and not ip:
                if len(networks) == 1:
                    ip = six.next(six.itervalues(networks)).get('IPAddress')

            if ip:
                extras['ip_address'] = ip

        if (network_state and name in self.state.containers
                and container_status == ContainerStatus.UP):
            device = self._get_device_id(container_id, name)
            extras['device'] = device
            extras['network_state'] = self.network.network_state(device)

            # include partition ID if we were provided a map of them
            if ip_partitions and ip:
                extras['partition'] = ip_partitions.get(ip)
        else:
            extras['network_state'] = NetworkState.UNKNOWN
            extras['device'] = None

        # lookup 'holy' and 'neutral' containers
        # TODO: this might go into the state as well..?
        cfg_container = self.config.containers.get(name)
        extras['neutral'] = cfg_container.neutral if cfg_container else False
        extras['holy'] = cfg_container.holy if cfg_container else False

        return Container(name, container_id, container_status, **extras)

    def destroy(self, force=False):
        containers = self._get_blockade_docker_containers()
        for container in list(containers.values()):
            container_id = container['Id']
            self.docker_client.stop(container_id, timeout=DEFAULT_KILL_TIMEOUT)
            self.docker_client.remove_container(container_id)

        self.network.restore(self.state.blockade_id)
        self.state.destroy()

        if self.config.is_udn():
            try:
                self.docker_client.remove_network(self.state.blockade_net_name)
            except docker.errors.APIError as err:
                if err.response.status_code != 404:
                    raise

    # Get the containers that are part of the initial Blockade group
    def _get_blockade_docker_containers(self):
        self.state.load()
        containers = {}
        filters = {"label": ["blockade.id=" + self.state.blockade_id]}
        prefix = self.state.blockade_id + "_"
        for container in self.docker_client.containers(all=True, filters=filters):
            for name in container['Names']:
                # strip leading '/'
                name = name[1:] if name[0] == '/' else name

                # strip prefix. containers will have these UNLESS `container_name`
                # was specified in the config
                name = name[len(prefix):] if name.startswith(prefix) else name
                if name in self.state.containers:
                    containers[name] = container
                    break
        return containers

    def _get_docker_containers(self):
        self.state.load()
        containers = self._get_blockade_docker_containers()
        # Search for and add any containers that were added to the state
        for state_container_name in self.state.containers:
            if state_container_name not in containers.keys():
                container_id = self.state.container_id(state_container_name)
                filters = {"id": container_id}
                for container in self.docker_client.containers(all=True, filters=filters):
                    containers[state_container_name] = container
        return containers

    def _get_all_containers(self):
        self.state.load()
        containers = []
        ip_partitions = self.network.get_ip_partitions(self.state.blockade_id)
        docker_containers = self._get_docker_containers()

        for name in docker_containers.keys():
            container = self._get_container_description(name, ip_partitions=ip_partitions)
            containers.append(container)

        return containers

    def status(self):
        return self._get_all_containers()

    def _get_running_containers(self, container_names=None, select_random=False):
        return self._get_containers_with_state(container_names, select_random, ContainerStatus.UP)

    def _get_created_containers(self, container_names=None, select_random=False):
        return self._get_containers_with_state(container_names, select_random,
                                               ContainerStatus.UP, ContainerStatus.DOWN)

    def _get_containers_with_state(self, container_names, select_random, *container_states):
        containers = self._get_all_containers()

        candidates = dict((c.name, c) for c in containers
                       if c.status in container_states)

        if select_random and candidates:
            return [random.choice(list(candidates.values()))]

        if container_names is None:
            return list(candidates.values())

        found = []
        for name in container_names:
            container = candidates.get(name)
            if not container:
                raise BlockadeError("Container %s is not found or not any of %s"
                                    % (name, container_states))
            found.append(container)
        return found

    def _get_running_container(self, container_name):
        return self._get_running_containers((container_name,))[0]

    def __with_running_container_device(self, container_names, func, select_random=False):
        message = ""
        audit_status = "Success"
        try:
            containers = self._get_running_containers(container_names, select_random)
            container_names = [c.name for c in containers]
            for container in containers:
                device = self._get_device_id(container.container_id, container.name)
                func(device)
            return container_names
        except Exception as ex:
            audit_status = "Failed"
            message = str(ex)
            raise
        finally:
            self._audit.log_event(func.__name__, audit_status, message,
                                  container_names)

    def flaky(self, container_names, select_random=False):
        return self.__with_running_container_device(container_names, self.network.flaky, select_random)

    def slow(self, container_names, select_random=False):
        return self.__with_running_container_device(container_names, self.network.slow, select_random)

    def duplicate(self, container_names, select_random=False):
        return self.__with_running_container_device(container_names, self.network.duplicate, select_random)

    def fast(self, container_names, select_random=False):
        return self.__with_running_container_device(container_names, self.network.fast, select_random)

    def restart(self, container_names, select_random=False):
        message = ""
        audit_status = "Success"
        try:
            containers = self._get_running_containers(container_names, select_random)
            container_names = [c.name for c in containers]
            for container in containers:
                self._stop(container)
                self._start(container.name)
            return container_names
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('restart', audit_status, message,
                                  container_names)

    def kill(self, container_names, signal="SIGKILL", select_random=False):
        message = ''
        audit_status = "Success"
        try:
            containers = self._get_running_containers(container_names, select_random)
            container_names = [c.name for c in containers]
            for container in containers:
                self._kill(container, signal)
            return container_names
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('kill', audit_status, message,
                                  container_names)

    def _kill(self, container, signal):
        self.docker_client.kill(container.container_id, signal)

    def stop(self, container_names, select_random=False):
        message = ''
        audit_status = "Success"
        try:
            # it is valid to try to stop an already stopped container
            containers = self._get_created_containers(container_names, select_random)
            container_names = [c.name for c in containers]
            for container in containers:
                self._stop(container)
            return container_names
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('stop', audit_status, message,
                                  container_names)

    def _stop(self, container):
        self.docker_client.stop(container.container_id, timeout=DEFAULT_KILL_TIMEOUT)

    def start(self, container_names, select_random=False):
        message = ''
        audit_status = "Success"
        try:
            # it is valid to try to start an already running container
            containers = self._get_created_containers(container_names, select_random)
            container_names = [c.name for c in containers]
            for container in container_names:
                self._start(container)
            return container_names
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('start', audit_status, message,
                                  container_names)

    def _start(self, container):
        container_id = self.state.container_id(container)
        if container_id is None:
            return

        # TODO: determine between create and/or start?
        self.docker_client.start(container_id)
        # update state
        updated_containers = self.state.containers
        updated_containers[container] = {'id': container_id}

    def random_partition(self):
        containers = [c.name for c in self._get_running_containers()
                      if not c.holy]

        # no containers to partition
        if not containers:
            return []

        num_containers = len(containers)
        num_partitions = random.randint(1, num_containers)

        # no partition at all -> join
        if num_partitions <= 1:
            self.join()
            return []
        else:
            pick = lambda: containers.pop(random.randint(0, len(containers)-1))

            # pick at least one container for each partition
            partitions = [[pick()] for _ in xrange(num_partitions)]

            # distribute the rest of the containers among the partitions
            for _ in xrange(len(containers)):
                random_partition = random.randint(0, num_partitions-1)
                partitions[random_partition].append(pick())

            self.partition(partitions)
            return partitions

    def partition(self, partitions):
        message = ''
        audit_status = "Success"
        try:
            containers = self._get_running_containers()
            container_dict = dict((c.name, c) for c in containers)
            partitions = expand_partitions(containers, partitions)

            container_partitions = []
            for partition in partitions:
                container_partitions.append([container_dict[c] for c in partition])

            self.network.partition_containers(self.state.blockade_id,
                                              container_partitions)
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('partition', audit_status, message,
                                  partitions)

    def join(self):
        message = ''
        audit_status = "Success"
        try:
            self.state.load()
            self.network.restore(self.state.blockade_id)
        except Exception as ex:
            message = str(ex)
            audit_status = "Failed"
            raise
        finally:
            self._audit.log_event('join', audit_status, message, [])

    def logs(self, container_name):
        container = self._get_running_container(container_name)
        return self.docker_client.logs(container.container_id)

    def _inspect_container(self, container_id):
        try:
            return self.docker_client.inspect_container(container_id)
        except docker.errors.APIError as err:
            if err.response.status_code == 404:
                err_msg = "Aborting. Docker container not found: %s"
                raise DockerContainerNotFound(err_msg % container_id)
            else:
                raise

    # containers can be the Docker ID or name
    def add_container(self, containers):
        if self.state.exists():
            self.state.load()

        updated_containers = self.state.containers
        for container in containers:
            container_info = self._inspect_container(container)
            container_id = container_info.get('Id')
            if container_id.startswith(container):
                # if container is the docker id, use the partial docker id
                name = container_id[:12]
            else:
                name = container

            # check if this name is already in the state file
            if self.state.container_id(name) is not None:
                continue
            updated_containers[name] = {'id': container_id}
        # persist the state
        self.state.update(updated_containers)

    def get_audit(self):
        return self._audit


class Container(object):
    ip_address = None
    network_state = NetworkState.NORMAL
    partition = None

    def __init__(self, name, container_id, status, **kwargs):
        self.name = name
        self.container_id = container_id
        self.status = status
        self.holy = False
        self.neutral = False

        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return dict(name=self.name,
                    container_id=self.container_id,
                    status=self.status,
                    ip_address=self.ip_address,
                    network_state=self.network_state,
                    partition=self.partition)


class ContainerStatus(object):
    '''Possible container status
    '''
    UP = "UP"
    DOWN = "DOWN"
    MISSING = "MISSING"


def expand_partitions(containers, partitions):
    '''
    Validate the partitions of containers. If there are any containers
    not in any partition, place them in an new partition.
    '''

    # filter out holy containers that don't belong
    # to any partition at all
    all_names = frozenset(c.name for c in containers if not c.holy)
    holy_names = frozenset(c.name for c in containers if c.holy)
    neutral_names = frozenset(c.name for c in containers if c.neutral)
    partitions = [frozenset(p) for p in partitions]

    unknown = set()
    holy = set()
    union = set()

    for partition in partitions:
        unknown.update(partition - all_names - holy_names)
        holy.update(partition - all_names)
        union.update(partition)

    if unknown:
        raise BlockadeError('Partitions contain unknown containers: %s' %
                            list(unknown))

    if holy:
        raise BlockadeError('Partitions contain holy containers: %s' %
                            list(holy))

    # put any leftover containers in an implicit partition
    leftover = all_names.difference(union)
    if leftover:
        partitions.append(leftover)

    # we create an 'implicit' partition for the neutral containers
    # in case they are not part of the leftover anyways
    if not neutral_names.issubset(leftover):
        partitions.append(neutral_names)

    return partitions
