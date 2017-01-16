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


class BlockadeUsageError(BlockadeError):
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


class HostExecError(BlockadeError):
    """Error in host command
    """

    def __init__(self, message, output=None, exit_code=None):
        super(HostExecError, self).__init__(message)
        self.output = output
        self.exit_code = exit_code

    def __str__(self):
        message = super(HostExecError, self).__str__()
        if self.exit_code is not None and self.output is not None:
            return "%s rc=%s output=%s" % (message, self.exit_code, self.output)
        if self.output is not None:
            return "%s output=%s" % (message, self.output)
        return message


class BlockadeStateTransitionError(BlockadeError):
    """The state machine was given an invalid event.  Based on the state that
     it is in and the event received the state machine could not process the
     event"""
    def __init__(self, current_state, event, msg=None):
        super(BlockadeStateTransitionError, self).__init__(msg)
        self.state = current_state
        self.event = event

    def __str__(self):
        return "Error processing the event %s when in the %s state" % (
            self.event, self.state)


class BlockadeHttpError(BlockadeError):
    """Errors from the REST API
    """
    def __init__(self, http_code, http_msg, msg=None):
        super(BlockadeStateTransitionError, self).__init__(msg)
        self.http_code = http_code
        self.http_msg = http_msg
