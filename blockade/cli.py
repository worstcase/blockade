#
#  Copyright (C) 2014 Dell, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import os
import threading
import argparse
import errno
import json
import sys
import traceback
import yaml
import signal

from clint.textui import puts, puts_err, colored, columns

from .api import rest
from .chaos import BlockadeChaos
from .config import BlockadeConfig
from .core import Blockade
from .errors import BlockadeError
from .errors import InsufficientPermissionsError
from .net import BlockadeNetwork
from .state import BlockadeState
from .utils import check_docker
from .host import HostExec


_logger = logging.getLogger(__name__)


def load_config(config_file=None):
    error = None
    try:
        # if a path was specified, load only from there and fail if not found
        if config_file is not None:
            with open(config_file) as f:
                d = yaml.safe_load(f)
                return BlockadeConfig.from_dict(d)

        # otherwise, try the default paths
        for path in ("blockade.yaml", "blockade.yml"):
            try:
                with open(path) as f:
                    d = yaml.safe_load(f)
                    return BlockadeConfig.from_dict(d)
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise

        # finally, return a "blank" config. This may be an empty blockade that
        # containers will later be added to
        return BlockadeConfig()
    except Exception as e:
        error = e
    raise BlockadeError("Failed to load config (from --config, "
                        "./blockade.yaml, or ./blockade.yml)" +
                        (": " + str(error) if error else ""))


def get_blockade(config, opts):
    blockade_id = opts.name if hasattr(opts, 'name') else None
    state = BlockadeState(blockade_id=blockade_id,
                          data_dir=opts.data_dir)
    return Blockade(config,
                    blockade_id=blockade_id,
                    state=state,
                    network=BlockadeNetwork(config, get_host_exec()))


_host_exec = None


def get_host_exec():
    global _host_exec
    if _host_exec is not None:
        return _host_exec

    host_exec = HostExec()
    _host_exec = host_exec
    return host_exec


def print_containers(containers, to_json=False):
    containers = sorted(containers, key=lambda c: c.name)

    if to_json:
        d = [c.to_dict() for c in containers]
        puts(json.dumps(d, indent=2, sort_keys=True, separators=(',', ': ')))

    else:
        puts(colored.blue(columns(["NODE",               15],
                                  ["CONTAINER ID",       15],
                                  ["STATUS",              7],
                                  ["IP",                 15],
                                  ["NETWORK",            10],
                                  ["PARTITION",          10])))

        def partition_label(c):
            if c.holy:
                return "H"
            elif c.partition:
                if c.neutral:
                    return str(c.partition) + " [N]"
                else:
                    return str(c.partition)
            elif c.neutral:
                return "N"
            else:
                return ""

        for container in containers:
            puts(columns([container.name,                15],
                         [container.container_id[:12],   15],
                         [container.status,               7],
                         [container.ip_address or "",    15],
                         [container.network_state,       10],
                         [partition_label(container),    10]))


def _add_output_options(parser):
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')


def _add_container_selection_options(parser):
    parser.add_argument('containers', metavar='CONTAINER', nargs='*',
                        help='Container to select')
    parser.add_argument('--all', action='store_true',
                        help='Select all containers')
    parser.add_argument('--random', action='store_true',
                        help='Select a random container')


def _check_container_selections(opts):
    if opts.containers and opts.all:
        raise BlockadeError("Either specify individual containers "
                            "or --all, but not both")
    elif opts.all and opts.random:
        raise BlockadeError("Specify either --all or --random, but not both")
    elif not (opts.containers or opts.all or opts.random):
        raise BlockadeError(
            "Specify individual containers or --all or --random")

    return (opts.containers or None, opts.all, opts.random)


def cmd_up(opts):
    """Start the containers and link them together
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    containers = b.create(verbose=opts.verbose, force=opts.force)
    print_containers(containers, opts.json)


def cmd_destroy(opts):
    """Destroy all containers and restore networks
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    b.destroy()


