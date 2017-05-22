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
import logging
import threading
import time
import uuid

import docker

from .errors import HostExecError


_logger = logging.getLogger(__name__)

DEFAULT_IMAGE = 'vimagick/iptables:latest'
DEFAULT_CONTAINER_PREFIX = 'blockade-helper'
CONTAINER_PREFIX_ENV = "BLOCKADE_HOST_CONTAINER_PREFIX"


class HostExec(object):
    """Runs host commands via exec in a long-lived container

    A container is launched on the first attempt to run a command. The
    container runs a sleep command with a configurable timeout - to ensure
    it stops running if orphaned. But to guard against race conditions where
    blockade attempts to use a container just as it is dying, we also have
    a separate expiration threshold, where blockade will automatically discard
    an old container well before it would die.
    """

    def __init__(self, image=DEFAULT_IMAGE, container_timeout=3600,
                 container_expire=3000, container_prefix=None,
                 docker_client=None):
        self._image = image
        self._container_timeout = container_timeout
        self._container_expire = container_expire

        if container_prefix:
            self._container_prefix = container_prefix
        elif os.environ.get(CONTAINER_PREFIX_ENV):
            self._container_prefix = os.environ[CONTAINER_PREFIX_ENV]
        else:
            self._container_prefix = DEFAULT_CONTAINER_PREFIX

        self._docker_client = docker_client or docker.APIClient(
            **docker.utils.kwargs_from_env(assert_hostname=False)
        )
        self._lock = threading.RLock()
        self._reset_container()

    def run(self, command):

        _logger.debug("Running host command '%s'", command)

        def _exec():
            self._assure_container()
            exec_handle = self._docker_client.exec_create(self._container_id,
                command)
            output = self._docker_client.exec_start(exec_handle).decode('utf-8')
            exec_details = self._docker_client.exec_inspect(exec_handle)
            exit_code = exec_details['ExitCode']
            if exit_code != 0:
                raise HostExecError(("Error running host command '%s'" %
                    (command,)), exit_code=exit_code, output=output)

            return output

        try:
            return _exec()

        except docker.errors.NotFound:
            # container was removed out-of-band. replace it and retry
            with self._lock:
                self._reset_container()
            return _exec()

        except (docker.errors.APIError, docker.errors.DockerException):
            # unknown Docker error, most likely a dead container.
            # replace it and retry
            _logger.debug("Docker error running command '%s'", command,
                          exc_info=True)
            with self._lock:
                self._remove_container()
            return _exec()

    def close(self):
        _logger.debug("Closing host exec system")
        with self._lock:
            self._remove_container()

    def _assure_container(self):
        with self._lock:
            if self._container_id is None:
                self._create_container()
            elif self._container_is_expired():
                self._remove_container()
                self._create_container()

    def _container_is_expired(self):
        if not self._container_id:
            return True
        return self._container_expire_time <= time.time()

    def _create_container(self):
        command = "sleep %d" % self._container_timeout
        name = '-'.join((self._container_prefix, uuid.uuid4().hex))

        _logger.debug("creating host container image=%s cmd='%s' name=%s",
            self._image, command, name)

        def _create():
            host_config = self._docker_client.create_host_config(
                network_mode="host", privileged=True)
            return self._docker_client.create_container(
                image=self._image, command=command, name=name,
                host_config=host_config)

        try:
            container = _create()
        except docker.errors.NotFound:
            self._docker_client.pull(self._image)
            container = _create()

        container_id = container.get('Id')
        self._docker_client.start(container=container_id)

        self._container_id = container_id
        self._container_expire_time = time.time() + float(self._container_expire)

    def _remove_container(self):
        if self._container_id:

            _logger.debug("Cleaning up host container %s", self._container_id)

            needs_remove = True
            try:
                self._docker_client.kill(self._container_id)
            except docker.errors.NotFound:
                needs_remove = False
            except (docker.errors.APIError, docker.errors.DockerException):
                _logger.debug("Error attempting to kill host container %s",
                              self._container_id, exc_info=True)

            if needs_remove:
                try:
                    self._docker_client.remove_container(
                        container=self._container_id, force=True)
                except docker.errors.NotFound:
                    pass

        self._reset_container()

    def _reset_container(self):
        self._container_id = None
        self._container_expire_time = 0
