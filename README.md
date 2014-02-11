Blockade
========

Blockade is a utility for testing network failures and partitions in
distributed applications. Blockade uses [Docker](http://www.docker.io)
containers to run application processes and manages the network from
the host system to create various failure scenarios.

A common use is to run a distributed application such as a database
or cluster and create network partitions, then observe the behavior of
the nodes. For example in a leader election system, you could partition
the leader away from the other nodes and ensure that the leader steps
down and that another node emerges as leader.

Check out the [Blockade documentation](http://blockade.readthedocs.org)!

Blockade features:

* A flexible YAML format to describe the containers in your application
* Support for dependencies between containers, using named links
- A CLI tool for managing and querying the status of your blockade
* Creation of arbitrary partitions between containers
* Giving a container a flaky network connection to others (drop packets)
* Giving a container a slow network connection to others (latency)
* While under partition or network failure control, containers can
  freely communicate with the host system -- so you can still grab logs
  and monitor the application.

Blockade is written and maintained by the
[Dell Cloud Manager](http://www.enstratius.com) (formerly Enstratius)
team and is used internally to test the behaviors of our software.
We also release a number of other internal components as open source,
most notably [Dasein Cloud](http://dasein.org).

Inspired by the excellent [Jepsen](http://aphyr.com/tags/jepsen) series.


Configuration
-------------

Blockade expects a ``blockade.yaml`` file in the current directory which
describes the containers to launch, how they are linked, and various
parameters for the blockade modes. Example:


```yaml

containers:
  c1:
    image: my_docker_image
    command: /bin/myapp
    volumes: {"/opt/myapp": "/opt/myapp_host"}
    ports: [80]
    environment: {"IS_MASTER": 1}

  c2:
    image: my_docker_image
    command: /bin/myapp
    volumes: ["/data"]
    links: {c1: master}

  c3:
    image: my_docker_image
    command: /bin/myapp
    links: {c1: master}

network:
  flaky: 30%
  slow: 75ms 100ms distribution normal
```

Blockade stores transient information in a local ``.blockade/`` directory.
This directory will be cleaned up automatically when you run the
``blockade destroy`` command.


Usage
-----

Blockade may be used from the command line manually. The commands are also
intended to be easy to wrap and automate within tests, etc.

Blockade must be run as root (or with sudo).


Commands
--------

``blockade up``

Start the containers and link them together, if necessary.


``blockade destroy``

Destroys all containers and restore networks.


``blockade status``

Print the status of the containers and blockade.


``blockade flaky n1``

``blockade flaky n1 n2``

Make network flaky to one or more containers.


``blockade slow n1``

Make network slow to one or more containers.


``blockade fast n1``

Restore network speed and reliability to one or more containers.


``blockade partition n1,n2``

``blockade partition n1,n2 n3,n4``

Create one or more network partitions. Each partition is specified as a
comma-separated list. Containers may not exist in more than one partition.
Containers not specified are grouped into an implicit partition. Each
partition command replaces any previous partition or block rules.


``blockade join``

Remove all partitions between containers.

License
-------

Blockade is offered under the Apache License 2.0.

Development
-----------

Install test depenedencies with ``pip install blockade[test]``.

You can run integration tests in a Vagrant VM using the included Vagrantfile.
Run ``vagrant up`` and Docker will be installed in your VM and tests run.
You can rerun them with ``vagrant provision``, or SSH into the VM and run
them yourself, from ``/vagrant``.

Blockade documentation is built with [Sphinx](http://sphinx-doc.org) and is
found under ``docs/``. To build:

```
  $ pip install -r requirements_docs.txt
  $ cd docs/
  $ make html
```

HTML output will be under ``docs/_build/html/``.
