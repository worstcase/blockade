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
- Creation of arbitrary partitions between containers
- Giving a container a flaky network connection to others (drop packets)
- Giving a container a slow network connection to others (latency)
- While under partition or network failure control, containers can
  freely communicate with the host system -- so you can still grab logs
  and monitor the application.

Blockade is written and maintained by the `Dell Cloud Manager`_ (formerly
Enstratius) team and is used internally to test the behaviors of our software.
We also release a number of other internal components as open source,
most notably `Dasein Cloud`_.

Blockade is inspired by the excellent `Jepsen`_ article series.

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

Development and Support
=======================

Blockade is `available on github <https://github.com/dcm-oss/blockade>`_.
Bug reports should be reported as
`issues <https://github.com/dcm-oss/blockade/issues>`_ there.

License
=======

Blockade is offered under the Apache License 2.0.


.. toctree::
   :hidden:

.. _Docker: https://www.docker.com
.. _named links: https://docs.docker.com/engine/userguide/networking/default_network/dockerlinks/
.. _Dell Cloud Manager: http://www.enstratius.com
.. _Dasein Cloud: http://dasein.org
.. _Jepsen: http://aphyr.com/tags/jepsen
