.. _guide:

==============
Blockade Guide
==============

This guide walks you through a simple example that highlights the power of
Blockade. We will start a fake "application" consisting of three Docker
containers. The first runs a simple ``sleep`` command. The other two
containers ping the first. With this simple structure, we can easily see
what happens when we introduce partitions and network failures between
the containers.

Check your Blockade install
---------------------------

To check your install, run the following commands:

.. code-block:: bash

    # check docker
    $ docker info

    # check blockade
    $ blockade -h

If you get an error from either command, you'll need to fix this before
proceeding. See the `Docker installation docs`_ and :ref:`install`.

Set up your Blockade config
---------------------------

Now create a new directory and in it create a ``blockade.yaml`` file with
these contents:

.. code-block:: yaml

    containers:
      c1:
        image: ubuntu:trusty
        command: /bin/sleep 300000
        ports: [10000]

      c2:
        image: ubuntu:trusty
        command: sh -c "ping $C1_PORT_10000_TCP_ADDR"
        links: ["c1"]

      c3:
        image: ubuntu:trusty
        command: sh -c "ping $C1_PORT_10000_TCP_ADDR"
        links: ["c1"]


This configuration specifies the three containers we described above. Note
that we rely on Docker `named links`_ which require at least one open port.
Hence our sleeping ``c1`` container has a fake port 10000 open.
The ``ubuntu:trusty`` image must exist in your Docker installation.
You can download it using the docker pull command ``sudo docker pull ubuntu:trusty``.

Start the Blockade
------------------

Now use the ``blockade up`` command to stand up our containers:

.. code-block:: bash

    $ blockade up

    NODE            CONTAINER ID    STATUS  IP              NETWORK    PARTITION
    c1              b9794aaeed42    UP      172.17.0.2      NORMAL
    c2              875885f54593    UP      172.17.0.4      NORMAL
    c3              9b7227b42466    UP      172.17.0.3      NORMAL

You should see output like above. Note that you get the local IP address
and Docker container ID for each container.

Now let's take a look at the output of ``c2``, which is pinging ``c1``. We'll use
the ``blockade logs`` command, but pipe it through tail so we just get the last
several lines:

.. code-block:: bash

    $ blockade logs c2 | tail
    64 bytes from 172.17.0.2: icmp_req=59 ttl=64 time=0.067 ms
    64 bytes from 172.17.0.2: icmp_req=60 ttl=64 time=0.077 ms
    64 bytes from 172.17.0.2: icmp_req=61 ttl=64 time=0.077 ms
    64 bytes from 172.17.0.2: icmp_req=62 ttl=64 time=0.073 ms
    64 bytes from 172.17.0.2: icmp_req=63 ttl=64 time=0.076 ms
    64 bytes from 172.17.0.2: icmp_req=64 ttl=64 time=0.070 ms
    64 bytes from 172.17.0.2: icmp_req=65 ttl=64 time=0.078 ms
    64 bytes from 172.17.0.2: icmp_req=66 ttl=64 time=0.073 ms
    64 bytes from 172.17.0.2: icmp_req=67 ttl=64 time=0.109 ms

The ``blockade logs`` command is the same as the ``docker logs`` command, it
grabs any stderr and or stdout output from the container.


Mess with the network
---------------------

Now let's try a couple network filters. We'll make the network to ``c2`` be
slow and the network to ``c3`` be flaky.

.. code-block:: bash

    $ blockade slow c2

    $ blockade flaky c3

    $ blockade status
    NODE            CONTAINER ID    STATUS  IP              NETWORK    PARTITION
    c1              b9794aaeed42    UP      172.17.0.2      NORMAL
    c2              875885f54593    UP      172.17.0.4      SLOW
    c3              9b7227b42466    UP      172.17.0.3      FLAKY


Now look at the logs for ``c2`` and ``c3`` again:

