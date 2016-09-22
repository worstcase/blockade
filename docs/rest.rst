.. _rest:

========
REST API
========

The REST API is provided by the Blockade daemon and exposes most of the
Blockade commands. In particular, it can be helpful for automated test suites,
allowing them to setup, manipulate, and destroy Blockades through the API.

Check the help for Blockade daemon options ``blockade daemon -h``

``Create a Blockade``
---------------------

**Example request:**

::

    POST /blockade/<name>
    Content-Type: application/json

    {
        "containers": {
            "c1": {
                "image": "ubuntu:trusty",
                "hostname": "c1",
                "command": "/bin/sleep 300"
            },
            "c2": {
                "image": "ubuntu:trusty",
                "hostname": "c2",
                "command": "/bin/sleep 300"
            }
        }
    }

**Response:**

::

    204 No content

``Execute an action on a Blockade (start, stop, restart, kill)``
----------------------------------------------------------------

**Example request:**

::

    POST /blockade/<name>/action
    Content-Type: application/json

    {
        "command": "start",
        "container_names": ["c1"]
    }

**Response:**

::

    204 No content

``Change the network state of a Blockade (fast, slow, duplicate, flaky)``
-------------------------------------------------------------------------

**Example request:**

::

    POST /blockade/<name>/network_state
    Content-Type: application/json

    {
        "network_state": "fast",
        "container_names": ["c1"]
    }

**Response:**

::

    204 No content

``Partition the network between containers``
--------------------------------------------

**Example request:**

::

    POST /blockade/<name>/partitions
    Content-Type: application/json

    {
        "partitions": [["c1"], ["c2", "c3"]]
    }

**Response:**

::

    204 No content

``Delete all partitions for a Blockade and restore full connectivity``
----------------------------------------------------------------------

**Example request:**

::

    DELETE /blockade/<name>/partitions

**Response:**

::

    204 No content

``List all Blockades``
----------------------

**Example request:**

::

    GET /blockade

**Response:**

::

    {
        "blockades": [
            "test_blockade1",
            "test_blockade2"
        ]
    }

``Get Blockade``
----------------

**Example request:**

::

    GET /blockade/<name>

**Response:**

::

    {
        "containers": {
            "c1": {
                "container_id": "729a67bc126f597b563410b8b5478929da04ba81c0ce4519c2d7eb48599a4406",
                "device": "veth035b534",
                "ip_address": "172.17.0.7",
                "name": "c1",
                "network_state": "NORMAL",
                "partition": null,
                "status": "UP"
            },
            "c2": {
                "container_id": "ee84117d7b6fd806279ee0e5a2a3737a8d21a1e5129df31d3e0f1dee22d94d35",
                "device": "veth304bac6",
                "ip_address": "172.17.0.6",
                "name": "c2",
                "network_state": "NORMAL",
                "partition": null,
                "status": "UP"
            }
        }
    }

``Add an existing Docker container to a Blockade``
----------------------------------------------------------------

**Example request:**

::

    PUT /blockade/<name>
    Content-Type: application/json

    {
        "container_ids": ["docker_container_id"]
    }

**Response:**

::

    204 No content

``Delete a Blockade``
---------------------

**Example request:**

::

    DELETE /blockade/<name>

**Response:**

::

    204 No content
