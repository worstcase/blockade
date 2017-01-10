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
        "containers": ["docker_container_id"]
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


Chaos REST API
==============

Users wishing to start *chaos* on their blockade can use this REST API.  Based
on the parameters given the *chaos* feature will randomly select containers
in the blockade to perform blockade events (duplicate, slow, flaky, or
partition) upon.

``Start chaos on a Blockade``
-----------------------------

Began performing chaos operations on a given blockade.  The user can control
the number of events that can happen at once as well as the number of
containers that can be effected in a given degradation period.  What possible
events can be selected can be controlled as well.  A *degradation* period
will start sometime between *min_start_delay* and *max_start_delay*
milliseconds and it will last for between *min_run_time* and *max_run_time*
milliseconds.

**Example request:**

::

    POST /blockade/<name>/chaos
    Content-Type: application/json

    {
        "min_start_delay": 30000,
        "max_start_delay": 300000,
        "min_run_time": 30000,
        "max_run_time": 300000,
        "min_containers_at_once": 1,
        "max_containers_at_once": 2,
        "min_events_at_once": 1,
        "max_events_at_once": 2,
        "event_set": ["SLOW", "DUPLICATE", "FLAKY", "STOP", "PARTITION"]
    }


**Response:**

::

    201 Successfully started chaos on <name>

``Update chaos parameters on a Blockade``
-----------------------------------------

This operation takes the same options as the create.

**Example request:**

::

    POST /blockade/<name>/chaos
    Content-Type: application/json

    {
        "min_start_delay": 30000,
        "max_start_delay": 300000,
        "min_run_time": 30000,
        "max_run_time": 300000,
        "min_containers_at_once": 1,
        "max_containers_at_once": 2,
        "min_events_at_once": 1,
        "max_events_at_once": 2,
        "event_set": ["SLOW", "DUPLICATE", "FLAKY", "STOP", "PARTITION"]
    }

**Response:**

::

    200 Updated chaos on <name>

``Get the current status of chaos``
-----------------------------------

**Example request:**

::

    GET /blockade/<name>/chaos

**Response:**

::

    {
        "state": "DEGRADED"
    }

``Stop chaos on a give blockade``
---------------------------------

**Example request:**

::

    DELETE /blockade/<name>/chaos

**Response:**

::

    Deleted chaos on <name>

