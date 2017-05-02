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

from copy import deepcopy

import errno
import os
import re
import yaml

from .errors import AlreadyInitializedError
from .errors import BlockadeError
from .errors import InconsistentStateError
from .errors import InvalidBlockadeName
from .errors import NotInitializedError


class BlockadeState(object):
    '''Blockade state related functionality'''

    def __init__(self,
                 blockade_id=None,
                 data_dir=None,
                 state_file=None,
                 state_version=1):

        if blockade_id:
            if re.match(r"^[a-zA-Z0-9-.]+$", blockade_id) is None:
                raise InvalidBlockadeName("'%s' is an invalid blockade ID. "
                                          "You may use only [a-zA-Z0-9-.]")

        # If no data_dir specificed put state file in:
        #   CWD/.blockade/
        # If data_dir specified put state file in:
        #   data_dir/.blockade/
        # If data_dir and blockade_id specified put state file in:
        #   data_dir/.blockade/blockade_id/
        if data_dir:
            self._data_dir = data_dir
            self._state_dir = os.path.join(data_dir, ".blockade")
        else:
            self._data_dir = None
            self._state_dir = os.path.join(os.getcwd(), ".blockade")

        if data_dir and blockade_id:
            self._state_dir = os.path.join(self._state_dir, blockade_id)

        self._state_dir = os.path.abspath(self._state_dir)

        state_file = state_file or "state.yml"
        self._state_file = os.path.join(self._state_dir, state_file)

        self._blockade_id = blockade_id or self._get_blockade_id_from_cwd()
        self._state_version = state_version
        self._containers = {}

    @property
    def blockade_id(self):
        return self._blockade_id

    @property
    def blockade_net_name(self):
        '''Generate blockade nework name based on the blockade_id'''
        return "%s_net" % self._blockade_id

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

    def initialize(self, containers):
        '''
        Initialize a new state file with the given contents.
        This function fails in case the state file already exists.
        '''
        self._containers = deepcopy(containers)
        self.__write(containers, initialize=True)

    def exists(self):
        '''Checks whether a blockade state file already exists'''
        return os.path.isfile(self._state_file)

    def update(self, containers):
        '''Update the current state file with the specified contents'''
        self._containers = deepcopy(containers)
        self.__write(containers, initialize=False)

    def load(self):
        '''Try to load a blockade state file in the current directory'''
        try:
            with open(self._state_file) as f:
                state = yaml.safe_load(f)
                self._containers = state['containers']
        except (IOError, OSError) as err:
            if err.errno == errno.ENOENT:
                raise NotInitializedError("No blockade exists in this context")
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(err))
        except Exception as err:
            raise InconsistentStateError("Failed to load Blockade state: "
                                         + str(err))

    def destroy(self):
        '''Try to remove the current state file and directory'''
        self._state_delete()

    def _get_blockade_id_from_cwd(self, cwd=None):
        '''Generate a new blockade ID based on the CWD'''
        if not cwd:
            cwd = os.getcwd()
        # this follows a similar pattern as docker-compose uses
        parent_dir = os.path.abspath(cwd)
        basename = os.path.basename(parent_dir).lower()
        blockade_id = re.sub(r"[^a-z0-9]", "", basename)
        if not blockade_id:  # if we can't get a valid name from CWD, use "default"
            blockade_id = "default"
        return blockade_id

    def _assure_dir(self):
        '''Make sure the state directory exists'''
        try:
            os.makedirs(self._state_dir)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

    def _state_delete(self):
        '''Try to delete the state.yml file and the folder .blockade'''
        try:
            os.remove(self._state_file)
        except OSError as err:
            if err.errno not in (errno.EPERM, errno.ENOENT):
                raise

        try:
            os.rmdir(self._state_dir)
        except OSError as err:
            if err.errno not in (errno.ENOTEMPTY, errno.ENOENT):
                raise

    def __base_state(self, containers):
        '''
        Convert blockade ID and container information into
        a state dictionary object.
        '''
        return dict(blockade_id=self._blockade_id,
                    containers=containers,
                    version=self._state_version)

    def __write(self, containers, initialize=True):
        '''Write the given state information into a file'''
        path = self._state_file
        self._assure_dir()
        try:
            flags = os.O_WRONLY | os.O_CREAT
            if initialize:
                flags |= os.O_EXCL
            with os.fdopen(os.open(path, flags), "w") as f:
                yaml.safe_dump(self.__base_state(containers), f)
        except OSError as err:
            if err.errno == errno.EEXIST:
                raise AlreadyInitializedError(
                    "Path %s exists. "
                    "You may need to destroy a previous blockade." % path)
            raise
        except Exception:
            # clean up our created file
            self._state_delete()
            raise

    def get_audit_file(self):
        audit_dir = os.path.join(self._state_dir, "audit")
        try:
            os.makedirs(audit_dir, 0o755)
        except OSError as os_e:
            if os_e.errno != errno.EEXIST:
                raise
        return os.path.join(audit_dir, "%s.json" % self._blockade_id)
