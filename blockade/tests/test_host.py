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

import time
import unittest
import threading
import logging

import docker

from blockade.host import HostExec
from blockade.errors import HostExecError
from blockade.tests.test_integration import INT_SKIP
from blockade.tests.helpers import HostExecHelper


_logger = logging.getLogger(__name__)

_GET_CONTAINER_ID_CMD = ["sh", "-c",
    "cat /proc/self/cgroup | grep docker | grep -o -E '[0-9a-f]{64}' "
    "| head -n 1"]


class HostExecTests(unittest.TestCase):

    def setUp(self):
        self.helper = HostExecHelper()

        self.docker = docker.APIClient(
            **docker.utils.kwargs_from_env(assert_hostname=False))

    def tearDown(self):
        self.helper.tearDown()

    def assert_no_containers(self):
        self.assertEqual(self.helper.find_created_containers(), [])

    def get_host_exec(self, **kwargs):
        return HostExec(container_prefix=self.helper.prefix, **kwargs)

    def test_reuse_container(self):
        """test that containers are reused"""
        # no containers should be running
        self.assert_no_containers()

        # run one process, which should start a container and leave it running

        host_exec = self.get_host_exec()
        container_hostname_1 = host_exec.run(_GET_CONTAINER_ID_CMD).strip()
        self.assertTrue(container_hostname_1)

        containers_1 = self.helper.find_created_containers()
        self.assertEqual(len(containers_1), 1)
        self.assertTrue(containers_1[0].startswith(container_hostname_1))

        # run another process, which should reuse the existing container
        container_hostname_2 = host_exec.run(_GET_CONTAINER_ID_CMD).strip()
        containers_2 = self.helper.find_created_containers()
        self.assertEqual(containers_1, containers_2)
        self.assertEqual(container_hostname_1, container_hostname_2)

        host_exec.close()
        self.assert_no_containers()

        container_hostname_3 = host_exec.run(_GET_CONTAINER_ID_CMD).strip()
        self.assertNotEqual(container_hostname_3, container_hostname_1)
        containers_3 = self.helper.find_created_containers()
        self.assertEqual(len(containers_3), 1)
        self.assertTrue(containers_3[0].startswith(container_hostname_3))

        host_exec.close()

    def test_killed_container(self):
        """test that dead containers are gracefully replaced"""
        host_exec = self.get_host_exec()
        host_exec.run(["hostname"])

        containers_1 = self.helper.find_created_containers()
        self.assertEqual(len(containers_1), 1)
        self.docker.kill(containers_1[0])

        host_exec.run(["hostname"])
        containers_2 = self.helper.find_created_containers()
        self.assertEqual(len(containers_2), 1)
        self.assertNotEqual(containers_1, containers_2)

        host_exec.close()

    def test_removed_container(self):
        """test that missing containers are gracefully replaced"""
        host_exec = self.get_host_exec()
        host_exec.run(["hostname"])

        containers_1 = self.helper.find_created_containers()
        self.assertEqual(len(containers_1), 1)
        self.docker.kill(containers_1[0])
        self.docker.remove_container(containers_1[0])

        host_exec.run(["hostname"])
        containers_2 = self.helper.find_created_containers()
        self.assertEqual(len(containers_2), 1)
        self.assertNotEqual(containers_1, containers_2)

        host_exec.close()

    def test_close_removed_container(self):
        """test that close() handles missing containers gracefully"""
        host_exec = self.get_host_exec()
        host_exec.run(["hostname"])

        containers_1 = self.helper.find_created_containers()
        self.assertEqual(len(containers_1), 1)
        self.docker.kill(containers_1[0])
        self.docker.remove_container(containers_1[0])
        host_exec.close()

    def test_expired_container(self):
        """ test that containers are replaced upon expiration"""
        host_exec = self.get_host_exec()
        host_exec.run(["hostname"])

        containers_1 = self.helper.find_created_containers()
        self.assertEqual(len(containers_1), 1)

        # ensure that expire time was set approximately correctly
        time_left = host_exec._container_expire_time - time.time()
        self.assertTrue(0 < time_left < host_exec._container_expire)

        # forcibly set expire time to ensure that next call triggers
        host_exec._container_expire_time = time.time()

        host_exec.run(["hostname"])
        containers_2 = self.helper.find_created_containers()
        self.assertEqual(len(containers_2), 1)
        self.assertNotEqual(containers_1, containers_2)

        host_exec.close()

    def test_command_error(self):
        """test that commands with nonzero exit codes result in exceptions
        """
        host_exec = self.get_host_exec()
        with self.assertRaises(HostExecError) as cm:
            host_exec.run(["false"])
        _logger.debug(cm.exception)
        host_exec.close()

    @unittest.skipIf(*INT_SKIP)
    def test_parallel_run(self):
        """test that many commands can be run in parallel"""

        host_exec = self.get_host_exec()
        event = threading.Event()

        error_lock = threading.Lock()
        errors = []

        def _thread():
            try:
                assert event.wait(60)
                for _ in range(10):
                    host_exec.run(["hostname"])

            except Exception as e:
                with error_lock:
                    errors.append(e)

        threads = [threading.Thread(target=_thread) for _ in range(10)]

        for t in threads:
            t.daemon = True
            t.start()

        event.set()

        for t in threads:
            t.join()

        self.assertEqual(errors, [])

        host_exec.close()
