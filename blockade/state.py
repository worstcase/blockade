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
    '''Make sure the .blockade directory exists'''
    try:
        os.mkdir(BLOCKADE_STATE_DIR)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise


def _state_delete():
    '''Try to delete the state.yml file and the folder .blockade'''
    try:
        os.remove(BLOCKADE_STATE_FILE)
    except OSError as err:
        if err.errno not in (errno.EPERM, errno.ENOENT):
            raise

    try:
        os.rmdir(BLOCKADE_STATE_DIR)
    except OSError as err:
        if err.errno not in (errno.ENOTEMPTY, errno.ENOENT):
            raise


class BlockadeState(object):
    '''
    Blockade state information containing blockade ID
    and the container specifications.
    '''

    def __init__(self, blockade_id, containers):
        self._blockade_id = blockade_id
        self._containers = containers

    @property
    def blockade_id(self):
        '''Blockade ID the state information belong to'''
        return self._blockade_id

    @property
    def containers(self):
        '''Dictionary of container information'''
        return deepcopy(self._containers)

    def container_id(self, name):
        '''Try to find the container ID with the specified name'''
        container = self._containers.get(name, None)
        if not container is None:
            return container.get('id', None)
        return None


class BlockadeStateFactory(object):
    '''Blockade state related functionality'''

    @staticmethod
    def get_blockade_id():
        '''Generate a new random blockade ID'''
        return BLOCKADE_ID_PREFIX + uuid.uuid4().hex[:10]

    @staticmethod
    def initialize(containers, blockade_id=None):
        '''
        Initialize a new state file with the given contents.
        This function fails in case the state file already exists.
        '''
        if blockade_id is None:
            blockade_id = BlockadeStateFactory.get_blockade_id()
        containers = deepcopy(containers)

        BlockadeStateFactory.__write(blockade_id, containers, initialize=True)

        return BlockadeState(blockade_id, containers)

    @staticmethod
    def update(blockade_id, containers):
        '''Update the current state file with the specified contents'''
        BlockadeStateFactory.__write(blockade_id, deepcopy(containers), initialize=False)

    @staticmethod
    def load():
        '''Try to load a blockade state file in the current directory'''
        try:
            with open(BLOCKADE_STATE_FILE) as f:
                state = yaml.safe_load(f)
                return BlockadeState(state['blockade_id'], state['containers'])

        except (IOError, OSError) as err:
            if err.errno == errno.ENOENT:
                raise NotInitializedError("No blockade exists in this context")
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(err))

        except Exception as err:
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(err))
    @staticmethod
    def destroy():
        '''Try to remove the current state file and directory'''
        _state_delete()

    @staticmethod
    def __base_state(blockade_id, containers):
        '''
        Convert blockade ID and container information into
        a state dictionary object.
        '''
        return dict(blockade_id=blockade_id,
                    containers=containers,
                    version=BLOCKADE_STATE_VERSION)

    @staticmethod
    def __write(blockade_id, containers, initialize=True):
        '''Write the given state information into a file'''
        path = BLOCKADE_STATE_FILE
        _assure_dir()
        try:
            flags = os.O_WRONLY | os.O_CREAT
            if initialize:
                flags |= os.O_EXCL
            with os.fdopen(os.open(path, flags), "w") as f:
                yaml.safe_dump(BlockadeStateFactory.__base_state(blockade_id, containers), f)
        except OSError as err:
            if err.errno == errno.EEXIST:
                raise AlreadyInitializedError(
                    "Path %s exists. "
                    "You may need to destroy a previous blockade." % path)
            raise
        except Exception:
            # clean up our created file
            _state_delete()
            raise
