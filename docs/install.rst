.. _install:

============
Requirements
============

Docker must be installed.

==========
Installing
==========

Blockade can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

    $ pip install blockade

Because Blockade executes ``iptables`` and ``tc`` commands, it must
be installed on a Linux system or VM. It must be run as a user that
has an ability to launch Docker containers. Typically this is done
by adding the user to the ``docker`` group.

It is potentially possibly to make Blockade talk to a remote Docker API
but this is not yet supported.


OSX
---

If you are using OSX, Blockade and Docker cannot yet be truly run natively.
Use the included ``Vagrantfile`` or another approach to get Docker and
Blockade installed into a Linux VM. If you have `Vagrant`_ installed, running
``vagrant up`` from the Blockade checkout directory should get you started.
Note that this may take a while, to download needed VMs and Docker containers.

.. _Vagrant: http://www.vagrantup.com
