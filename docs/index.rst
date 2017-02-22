========
blockade
========

Blockade is a utility for testing network failures and partitions in
distributed applications. Blockade uses `Docker`_ containers to run
application processes and manages the network from the host system to
create various failure scenarios.

A common use is to run a distributed application such as a database
or cluster and create network partitions, then observe the behavior of
the nodes. For example in a leader election system, you could partition
the leader away from the other nodes and ensure that the leader steps
down and that another node emerges as leader.

Blockade features:

- A flexible YAML format to describe the containers in your application
- Support for dependencies between containers, using `named links`_
- A CLI tool for managing and querying the status of your blockade
- When run as a daemon, a simple :ref:`rest` can be used to configure your
  blockade
- Creation of arbitrary partitions between containers
- Giving a container a flaky network connection to others (drop packets)
- Giving a container a slow network connection to others (latency)
- While under partition or network failure control, containers can
  freely communicate with the host system -- so you can still grab logs
  and monitor the application.

Blockade was originally developed by the Dell Cloud Manager
(formerly Enstratius) team. Blockade is inspired by the excellent
`Jepsen`_ article series.

Get started with the :ref:`guide`!

Reference Documentation
=======================

.. toctree::
   :maxdepth: 1

   install
   guide
   config
   commands
   changes
   rest

Development and Support
=======================

Blockade is `available on github <https://github.com/worstcase/blockade>`_.
Bug reports should be reported as
`issues <https://github.com/worstcase/blockade/issues>`_ there.

License
=======

Blockade is offered under the Apache License 2.0.


.. toctree::
   :hidden:

.. _Docker: https://www.docker.com
.. _named links: https://docs.docker.com/engine/userguide/networking/default_network/dockerlinks/
.. _Jepsen: http://aphyr.com/tags/jepsen
