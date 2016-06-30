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

import docker
import six
import time


# NOTE the values from the client are "byte strings".
# We need to make sure we properly decode them in Python3.

def docker_run(command,
               image='ubuntu:trusty',
               network_mode='host',
               privileged=True):

    docker_client = docker.Client()

    try:
        container = docker_client.create_container(image=image, command=command)
    except docker.errors.NotFound:
        docker_client.pull(image)
        container = docker_client.create_container(image=image, command=command)

    docker_client.start(container=container.get('Id'),
                        network_mode=network_mode,
                        privileged=privileged)

    stdout = docker_client.logs(container=container.get('Id'),
                                stdout=True, stream=True)
    output = b''
    for item in stdout:
        output += item

    docker_client.stop(container=container.get('Id'))
    docker_client.remove_container(container=container.get('Id'), force=True)

    return output.decode('utf-8')