def cmd_status(opts):
    """Print status of containers and networks
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    containers = b.status()
    print_containers(containers, opts.json)


def __with_containers(opts, func, **kwargs):
    containers, select_all, select_random = _check_container_selections(opts)
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    b.state.load()

    configured_containers = set(b.state.containers.keys())
    container_names = configured_containers \
        if select_all or (select_random and not containers)\
        else configured_containers.intersection(containers)

    if len(container_names) > 0:
        kwargs['select_random'] = select_random
        return func(b, container_names, **kwargs)
    else:
        raise BlockadeError('selection does not match any container')


def cmd_start(opts):
    """Start some or all containers
    """
    __with_containers(opts, Blockade.start)


def cmd_kill(opts):
    """Kill some or all containers
    """
    kill_signal = opts.signal if hasattr(opts, 'signal') else "SIGKILL"
    __with_containers(opts, Blockade.kill, signal=kill_signal)


def cmd_stop(opts):
    """Stop some or all containers
    """
    __with_containers(opts, Blockade.stop)


def cmd_restart(opts):
    """Restart some or all containers
    """
    __with_containers(opts, Blockade.restart)


def cmd_flaky(opts):
    """Make the network flaky for some or all containers
    """
    __with_containers(opts, Blockade.flaky)


def cmd_slow(opts):
    """Make the network slow for some or all containers
    """
    __with_containers(opts, Blockade.slow)


def cmd_fast(opts):
    """Restore network speed and reliability for some or all containers
    """
    __with_containers(opts, Blockade.fast)


def cmd_duplicate(opts):
    """Introduce packet duplication into the network of some or all containers
    """
    __with_containers(opts, Blockade.duplicate)


def cmd_chaos(opts):
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    b.state.load()

    event_set = None
    if opts.events is not None:
        event_set = [i.strip() for i in opts.events.split(",")]
    if opts.degrade_delay_min > opts.degrade_delay_max:
        opts.degrade_delay_min = opts.degrade_delay_max
    if opts.degrade_runtime_min > opts.degrade_runtime_max:
        opts.degrade_runtime_min = opts.degrade_runtime_max
    if opts.containers_at_once_min > opts.containers_at_once_max:
        opts.containers_at_once_min = opts.containers_at_once_max

    e = threading.Event()

    def chaos_ended():
        e.set()

    c = BlockadeChaos(b, b.state.blockade_id,
                      min_start_delay=opts.degrade_delay_min,
                      max_start_delay=opts.degrade_delay_max,
                      min_run_time=opts.degrade_runtime_min,
                      max_run_time=opts.degrade_runtime_max,
                      min_containers_at_once=opts.containers_at_once_min,
                      max_containers_at_once=opts.containers_at_once_max,
                      event_set=event_set,
                      done_notification_func=chaos_ended)
    try:
        try:
            while not e.is_set():
                # for some reason the thread will not wake up on cnt+c if the
                # event wait is None
                e.wait(100000)
        except KeyboardInterrupt:
            e.set()
            puts_err(colored.green("Shutting down chaos...\n"))
        except BaseException as bex:
            puts_err(colored.red(
                    "An exception occurred during chaos.  Attempting to "
                    "shutdown nicely: %s" % str(bex)))
        c.stop()
        c.delete()
        puts_err(colored.green("Chaos ended.\n"))
    except BaseException as outer_bex:
        puts_err(colored.red(
                "Chaos was not shutdown cleanly.  Containers may be in a "
                "degraded state: %s" % str(outer_bex)))


def cmd_partition(opts):
    """Partition the network between containers

    Replaces any existing partitions outright. Any containers NOT specified
    in arguments will be globbed into a single implicit partition. For
    example if you have three containers: c1, c2, and c3 and you run:

        blockade partition c1

    The result will be a partition with just c1 and another partition with
    c2 and c3.

    Alternatively, --random may be specified, and zero or more random
    partitions will be generated by blockade.
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)

    if opts.random:
        if opts.partitions:
            raise BlockadeError("Either specify individual partitions "
                                "or --random, but not both")
        b.random_partition()

    else:
        partitions = []
        for partition in opts.partitions:
            names = []
            for name in partition.split(","):
                name = name.strip()
                if name:
                    names.append(name)
            partitions.append(names)
        if not partitions:
            raise BlockadeError("Either specify individual partitions "
                                "or random")
        b.partition(partitions)


def cmd_join(opts):
    """Restore full networking between containers
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    b.join()


def cmd_logs(opts):
    """Fetch the logs of a container
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    puts(b.logs(opts.container).decode(encoding='UTF-8'))


def cmd_daemon(opts):
    """Start the Blockade REST API
    """
    if opts.data_dir is None:
        raise BlockadeError("You must supply a data directory for the daemon")
    rest.start(data_dir=opts.data_dir, port=opts.port, debug=opts.debug,
        host_exec=get_host_exec())


