Changelog
=========

0.2.0 (2015-12-23)
------------------
- #14: Support for docker >1.6, with the native driver. Eliminates the need
  to use the deprecated LXC driver. Contributed by Gregor Uhlenheuer.
- #12: Fix port publishing. **Breaking change**: the order of port publishing was
  swapped to be ``{external: internal}``, to be consistent with the docker
  command line. Contributed by aidanhs.
- Introduces new ``duplicate`` command, which causes some packets to a container
  to be duplicated. Contributed by Gregor Uhlenheuer.
- Introduces new ``start``, ``stop``, and ``restart`` commands, which manage
  specified containers via Docker. Contributed By Gregor Uhlenheuer.
- Introduces new random partition behavior: ``blockade partition --random`` will
  create zero or more random partitions. Contributed By Gregor Uhlenheuer.
- Reworked the blockade ID generation to be more like docker-compose, instead
  of using randomly-generated IDs. If ``--name`` is specified on the command
  line, this is used as the blockade ID and is prefixed to container names.
  Otherwise the blockade name is taken from the basename of the current
  working directory.
- Numerous other small fixes and features, many contributed by Gregor
  Uhlenheuer. Thanks Gregor!


0.1.2 (2015-1-28)
-----------------

- #6: Change ``ports`` config keyword to match docker usage. It now publishes a
  container port to the host. The ``expose`` config keyword now offers the
  previous behavior of ``ports``: it makes a port available from the container,
  for linking to other containers. Thanks to Simon Bahuchet for the
  contribution.
- #9: Fix logs command for Python 3.
- Updated dependencies.


0.1.1 (2014-02-12)
------------------

- Support for Python 2.6 and Python 3.x


0.1.0 (2014-02-11)
------------------

- Initial release of Blockade!
