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

import collections
import numbers
import os
import re

from .errors import BlockadeConfigError


class BlockadeContainerConfig(object):
    '''Class that encapsulates the configuration of one container
    '''

    @staticmethod
    def from_dict(name, values):
        '''
        Convert a dictionary of configuration values
        into a sequence of BlockadeContainerConfig instances
        '''

        # determine the number of instances of this container
        count = 1
        count_value = values.get('count', 1)
        if isinstance(count_value, int):
            count = max(count_value, 1)

        def with_index(name, idx):
            if name and idx:
                return '%s_%d' % (name, idx)
            return name

        def get_instance(n, idx=None):
            return BlockadeContainerConfig(
                with_index(n, idx),
                values['image'],
                command=values.get('command'),
                links=values.get('links'),
                volumes=values.get('volumes'),
                publish_ports=values.get('ports'),
                expose_ports=values.get('expose'),
                environment=values.get('environment'),
                hostname=values.get('hostname'),
                dns=values.get('dns'),
                start_delay=values.get('start_delay', 0),
                neutral=values.get('neutral', False),
                holy=values.get('holy', False),
                container_name=with_index(values.get('container_name'), idx),
                cap_add=values.get('cap_add'))

        if count == 1:
            yield get_instance(name)
        else:
            for idx in range(1, count+1):
                # TODO: configurable name/index format
                yield get_instance(name, idx)

    def __init__(self, name, image, command=None, links=None, volumes=None,
                 publish_ports=None, expose_ports=None, environment=None,
                 hostname=None, dns=None, start_delay=0, neutral=False,
                 holy=False, container_name=None, cap_add=None):
        self.name = name
        self.hostname = hostname
        self.dns = dns
        self.image = image
        self.command = command
        self.links = _dictify(links, 'links')
        self.volumes = _dictify(volumes, 'volumes', lambda x: os.path.abspath(_populate_env(x)))
        self.publish_ports = _dictify(publish_ports, 'ports')
        self.neutral = neutral
        self.holy = holy
        self.container_name = container_name
        self.cap_add = cap_add

        if neutral and holy:
            raise BlockadeConfigError("container must not be 'neutral' and 'holy' at the same time")

        # check start_delay format
        if not (isinstance(start_delay, numbers.Number) and start_delay >= 0):
            raise BlockadeConfigError("'start_delay' must be numeric and non-negative")

        self.start_delay = start_delay

        # all published ports must also be exposed
        self.expose_ports = list(set(
            int(port) for port in
            (expose_ports or []) + list(self.publish_ports.values())
        ))

        self.environment = _dictify(environment, _populate_env, _populate_env)

    def get_name(self, blockade_id):
        if self.container_name:
            return self.container_name
        return '_'.join((blockade_id, self.name))


_DEFAULT_NETWORK_CONFIG = {
    "driver": "default",
    "flaky": "30%",
    "slow": "75ms 100ms distribution normal",
    "duplicate": "5%",
}


class BlockadeConfig(object):
    @staticmethod
    def from_dict(values):
        '''
        Instantiate a BlockadeConfig instance based on
        a given dictionary of configuration values
        '''
        try:
            containers = values['containers']
            parsed_containers = {}
            for name, container_dict in containers.items():
                try:
                    # one config entry might result in many container
                    # instances (indicated by the 'count' config value)
                    for cnt in BlockadeContainerConfig.from_dict(name, container_dict):
                        # check for duplicate 'container_name' definitions
                        if cnt.container_name:
                            cname = cnt.container_name
                            existing = [c for c in parsed_containers.values() if c.container_name == cname]
                            if existing:
                                raise BlockadeConfigError("Duplicate 'container_name' definition: %s" % (cname))
                        parsed_containers[cnt.name] = cnt
                except Exception as err:
                    raise BlockadeConfigError(
                        "Container '%s' config problem: %s" % (name, err))

            network = values.get('network')
            if network:
                defaults = _DEFAULT_NETWORK_CONFIG.copy()
                defaults.update(network)
                network = defaults
            else:
                network = _DEFAULT_NETWORK_CONFIG.copy()

            return BlockadeConfig(parsed_containers, network=network)

        except KeyError as err:
            raise BlockadeConfigError("Config missing value: " + str(err))

        except Exception as err:
            # TODO log this to some debug stream?
            raise BlockadeConfigError("Failed to load config: " + str(err))

    def is_udn(self):
        return self.network['driver'] == 'udn'

    def __init__(self, containers = {}, network=None):
        self.containers = containers
        self.sorted_containers = dependency_sorted(containers)
        self.network = network or _DEFAULT_NETWORK_CONFIG.copy()


def _populate_env(value):
    cwd = os.getcwd()
    # in here we may place some 'special' placeholders
    # that get replaced by blockade itself
    builtins = {
        # usually $PWD is set by the shell anyway but
        # blockade is often used in terms of sudo that sometimes
        # removes various environment variables
        'PWD': cwd,
        'CWD': cwd
        }

    def get_env_value(match):
        key = match.group(1)
        env = os.environ.get(key) or builtins.get(key)
        if not env:
            raise BlockadeConfigError("there is no environment variable '$%s'" % (key))
        return env
    return re.sub(r"\${([a-zA-Z][-_a-zA-Z0-9]*)}", get_env_value, value)


def _dictify(data, name='input', key_mod=lambda x: x, value_mod=lambda x: x):
    if data:
        if isinstance(data, collections.Sequence):
            return dict((key_mod(str(v)), value_mod(str(v))) for v in data)
        elif isinstance(data, collections.Mapping):
            return dict((key_mod(str(k)), value_mod(str(v or k))) for k, v in list(data.items()))
        else:
            raise BlockadeConfigError("invalid %s: need list or map"
                                      % (name,))
    else:
        return {}


def dependency_sorted(containers):
    """Sort a dictionary or list of containers into dependency order

    Returns a sequence
    """
    if not isinstance(containers, collections.Mapping):
        containers = dict((c.name, c) for c in containers)

    container_links = dict((name, set(c.links.keys()))
                           for name, c in containers.items())
    sorted_names = _resolve(container_links)
    return [containers[name] for name in sorted_names]


def _resolve(d):
    all_keys = frozenset(d.keys())
    result = []
    resolved_keys = set()

    # TODO: take start delays into account as well

    while d:
        resolved_this_round = set()
        for name, links in list(d.items()):
            # containers with no links can be started in any order.
            # containers whose parent containers have already been resolved
            # can be added now too.
            if not links or links <= resolved_keys:
                result.append(name)
                resolved_this_round.add(name)
                del d[name]

            # guard against containers which link to unknown containers
            unknown = links - all_keys
            if len(unknown) == 1:
                raise BlockadeConfigError(
                    "container %s links to unknown container %s" %
                    (name, list(unknown)[0]))
            elif len(unknown) > 1:
                raise BlockadeConfigError(
                    "container %s links to unknown containers %s" %
                    (name, unknown))

        # if we made no progress this round, we have a circular dep
        if not resolved_this_round:
            raise BlockadeConfigError("containers have circular links!")

        resolved_keys.update(resolved_this_round)

    return result