def cmd_add(opts):
    """Add one or more existing Docker containers to a Blockade group
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)
    b.add_container(opts.containers)


def cmd_version(opts):
    """Show the Blockade version information
    """
    import blockade.version
    puts("Blockade " + blockade.version.__version__)


def cmd_events(opts):
    """Get the event log for a given blockade
    """
    config = load_config(opts.config)
    b = get_blockade(config, opts)

    if opts.json:
        outf = None
        _write = puts
        if opts.output is not None:
            outf = open(opts.output, "w")
            _write = outf.write
        try:
            delim = ""
            logs = b.get_audit().read_logs(as_json=False)
            _write('{"events": [')
            _write(os.linesep)
            for l in logs:
                _write(delim + l)
                delim = "," + os.linesep
            _write(os.linesep)
            _write(']}')
        finally:
            if opts.output is not None:
                outf.close()
    else:
        puts(colored.blue(columns(["EVENT",         10],
                                  ["TARGET",        16],
                                  ["STATUS",         8],
                                  ["TIME",          16],
                                  ["MESSAGE",       25])))

        logs = b.get_audit().read_logs(as_json=True)
        for l in logs:
            puts(columns([l['event'],                          10],
                         [str([str(t) for t in l['targets']]), 16],
                         [l['status'],                          8],
                         [str(l['timestamp']),                 16],
                         [l['message'],                        25]))


_CMDS = (("up", cmd_up),
         ("destroy", cmd_destroy),
         ("status", cmd_status),
         ("start", cmd_start),
         ("restart", cmd_restart),
         ("stop", cmd_stop),
         ("kill", cmd_kill),
         ("logs", cmd_logs),
         ("flaky", cmd_flaky),
         ("slow", cmd_slow),
         ("duplicate", cmd_duplicate),
         ("fast", cmd_fast),
         ("partition", cmd_partition),
         ("join", cmd_join),
         ("daemon", cmd_daemon),
         ("add", cmd_add),
         ("chaos", cmd_chaos),
         ("events", cmd_events),
         ("version", cmd_version))


def setup_parser():
    parser = argparse.ArgumentParser(description='Blockade')
    parser.add_argument("--config", "-c", metavar="blockade.yaml",
                        help="Config YAML. Looks in CWD if not specified.")
    parser.add_argument(
        "--data-dir", "-d", metavar="DIR", action="store",
        help="Base directory for state data. CWD if not specified.")
    parser.add_argument("-n", "--name", metavar="NAME",
                        help="Unique name for blockade. "
                        "Default: basename of working directory")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print verbose output")
    parser.add_argument("--debug", "-D", action="store_true",
                        help="Print verbose output")
    parser.add_argument("--logconf", "-l",
                        help="Path to the log configuration file.")

    subparsers = parser.add_subparsers(title="commands")

    command_parsers = {}
    for command, func in _CMDS:
        subparser = subparsers.add_parser(
            command,
            description=func.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
        subparser.set_defaults(func=func)
        command_parsers[command] = subparser

    # add additional parameters to some commands
    up_parser = command_parsers["up"]
    _add_output_options(up_parser)
    up_parser.add_argument(
        "-f", "--force", action="store_true",
        help="Try to remove any conflicting containers if necessary")

    _add_output_options(command_parsers["status"])

    _add_container_selection_options(command_parsers["start"])
    _add_container_selection_options(command_parsers["kill"])
    _add_container_selection_options(command_parsers["stop"])
    _add_container_selection_options(command_parsers["restart"])
    _add_container_selection_options(command_parsers["flaky"])
    _add_container_selection_options(command_parsers["slow"])
    _add_container_selection_options(command_parsers["fast"])
    _add_container_selection_options(command_parsers["duplicate"])

    command_parsers["logs"].add_argument("container", metavar='CONTAINER',
                                         help="Container to fetch logs for")

    command_parsers["partition"].add_argument(
        'partitions', nargs='*', metavar='PARTITION',
        help='Comma-separated partition')
    command_parsers["partition"].add_argument(
        "-z", "--random", action='store_true',
        help='Randomly select zero or more partitions')

    command_parsers["kill"].add_argument(
        "-s", "--signal", action="store", default="SIGKILL",
        help="Specify the signal to be sent (str or int). Defaults to "
             "SIGKILL.")

    command_parsers["daemon"].add_argument(
        "-p", "--port", action='store',
        type=int, default=5000, help="REST API port. Default is 5000.")

    command_parsers["add"].add_argument(
        "containers", nargs="*", metavar='CONTAINER',
        help="Docker container to add to the Blockade group")

    command_parsers["chaos"].add_argument(
            "--events",
            help="Only choose events from the given set.  All events are "
                 "enabled by default.")
    command_parsers["chaos"].add_argument(
            "--degrade-delay-min",
            help="The minimum amount of time to wait between blockade "
                 "degradation event in milliseconds.", type=int, default=30000)
    command_parsers["chaos"].add_argument(
            "--degrade-delay-max",
            help="The maximum amount of time to wait between blockade "
                 "degradation event.", type=int, default=300000)
    command_parsers["chaos"].add_argument(
            "--degrade-runtime-min",
            help="The minimum amount of time to run a blockade degradation "
                 "event in milliseconds.", type=int, default=30000)
    command_parsers["chaos"].add_argument(
            "--degrade-runtime-max",
            help="The maximum amount of time to run a blockade degradation "
                 "event in milliseconds.", type=int, default=300000)
    command_parsers["chaos"].add_argument(
            "--containers-at-once-min",
            help="The minimum number of containers to effect at once.",
            type=int, default=1)
    command_parsers["chaos"].add_argument(
            "--containers-at-once-max",
            help="The maximum number of containers to effect at once.",
            type=int, default=1)

    command_parsers["events"].add_argument(
            "--json", action='store_true',
            help="Show the data in JSON format.")
    command_parsers["events"].add_argument(
            "--output",
            help="A path to the file where the data should be written.  The "
                 "default is stdout.",
            type=str)

    return parser


def _setup_logging(opts):
    if opts.logconf is None:
        l = logging.getLogger("blockade")
        if len(l.handlers) > 0:
            # this happens if logging is already setup.  It only comes up in
            # tests
            return
        handler = logging.StreamHandler()
        if opts.debug:
            l.setLevel(logging.DEBUG)
        elif opts.verbose:
            l.setLevel(logging.INFO)
        else:
            l.setLevel(logging.WARN)
        f = '%(asctime)s %(levelname)s %(message)s'
        handler.setFormatter(logging.Formatter(f))
        l.addHandler(handler)
        return
    if not os.path.exists(opts.logconf):
        raise BlockadeError(
                "The logging config file %s does not exist" % opts.logconf)
    with open(opts.logconf, 'r') as f:
        config = yaml.load(f.read())
        logging.config.dictConfig(config)


def run_cleanups():
    _logger.debug("Running cleanup functions")
    try:
        get_host_exec().close()
    except:
        puts_err(
            colored.red("\nUnexpected error in cleanup! This may be a Blockade bug.\n"))
        traceback.print_exc()


def main(args=None):
    if sys.version_info >= (3, 2) and sys.version_info < (3, 3):
        puts_err(colored.red("\nFor Python 3, Flask requires Python >= 3.3\n"))
        sys.exit(1)

    parser = setup_parser()
    opts = parser.parse_args(args=args)
    _setup_logging(opts)

    # register a signal handler to trigger graceful shutdown. The sys.exit
    # call will ultimately trigger the finally block below to run.
    # note that SIGINT is handled below in the normal flow of the try/except
    # block.
    def _signal_handler(*args):
        sys.exit()

    signal.signal(signal.SIGTERM, _signal_handler)

    rc = 0

    try:

        # don't bother pinging docker for a version command
        if opts.func != cmd_version:
            check_docker()

        opts.func(opts)
    except InsufficientPermissionsError as e:
        puts_err(colored.red(
                 "\nInsufficient permissions error:\n") + str(e) + "\n")
        rc = 1
    except BlockadeError as e:
        puts_err(colored.red("\nError:\n") + str(e) + "\n")
        rc = 1

    except KeyboardInterrupt:
        puts_err(colored.red("Caught Ctrl-C. exiting!"))

    except SystemExit:
        pass

    except:
        puts_err(
            colored.red("\nUnexpected error! This may be a Blockade bug.\n"))
        traceback.print_exc()
        rc = 2

    finally:
        run_cleanups()

    sys.exit(rc)


if __name__ == '__main__':
    main()
