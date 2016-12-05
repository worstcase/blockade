.. _install:

============
Requirements
============

You need an accessible `Docker Engine`_ API, and the ability to launch
privileged containers with host networking. Docker can be local or remote.
If remote, set ``DOCKER_HOST`` and the other `environment variables`_
to configure the URL and credentials. Generally, if the ``docker`` cli
works, so should Blockade.

Docker Swarm is not supported at this time.

==========
Installing
==========

Blockade can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

    $ pip install blockade


macOS or Windows
----------------

Blockade works on macOS either natively pointing to a remote Docker Engine API
or via `Docker for Mac`_.

Blockade does not support Windows native containers. Nor is it known to work
with `Docker for Windows`_, but this may be possible. One option is to run
Blockade itself in a container, in daemon mode, and talk to it via the
:ref:`rest`.

Another great option is `Vagrant`_, to run Blockade and Docker in a Linux VM.
Use the included ``Vagrantfile`` or another approach to get Docker and
Blockade installed into a Linux VM. If you have `Vagrant`_ installed, running
``vagrant up`` from the Blockade checkout directory should get you started.
Note that this may take a while, to download needed VMs and Docker containers.

.. _Docker Engine: https://docs.docker.com/engine/installation/
.. _environment variables: https://docs.docker.com/engine/reference/commandline/cli/#/environment-variables
.. _Docker for Mac: https://docs.docker.com/docker-for-mac/
.. _Vagrant: http://www.vagrantup.com
