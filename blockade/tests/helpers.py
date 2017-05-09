#
#  Copyright (C) 2017 Quest, Inc.
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

import os
import uuid
import logging

import docker

import blockade.host


_logger = logging.getLogger(__name__)


class HostExecHelper(object):
    def __init__(self):
        self.prefix = "blockade-test-" + uuid.uuid4().hex[:8]
        self.docker = docker.APIClient(
            **docker.utils.kwargs_from_env(assert_hostname=False))

    def setup_prefix_env(self):
        os.environ[blockade.host.CONTAINER_PREFIX_ENV] = self.prefix

    def tearDown(self):
        containers = self.find_created_containers()
        if containers:
            for c in containers:
                try:
                    self.docker.kill(c)
                except docker.errors.APIError:
                    pass  # already dead

                try:
                    self.docker.remove_container(c, force=True)
                except docker.errors.APIError as e:
                    if not "already in progress" in str(e):
                        _logger.exception("Failed to remove container %s", c)

            raise Exception("Test failed to tear down %d created container(s). "
                      "They have been removed." % len(containers))

    def find_created_containers(self):
        containers = self.docker.containers(all=True)

        return [c['Id'] for c in containers
                if any(name.startswith("/"+self.prefix) for name in c['Names'])]