.. code-block:: bash

    $ blockade logs c2 | tail
    64 bytes from 172.17.0.2: icmp_req=358 ttl=64 time=126 ms
    64 bytes from 172.17.0.2: icmp_req=359 ttl=64 time=0.077 ms
    64 bytes from 172.17.0.2: icmp_req=360 ttl=64 time=64.5 ms
    64 bytes from 172.17.0.2: icmp_req=361 ttl=64 time=265 ms
    64 bytes from 172.17.0.2: icmp_req=362 ttl=64 time=158 ms
    64 bytes from 172.17.0.2: icmp_req=363 ttl=64 time=64.8 ms
    64 bytes from 172.17.0.2: icmp_req=364 ttl=64 time=3.47 ms
    64 bytes from 172.17.0.2: icmp_req=365 ttl=64 time=90.2 ms
    64 bytes from 172.17.0.2: icmp_req=366 ttl=64 time=0.067 ms

    $ blockade logs c3 | tail
    64 bytes from 172.17.0.2: icmp_req=415 ttl=64 time=0.075 ms
    64 bytes from 172.17.0.2: icmp_req=416 ttl=64 time=0.079 ms
    64 bytes from 172.17.0.2: icmp_req=419 ttl=64 time=0.063 ms
    64 bytes from 172.17.0.2: icmp_req=420 ttl=64 time=0.065 ms
    64 bytes from 172.17.0.2: icmp_req=421 ttl=64 time=0.063 ms
    64 bytes from 172.17.0.2: icmp_req=425 ttl=64 time=0.062 ms
    64 bytes from 172.17.0.2: icmp_req=426 ttl=64 time=0.079 ms
    64 bytes from 172.17.0.2: icmp_req=427 ttl=64 time=0.056 ms
    64 bytes from 172.17.0.2: icmp_req=428 ttl=64 time=0.066 ms


Note how the time value of the ``c2`` pings is erratic, while
``c3``  is missing many packets (look at the ``icmp_req`` value --
it should be sequential).

Now let's use ``blockade fast`` to fix the network:

.. code-block:: bash

    $ blockade fast --all

    $ blockade status
    NODE            CONTAINER ID    STATUS  IP              NETWORK    PARTITION
    c1              6367a903f093    UP      172.17.0.2      NORMAL
    c2              35efaf92bba0    UP      172.17.0.4      NORMAL
    c3              e8ed611a38de    UP      172.17.0.3      NORMAL


Partition the network
---------------------

Blockade can also create partitions between containers. This is valuable for
testing split-brain behaviors. To demonstrate, let's partition node ``c2`` off
from the other two containers. It will no longer be able to ping ``c1``, but
``c3`` will continue unhindered.

Partitions are specified as groups of comma-separated container names:

.. code-block:: bash

    $ blockade partition c1,c3 c2

    $ blockade status
    NODE            CONTAINER ID    STATUS  IP              NETWORK    PARTITION
    c1              6367a903f093    UP      172.17.0.2      NORMAL     1
    c2              35efaf92bba0    UP      172.17.0.4      NORMAL     2
    c3              e8ed611a38de    UP      172.17.0.3      NORMAL     1

Note the partition column: ``c1`` and ``c3`` are in partition #1 while ``c2``
is in partition #2.

You can now use ``blockade logs`` to check the output of ``c2`` and ``c3`` and
see the partition in effect.

Restore the network with the ``join`` command:

.. code-block:: bash

    $ blockade join
    $ blockade status
    NODE            CONTAINER ID    STATUS  IP              NETWORK    PARTITION
    c1              6367a903f093    UP      172.17.0.2      NORMAL
    c2              35efaf92bba0    UP      172.17.0.4      NORMAL
    c3              e8ed611a38de    UP      172.17.0.3      NORMAL


Tear down the Blockade
----------------------

Once finished, kill the containers and restore the network with the
``destroy`` command:

.. code-block:: bash

    $ blockade destroy


Next steps
----------

Next, check out the reference details in :ref:`config` and :ref:`commands`.

.. _Docker installation docs: https://docs.docker.com/engine/installation/
.. _named links: https://docs.docker.com/engine/userguide/networking/default_network/dockerlinks/
