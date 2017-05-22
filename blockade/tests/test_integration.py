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
import os
import sys
import tempfile
import shutil
import traceback
import json
import time
from io import StringIO
from textwrap import dedent

import docker
import six
import mock
from clint.textui.colored import ColoredString

from blockade.tests import unittest
import blockade.cli
from .util import wait
from .helpers import HostExecHelper


INT_ENV = "BLOCKADE_INTEGRATION_TESTS"
INT_SKIP = (not os.getenv(INT_ENV), "export %s=1 to run" % INT_ENV)


class FakeExit(Exception):
    def __init__(self, rc):
        self.rc = rc
        self.stdout = None
        self.stderr = None

    def __str__(self):
        return "FakeExit rc=%s\nstdout:\n%s\n\nstderr:%s" % (self.rc,
            self.stdout, self.stderr)


def example_config_path(filename):
    example_dir = os.path.join(os.path.dirname(__file__), "../..", "examples")
    example_dir = os.path.abspath(example_dir)
    if not os.path.exists(example_dir):
        raise Exception("example config directory not found: %s" % example_dir)

    config_path = os.path.join(example_dir, filename)
    if not os.path.exists(config_path):
        raise Exception("example config not found: %s" % config_path)
    return config_path


def coerce_output(s):
    if isinstance(s, ColoredString):
        return six.u(str(s))
    elif isinstance(s, six.binary_type):
        return six.u(s)
    else:
        return s


