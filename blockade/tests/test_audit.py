#
#  Copyright (c) 2017, Stardog Union. <http://stardog.com>
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
import json
import os
import tempfile
import unittest

from blockade import audit


class AuditTest(unittest.TestCase):

    def test_basic_audit(self):
        fd, tmpfile = tempfile.mkstemp()
        os.close(fd)
        a = audit.EventAuditor(tmpfile)
        a.log_event("SLOW", "success", "message1", ["c1"])
        a.log_event("FLAKY", "success", "message2", ["c1"])

        ctr = 1
        for d in a.read_logs(as_json=True):
            self.assertEqual(d['message'], "message%d" % ctr)
            ctr += 1
        self.assertEqual(ctr, 3)
        ctr = 1
        for l in a.read_logs():
            d = json.loads(l)
            self.assertEqual(d['message'], "message%d" % ctr)
            ctr += 1
        self.assertEqual(ctr, 3)
        a.clean()
        self.assertFalse(os.path.exists(tmpfile))
