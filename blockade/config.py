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
        if isinstance(count_value, (int, long)):
            count = max(count_value, 1)

        def get_instance(n):
            return BlockadeContainerConfig(
                n,
                values['image'],
                command=values.get('command'),
                links=values.get('links'),
                volumes=values.get('volumes'),
                publish_ports=values.get('ports'),
                expose_ports=values.get('expose'),
                environment=values.get('environment'),
                start_delay=values.get('start_delay', 0))

        if count == 1:
            yield get_instance(name)
        else:
            for idx in xrange(1, count+1):
                # TODO: configurable name/index format
                yield get_instance('%s_%d' % (name, idx))

    def __init__(self, name, image, command=None, links=None, volumes=None,
                 publish_ports=None, expose_ports=None, environment=None, start_delay=0):
        self.name = name
        self.image = image
        self.command = command
        self.links = _dictify(links, 'links')
        self.volumes = _dictify(volumes, 'volumes', lambda x: os.path.abspath(_populate_env(x)))
        self.publish_ports = _dictify(publish_ports, 'ports')

        # check start_delay format
        if not isinstance(start_delay, (int, long)):
            raise BlockadeConfigError("'start_delay' has to be an integer")

        self.start_delay = max(start_delay, 0)

        # all published ports must also be exposed
        self.expose_ports = list(set(
            int(port) for port in
            (expose_ports or []) + list(self.publish_ports.values())
        ))
        self.environment = _dictify(environment, _populate_env, _populate_env)


_DEFAULT_NETWORK_CONFIG = {
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

    def __init__(self, containers, network=None):
        self.containers = containers
        self.sorted_containers = dependency_sorted(containers)
        self.network = network or {}


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
