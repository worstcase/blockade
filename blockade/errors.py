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


class BlockadeError(Exception):
    """Expected error within Blockade
    """


class BlockadeConfigError(BlockadeError):
    """Error in configuration
    """


class BlockadeContainerConflictError(BlockadeError):
    """Error on conflicting containers
    """


class AlreadyInitializedError(BlockadeError):
    """Blockade already created in this context
    """


class NotInitializedError(BlockadeError):
    """Blockade not created in this context
    """


class InconsistentStateError(BlockadeError):
    """Blockade state is inconsistent (partially created or destroyed)
    """


class InsufficientPermissionsError(BlockadeError):
    """Blockade is executed with insufficient permissions
    """


class InvalidBlockadeName(BlockadeError):
    """Invalid blockade name
    """

class DockerContainerNotFound(BlockadeError):
    """Docker container not found
    """
