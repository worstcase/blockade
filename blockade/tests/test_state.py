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
import shutil
import tempfile

from blockade.tests import unittest
from blockade.state import BlockadeStateFactory
from blockade.errors import NotInitializedError


class BlockadeStateTests(unittest.TestCase):
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

    def test_state_initialize(self):

        containers = {"n1": {"a": 1}, "n2": {"a": 4}}
        state = BlockadeStateFactory.initialize(containers=containers)

        self.assertTrue(os.path.exists(".blockade/state.yml"))

        self.assertEqual(state.containers, containers)
        self.assertIsNot(state.containers, containers)
        self.assertIsNot(state.containers["n2"], containers["n2"])

        self.assertRegexpMatches(state.blockade_id, "^[a-z0-9]+$")

        state2 = BlockadeStateFactory.load()
        self.assertEqual(state2.containers, state.containers)
        self.assertIsNot(state2.containers, state.containers)
        self.assertIsNot(state2.containers["n2"], state.containers["n2"])
        self.assertEqual(state2.blockade_id, state.blockade_id)

        BlockadeStateFactory.destroy()
        self.assertFalse(os.path.exists(".blockade/state.yml"))
        self.assertFalse(os.path.exists(".blockade"))

    def test_state_uninitialized(self):
        with self.assertRaises(NotInitializedError):
            BlockadeStateFactory.load()


class BlockadeIdTests(unittest.TestCase):
    def test_blockade_id(self):
        get_blockade_id = BlockadeStateFactory.get_blockade_id
        self.assertEqual(get_blockade_id(cwd="/abs/path/1234"), "1234")
        self.assertEqual(get_blockade_id(cwd="rel/path/abc"), "abc")

        # invalid names should be replaced with "default"
        self.assertEqual(get_blockade_id(cwd="/"), "default")
        self.assertEqual(get_blockade_id(cwd="rel/path/$$("), "default")
