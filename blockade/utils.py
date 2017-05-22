#
#  Copyright (C) 2016 Dell, Inc.
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

from .errors import BlockadeError

import docker


# NOTE the values from the client are "byte strings".
# We need to make sure we properly decode them in Python3.

def docker_run(command,
               image='ubuntu:trusty',
               network_mode='host',
               privileged=True,
               docker_client=None):

    default_client = docker.APIClient(
        **docker.utils.kwargs_from_env(assert_hostname=False)
    )
    docker_client = docker_client or default_client

    host_config = docker_client.create_host_config(
            network_mode=network_mode, privileged=privileged)

    try:
        container = docker_client.create_container(
                image=image, command=command, host_config=host_config)
    except docker.errors.NotFound:
        docker_client.pull(image)
        container = docker_client.create_container(
                image=image, command=command, host_config=host_config)

    docker_client.start(container=container.get('Id'))

    stdout = docker_client.logs(container=container.get('Id'),
                                stdout=True, stream=True)
    output = b''
    for item in stdout:
        output += item

    output = output.decode('utf-8')

    status_code = docker_client.wait(container=container.get('Id'))
    if status_code == 2 and 'No such file or directory' in output:
        docker_client.remove_container(container=container.get('Id'),
                                       force=True)
        return
    elif status_code != 0:
        err_msg = "Problem running Blockade command '%s'"
        raise BlockadeError(err_msg % command)

    docker_client.remove_container(container=container.get('Id'), force=True)

    return output


def check_docker():
    client = docker.APIClient(
        **docker.utils.kwargs_from_env(assert_hostname=False)
    )
    try:
        client.ping()
    except Exception as e:
        raise BlockadeError(("Unable to connect to Docker: %s\n\n" +
            "Blockade requires access to a Docker API.\nEnsure that Docker " +
            "is running and your user has the correct privileges to access " +
            "it.\nOr set the DOCKER_HOST env to point to an external Docker.")
        % (str(e),))
