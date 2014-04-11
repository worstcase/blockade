.. _install:

============
Requirements
============

Docker must be installed and configured to use the LXC driver. The
``native`` libcontainer driver is not yet supported by Blockade because
it does not expose the necessary network parameters.

Configure the LXC driver by adding ``-e lxc`` to your Docker daemon options.
On Ubuntu, this is done by adding the following to ``/etc/default/docker``:

.. code-block:: bash

    DOCKER_OPTS="-e lxc"

Note you will also need to have the LXC command-line utilities installed.

==========
Installing
==========

Blockade can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

    $ pip install blockade

Because Blockade directly executes ``iptables`` and ``tc`` commands, it must
be installed on a Linux system or VM and run as root.


OSX
---

If you are using OSX, Blockade and Docker cannot yet be truly run natively.
Use the included ``Vagrantfile`` or another approach to get Docker and
Blockade installed into a Linux VM. If you have `Vagrant`_ installed, running
``vagrant up`` from the Blockade checkout directory should get you started.
Note that this may take a while, to download needed VMs and Docker containers.

.. _Vagrant: http://www.vagrantup.com
