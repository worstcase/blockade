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
import tempfile
import shutil
from textwrap import dedent

from blockade import cli
from blockade.tests import unittest
from blockade.errors import BlockadeError


class CommandLineTests(unittest.TestCase):

    def test_parser(self):
        # just make sure we don't have any typos for now
        cli.setup_parser()


class ConfigFilePathTests(unittest.TestCase):
    tempdir = None
    oldcwd = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.oldcwd = os.getcwd()
        os.chdir(self.tempdir)

    def tearDown(self):
        if self.oldcwd:
            os.chdir(self.oldcwd)
        if self.tempdir:
            try:
                shutil.rmtree(self.tempdir)
            except Exception:
                pass

    def _writeConfig(self, path):
        with open(path, "w") as f:
            f.write(dedent('''\
                containers:
                  zzz:
                    image: ubuntu:trusty
                    command: sleep infinity
            '''))

    def test_yml(self):
        """load config from blockade.yml"""
        self._writeConfig("blockade.yml")
        config = cli.load_config()
        self.assertIn("zzz", config.containers)

    def test_yaml(self):
        """load config from blockade.yaml"""
        self._writeConfig("blockade.yaml")
        config = cli.load_config()
        self.assertIn("zzz", config.containers)

    def test_custom(self):
        """load config from custom path"""
        self._writeConfig("custom-file.yaml")
        config = cli.load_config("./custom-file.yaml")
        self.assertIn("zzz", config.containers)

    def test_custom_notfound(self):
        """load config from nonexistent custom path"""
        with self.assertRaisesRegexp(BlockadeError, "^Failed to load config"):
            cli.load_config("./custom-file.yaml")

    def test_noconfig(self):
        """load default config when no file is present"""
        config = cli.load_config()
        self.assertEqual(0, len(config.containers))
