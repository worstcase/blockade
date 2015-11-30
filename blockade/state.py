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

import uuid
import os
import errno
from copy import deepcopy

import yaml

from .errors import AlreadyInitializedError, NotInitializedError, \
    InconsistentStateError

BLOCKADE_STATE_DIR = ".blockade"
BLOCKADE_STATE_FILE = ".blockade/state.yml"
BLOCKADE_ID_PREFIX = "blockade-"
BLOCKADE_STATE_VERSION = 1


def _assure_dir():
    try:
        os.mkdir(BLOCKADE_STATE_DIR)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def _state_delete():
    try:
        os.remove(BLOCKADE_STATE_FILE)
    except OSError as e:
        if e.errno not in (errno.EPERM, errno.ENOENT):
            raise

    try:
        os.rmdir(BLOCKADE_STATE_DIR)
    except OSError as e:
        if e.errno not in (errno.ENOTEMPTY, errno.ENOENT):
            raise


def _base_state(blockade_id, containers):
    return dict(blockade_id=blockade_id, containers=containers,
                version=BLOCKADE_STATE_VERSION)


class BlockadeState(object):
    def __init__(self, blockade_id, containers):
        self._blockade_id = blockade_id
        self._containers = containers

    @property
    def blockade_id(self):
        return self._blockade_id

    @property
    def containers(self):
        return deepcopy(self._containers)

    def container_id(self, name):
        container = self._containers.get(name, None)
        if not container is None:
            return container.get('id', None)
        return None


class BlockadeStateFactory(object):
    # annoyed with how this ended up structured, and that I called it
    # a factory, but fuckit..

    @staticmethod
    def get_blockade_id():
        return BLOCKADE_ID_PREFIX + uuid.uuid4().hex[:10]

    @staticmethod
    def __write(blockade_id, containers, initialize=True):
        f = None
        path = BLOCKADE_STATE_FILE
        _assure_dir()
        try:
            flags = os.O_WRONLY | os.O_CREAT
            if initialize:
                flags |= os.O_EXCL
            with os.fdopen(os.open(path, flags), "w") as f:
                yaml.safe_dump(_base_state(blockade_id, containers), f)
        except OSError as e:
            if e.errno == errno.EEXIST:
                raise AlreadyInitializedError(
                    "Path %s exists. "
                    "You may need to destroy a previous blockade." % path)
            raise
        except Exception:
            # clean up our created file
            _state_delete()
            raise

    @staticmethod
    def initialize(containers, blockade_id=None):
        if blockade_id is None:
            blockade_id = BlockadeStateFactory.get_blockade_id()
        containers = deepcopy(containers)

        BlockadeStateFactory.__write(blockade_id, containers, initialize=True)

        return BlockadeState(blockade_id, containers)

    @staticmethod
    def update(blockade_id, containers):
        BlockadeStateFactory.__write(blockade_id, deepcopy(containers), initialize=False)

    @staticmethod
    def load():
        try:
            with open(BLOCKADE_STATE_FILE) as f:
                state = yaml.safe_load(f)
                return BlockadeState(state['blockade_id'], state['containers'])

        except (IOError, OSError) as e:
            if e.errno == errno.ENOENT:
                raise NotInitializedError("No blockade exists in this context")
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(e))

        except Exception as e:
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(e))

    @staticmethod
    def destroy():
        _state_delete()