class IntegrationTests(unittest.TestCase):
    """Integration tests that run the full CLI args down.

    Tests that are Linux and Docker only should be decorated with:
        @unittest.skipIf(*INT_SKIP)

    They will only be run when BLOCKADE_INTEGRATION_TESTS=1 env is set.
    """

    sysexit_patch = None
    stderr_patch = None
    tempdir = None
    oldcwd = None

    def setUp(self):
        self.sysexit_patch = mock.patch("sys.exit")
        self.mock_sysexit = self.sysexit_patch.start()

        def exit(rc):
            raise FakeExit(rc)

        self.mock_sysexit.side_effect = exit

        self.tempdir = tempfile.mkdtemp()
        self.oldcwd = os.getcwd()
        os.chdir(self.tempdir)

        self.host_exec_helper = HostExecHelper()
        self.host_exec_helper.setup_prefix_env()

    def tearDown(self):
        if self.sysexit_patch:
            self.sysexit_patch.stop()

        if self.oldcwd:
            os.chdir(self.oldcwd)
        if self.tempdir:
            try:
                shutil.rmtree(self.tempdir)
            except Exception:
                pass

        self.host_exec_helper.tearDown()

    def call_blockade(self, *args):
        stdout = StringIO()
        stderr = StringIO()
        with mock.patch("blockade.cli.puts") as mock_puts:
            mock_puts.side_effect = lambda s: stdout.write(coerce_output(s))

            with mock.patch("blockade.cli.puts_err") as mock_puts_err:
                mock_puts_err.side_effect = lambda s: stderr.write(
                    coerce_output(s))

                try:
                    blockade.cli.main(args)
                except FakeExit as e:
                    if e.rc != 0:
                        e.stderr = stderr.getvalue()
                        e.stdout = stdout.getvalue()
                        raise
                return (stdout.getvalue(), stderr.getvalue())

    def test_badargs(self):
        with mock.patch("sys.stderr"):
            with self.assertRaises(FakeExit) as cm:
                self.call_blockade("--notarealarg")

            self.assertEqual(cm.exception.rc, 2)

    def test_version(self):
        stdout, _ = self.call_blockade("version")
        self.assertIn(blockade.__version__, stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_containers(self):
        config_path = example_config_path("sleep/blockade.yaml")

        # TODO make this better. so far we just walk through all
        # the major operations, but don't really assert anything
        # other than exit code.
        try:
            self.call_blockade("-c", config_path, "up")

            self.call_blockade("-c", config_path, "status")
            stdout, _ = self.call_blockade("-c", config_path, "status",
                                           "--json")
            parsed = json.loads(stdout)
            self.assertEqual(len(parsed), 3)

            self.call_blockade("-c", config_path, "flaky", "c1")
            self.call_blockade("-c", config_path, "slow", "c2", "c3")
            self.call_blockade("-c", config_path, "duplicate", "c2", "c3")
            self.call_blockade("-c", config_path, "fast", "c3")

            # make sure it is harmless for call fast when nothing is slow
            self.call_blockade("-c", config_path, "fast", "--all")

            with self.assertRaises(FakeExit):
                self.call_blockade("-c", config_path, "slow", "notarealnode")

            self.call_blockade("-c", config_path, "partition", "c1,c2", "c3")
            self.call_blockade("-c", config_path, "join")

            stdout, _ = self.call_blockade("-c", config_path, "logs", "c1")
            self.assertEquals("I am c1", stdout.strip())

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_events(self):
        config_path = example_config_path("sleep/blockade.yaml")

        try:
            self.call_blockade("-c", config_path, "up")
            self.call_blockade("-c", config_path, "flaky", "c1")
            self.call_blockade("-c", config_path, "slow", "c2", "c3")

            expected_events = ["flaky", "slow"]

            # call events in all 3 ways
            stdout, _ = self.call_blockade("-c", config_path, "events")
            self.assertTrue(stdout.strip())  # just ensure there IS output

            stdout, _ = self.call_blockade("-c", config_path, "events",
                                           "--json")
            parsed = json.loads(stdout)
            events = [e["event"] for e in parsed["events"]]
            self.assertEquals(expected_events, events)

            stdout, _ = self.call_blockade("-c", config_path, "events",
                                           "--json", "--output", "output.json")
            self.assertEquals(0, len(stdout.strip()))
            with open("output.json") as f:
                parsed = json.load(f)
            events = [e["event"] for e in parsed["events"]]
            self.assertEquals(expected_events, events)

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_containers_name_check(self):

        try:
            config_path = "./blockade.yaml"
            with open(config_path, "w") as f:
                f.write(dedent('''\
                    containers:
                      zzz:
                        image: krallin/ubuntu-tini:trusty
                        command: ["sleep", "infinity"]
                        expose: [10000]
                      aaa:
                        image: krallin/ubuntu-tini:trusty
                        command: ["sleep", "infinity"]
                        links: ["zzz"]
                    '''))

            self.call_blockade("-c", config_path, "up")

            stdout, _ = self.call_blockade("-c", config_path, "status", "--json")
            parsed = json.loads(stdout)
            # Make sure the container name of zzz is not the pseudo-name created
            # by the link (returned as /blockade-86c6c42ff9-aaa/zzz from the
            # Docker API, reduced to aaa/zzz by blockade. Container names are
            # (as of 1.7) returned alphabetically, hence the names aaa and zzz.
            cnames = sorted([c["name"] for c in parsed])
            self.assertEqual(cnames, ["aaa", "zzz"])

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_containers_dns_discovery(self):

        try:
            config_path = "./blockade.yaml"
            with open(config_path, "w") as f:
                f.write(dedent('''\
                    containers:
                      zzz:
                        container_name: zzz
                        image: krallin/ubuntu-tini:trusty
                        command: ["sh", "-c", "sleep 3 && ping -i1 -c3 aaa && sleep infinity"]
                      aaa:
                        container_name: aaa
                        image: krallin/ubuntu-tini:trusty
                        command: ["sh", "-c", "sleep 3 && ping -i1 -c3 zzz && sleep infinity"]
                    network:
                      driver: udn
                    '''))

            self.call_blockade("-c", config_path, "up")

            # If container exited after this sleep, it probably means that
            # ping wasn't able to resolve neighbour host
            time.sleep(6)

            stdout, _ = self.call_blockade("-c", config_path, "status", "--json")
            parsed = json.loads(stdout)
            statuses = [c["status"] for c in parsed]
            self.assertEqual(statuses, ["UP", "UP"])

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_ping_link_ordering(self):
        config_path = example_config_path("ping/blockade.yaml")

        try:
            self.call_blockade("-c", config_path, "up")

            self.call_blockade("-c", config_path, "status")
            stdout, _ = self.call_blockade("-c", config_path, "status",
                                           "--json")
            parsed = json.loads(stdout)
            self.assertEqual(len(parsed), 3)

            # we just want to make sure everything came up ok -- that
            # containers were started in the right order.
            for container in parsed:
                self.assertEqual(container['status'], "UP")

            # could actually try to parse out the logs here and assert that
            # network filters are working.

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_duplicate(self):
        config_path = example_config_path("ping/blockade.yaml")

        try:
            self.call_blockade("-c", config_path, "up")

            self.call_blockade("-c", config_path, "status")
            stdout, _ = self.call_blockade("-c", config_path, "status",
                                           "--json")
            parsed = json.loads(stdout)
            self.assertEqual(len(parsed), 3)

            self.call_blockade("-c", config_path, "duplicate", "c2")

            def predicate():
                stdout, _ = self.call_blockade("-c", config_path, "logs", "c2")
                return "DUP!" in stdout

            # wait for a duplicate packet to show up in the ping output
            wait(predicate, wait=1, timeout=60)

        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_veth_update(self):
        config_path = example_config_path("sleep/blockade.yaml")

        try:
            self.call_blockade("-c", config_path, "up")

            self.call_blockade("-c", config_path, "stop", "c1", "c2")
            self.call_blockade("-c", config_path, "start", "c1", "c2")
            self.call_blockade("-c", config_path, "slow", "c1", "c2")
        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)

    @unittest.skipIf(*INT_SKIP)
    def test_restart_container_with_docker_then_action(self):
        config_path = example_config_path("sleep/blockade.yaml")

        try:
            self.call_blockade("-c", config_path, "up")

            stdout, _ = self.call_blockade("-c", config_path, "status",
                                           "--json")
            parsed = json.loads(stdout)
            # find the c1 container ID
            kill_id = None
            for c in parsed:
                if c['name'] == "c1":
                    kill_id = c['container_id']
            if kill_id is None:
                raise Exception("A container name c1 was not found")
            docker_client = docker.APIClient(
                **docker.utils.kwargs_from_env(assert_hostname=False))

            docker_client.stop(kill_id)
            docker_client.start(kill_id)

            self.call_blockade("-c", config_path, "slow", "c1")
        finally:
            try:
                self.call_blockade("-c", config_path, "destroy")
            except Exception:
                print("Failed to destroy Blockade!")
                traceback.print_exc(file=sys.stdout)
