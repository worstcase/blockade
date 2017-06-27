Changelog
=========

0.4.0 (2017-06-26)
------------------
- Added new chaos functionality. When used, blockade will randomly
  select containers to impair with partitions, slow network, etc.
  Contributed by John Bresnahan (@buzztroll) of Stardog Union.
- Added an event trail that logs all blockade events that are run
  against a blockade over its lifetime. This can be helpful in
  correlating blockade events to application errors. Contributed by
  John Bresnahan (@buzztroll) of Stardog Union.
- Substantially improved overall performance by using a cached container
  for all host commands.
- #62: Fixed bug with using blockade commands against a restarted
  container. Contributed by John Bresnahan (@buzztroll) of Stardog Union.
- Updated Docker SDK and API version. Contributed by Vladimir Borodin
  (dev1ant).


0.3.1 (2016-12-09)
------------------
- #43: Restore support for loading from ``blockade.yml`` config file.
- #26: Improved error messages when running blockade without access
  to the Docker API.
- #25: Improved error messages when determining container host network
  device fails.
- #40: Fixed ``kill`` command (broken in 0.3.0).
- #1: Fixed support for configuring Docker API via ``DOCKER_HOST`` env.
- #36: Truncate long blockade IDs to avoid iptables limits.
- Switched to directly inspecting ``/sys`` for container network devices
  instead of via ``ip``. This means containers no longer need to have ``ip``
  installed.
- Improved Blockade Python API by returning names of the containers a
  command has operated on. Contributed by Gregor Uhlenheuer (@kongo2002).
- Fixed ``Vagrantfile`` to also work on Windows. Contributed by Oresztesz
  Margaritisz (@gitaroktato).
- Documentation fix contributed by Konrad Klocek (@kklocek).
- Added new ``version`` command that prints Blockade version and exits.
- Added ``cap_add`` container config option, for specifying additional
  root capabilities. Contributed by Maciej Zimnoch (@Zimnx).


0.3.0 (2016-10-29)
------------------
- Reworks all network commands to run in Docker containers. This allows
  Blockade to be run without root privileges, as long as the user can
  access Docker.
- Introduces a REST API and daemon mode that allows creation and
  management of blockades remotely.
- Adds ability to add a container to a running blockade, via ``add``
  command.
- Adds support for Docker user-defined networks to allow any-to-any
  communication between containers, without links. Contributed by
  Stas Kelvich (@kelvich).
- Adds ability to configure DNS servers for containers in a blockade.
  Contributed by Vladimir Borodin (@dev1ant).
- Adds a generic ``--random`` flag for many commands to allow easier
  randomized chaos testing. Contributed by Gregor Uhlenheuer (@kongo2002).
- Introduces a new ``kill`` command for killing containers in a blockade.
- Fixed links to Docker documentation. Contributed by @joepadmiraal.
- Fixed links of named containers. Contributed by Gregor Uhlenheuer
  (@kongo2002).


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
