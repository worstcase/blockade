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

from .errors import BlockadeConfigError


class BlockadeContainerConfig(object):
    @staticmethod
    def from_dict(name, d):
        return BlockadeContainerConfig(
            name, d['image'],
            command=d.get('command'), links=d.get('links'),
            lxc_conf=d.get('lxc_conf'), volumes=d.get('volumes'),
            ports=d.get('ports'), environment=d.get('environment'))

    def __init__(self, name, image, command=None, links=None, lxc_conf=None,
                 volumes=None, ports=None, environment=None):
        self.name = name
        self.image = image
        self.command = command
        self.links = _dictify(links, "links")
        self.lxc_conf = dict(lxc_conf or {})
        self.volumes = _dictify(volumes, "volumes")
        self.ports = _dictify(ports, "ports")
        self.environment = dict(environment or {})


_DEFAULT_NETWORK_CONFIG = {
    "flaky": "30%",
    "slow": "75ms 100ms distribution normal",
}


class BlockadeConfig(object):
    @staticmethod
    def from_dict(d):
        try:
            containers = d['containers']
            parsed_containers = {}
            for name, container_dict in containers.items():
                try:
                    container = BlockadeContainerConfig.from_dict(
                        name, container_dict)
                    parsed_containers[name] = container

                except Exception as e:
                    raise BlockadeConfigError(
                        "Container '%s' config problem: %s" % (name, e))

            network = d.get('network')
            if network:
                defaults = _DEFAULT_NETWORK_CONFIG.copy()
                defaults.update(network)
                network = defaults

            else:
                network = _DEFAULT_NETWORK_CONFIG.copy()

            return BlockadeConfig(parsed_containers, network=network)

        except KeyError as e:
            raise BlockadeConfigError("Config missing value: " + str(e))

        except Exception as e:
            # TODO log this to some debug stream?
            raise BlockadeConfigError("Failed to load config: " + str(e))

    def __init__(self, containers, network=None):
        self.containers = containers
        self.sorted_containers = dependency_sorted(containers)
        self.network = network or {}


def _dictify(data, name="input"):
    if data:
        if isinstance(data, collections.Sequence):
            return dict((str(v), str(v)) for v in data)
        elif isinstance(data, collections.Mapping):
            return dict((str(k), str(v or k)) for k, v in list(data.items()))
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

    # use ordered dict to preserve original order of nondependent containers
    d = collections.OrderedDict((name, set(c.links.keys()))
                                for name, c in containers.items())
    sorted_names = _resolve(d)
    return [containers[name] for name in sorted_names]


def _resolve(d):
    all_keys = set(d.keys())
    result = []
    resolved_keys = set()

    while d:
        resolved_keys_count = len(resolved_keys)
        for name, links in list(d.items()):
            # containers with no links can be started in any order.
            # containers whose parent containers have already been resolved
            # can be added now too.
            if not links or links <= resolved_keys:
                result.append(name)
                resolved_keys.add(name)
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
        if len(resolved_keys) == resolved_keys_count:
            raise BlockadeConfigError("containers have circular links!")

    return result
