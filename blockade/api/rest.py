#
#  Copyright (C) 2016 Dell, Inc.
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
import signal
import sys
import traceback

from flask import Flask, abort, jsonify, request, Response
from gevent.wsgi import WSGIServer

from blockade import chaos
from blockade import errors
from blockade.api.manager import BlockadeManager
from blockade.config import BlockadeConfig
from blockade.errors import DockerContainerNotFound
from blockade.errors import InvalidBlockadeName


app = Flask(__name__)


def stack_trace_handler(signum, frame):
    code = []
    code.append(" === Stack trace Begin === ")
    for threadId, stack in list(sys._current_frames().items()):
        code.append("##### Thread %s #####" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('\tFile: "%s", line %d, in %s' %
                        (filename, lineno, name))
        if line:
            code.append(line)
    code.append(" === Stack trace End === ")
    app.logger.warn("\n".join(code))


def start(data_dir='/tmp', port=5000, debug=False, host_exec=None):
    signal.signal(signal.SIGUSR2, stack_trace_handler)

    BlockadeManager.set_data_dir(data_dir)
    if host_exec:
        BlockadeManager.set_host_exec(host_exec)
    app.debug = debug
    http_server = WSGIServer(('', port), app)
    http_server.serve_forever()


############## ERROR HANDLERS ##############


@app.errorhandler(415)
def unsupported_media_type(error):
    return 'Content-Type must be application/json', 415


@app.errorhandler(404)
def blockade_name_not_found(error):
    return 'Blockade name not found', 404


@app.errorhandler(InvalidBlockadeName)
def invalid_blockade_name(error):
    return 'Invalid blockade name', 400


@app.errorhandler(DockerContainerNotFound)
def docker_container_not_found(error):
    return 'Docker container not found', 400


################### ROUTES ###################


@app.route("/blockade")
def list_all():
    blockades = BlockadeManager.get_all_blockade_names()
    return jsonify(blockades=blockades)


@app.route("/blockade/<name>", methods=['POST'])
def create(name):
    if not request.headers['Content-Type'] == 'application/json':
        abort(415)

    if BlockadeManager.blockade_exists(name):
        return 'Blockade name already exists', 400

    # This will abort with a 400 if the JSON is bad
    data = request.get_json()
    config = BlockadeConfig.from_dict(data)
    BlockadeManager.store_config(name, config)

    b = BlockadeManager.get_blockade(name)
    containers = b.create()

    return '', 204


@app.route("/blockade/<name>", methods=['PUT'])
def add(name):
    if not request.headers['Content-Type'] == 'application/json':
        abort(415)

    if not BlockadeManager.blockade_exists(name):
        abort(404)

    data = request.get_json()
    containers = data.get('containers')
    b = BlockadeManager.get_blockade(name)
    b.add_container(containers)

    return '', 204


@app.route("/blockade/<name>/action", methods=['POST'])
def action(name):
    if not request.headers['Content-Type'] == 'application/json':
        abort(415)

    if not BlockadeManager.blockade_exists(name):
        abort(404)

    commands = ['start', 'stop', 'restart', 'kill']
    data = request.get_json()
    command = data.get('command')
    container_names = data.get('container_names')
    if command is None:
        return "'command' not found in body", 400
    if command not in commands:
        error_str = "'%s' is not a valid action" % command
        return error_str, 400
    if container_names is None:
        return "'container_names' not found in body", 400

    b = BlockadeManager.get_blockade(name)
    if 'kill' == command:
        signal = request.args.get('signal', 'SIGKILL')
        getattr(b, command)(container_names, signal=signal)
    else:
        getattr(b, command)(container_names)

    return '', 204


@app.route("/blockade/<name>/partitions", methods=['POST'])
def partitions(name):
    if not request.headers['Content-Type'] == 'application/json':
        abort(415)

    if not BlockadeManager.blockade_exists(name):
        abort(404)

    b = BlockadeManager.get_blockade(name)

    if request.args.get('random', False):
        b.random_partition()
        return '', 204

    data = request.get_json()
    partitions = data.get('partitions')
    if partitions is None:
        return "'partitions' not found in body", 400
    for partition in partitions:
        if not isinstance(partition, list):
            return "'partitions' must be a list of lists", 400
    b.partition(partitions)

    return '', 204


@app.route("/blockade/<name>/partitions", methods=['DELETE'])
def delete_partitions(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404)

    b = BlockadeManager.get_blockade(name)
    b.join()
    return '', 204


@app.route("/blockade/<name>/network_state", methods=['POST'])
def network_state(name):
    if not request.headers['Content-Type'] == 'application/json':
        abort(415)

    if not BlockadeManager.blockade_exists(name):
        abort(404)

    network_states = ['flaky', 'slow', 'fast', 'duplicate']
    data = request.get_json()
    network_state = data.get('network_state')
    container_names = data.get('container_names')
    if network_state is None:
        return "'network_state' not found in body", 400
    if network_state not in network_states:
        error_str = "'%s' is not a valid network state" % network_state
        return error_str, 400
    if container_names is None:
        return "'container_names' not found in body", 400

    b = BlockadeManager.get_blockade(name)
    getattr(b, network_state)(container_names)

    return '', 204


@app.route("/blockade/<name>")
def status(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)

    containers = {}
    b = BlockadeManager.get_blockade(name)
    for container in b.status():
        containers[container.name] = container.to_dict()

    return jsonify(containers=containers)


@app.route("/blockade/<name>/events")
def get_events(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)

    b = BlockadeManager.get_blockade(name)

    def generate():
        yield '{"events": ['
        for a in b.get_audit().read_logs(as_json=False):
            yield a
        yield ']}'

    return Response(generate(), mimetype='application/json')


@app.route("/blockade/<name>", methods=['DELETE'])
def destroy(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404)

    if _chaos.exists(name):
        try:
            _chaos.delete(name)
        except errors.BlockadeUsageError as bue:
            app.logger.error(bue)

    b = BlockadeManager.get_blockade(name)
    b.destroy()
    b.get_audit().clean()
    BlockadeManager.delete_config(name)

    return '', 204


_chaos = chaos.Chaos()


def _validate_chaos_input(option):
    valid_inputs = [
        "min_start_delay", "max_start_delay",
        "min_run_time", "max_run_time",
        "min_containers_at_once", "max_containers_at_once",
        "event_set"
    ]
    for o in option:
        if o not in valid_inputs:
            raise errors.BlockadeHttpError(400, "%s is not a valid input")


@app.route("/blockade/<name>/chaos", methods=['POST'])
def chaos_new(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)
    if not request.headers['Content-Type'] == 'application/json':
        abort(415, "The body is not in JSON format")
    options = request.get_json()
    _validate_chaos_input(options)
    try:
        _chaos.new_chaos(BlockadeManager.get_blockade(name), name, **options)
        return "Successfully started chaos on %s" % name, 201
    except errors.BlockadeUsageError as bue:
        app.logger.error(str(bue))
        return bue.http_msg, bue.http_code


@app.route("/blockade/<name>/chaos", methods=['PUT'])
def chaos_update(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)
    options = request.get_json()
    _validate_chaos_input(options)
    try:
        _chaos.update_options(name, **options)
        return "Updated chaos on %s" % name, 200
    except errors.BlockadeUsageError as bue:
        app.logger.error(str(bue))
        return bue.http_msg, bue.http_code


@app.route("/blockade/<name>/chaos", methods=['DELETE'])
def chaos_destroy(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)
    try:
        _chaos.stop(name)
        _chaos.delete(name)
        return "Deleted chaos on %s" % name, 200
    except errors.BlockadeUsageError as bue:
        app.logger.error(str(bue))
        return str(bue), 500


@app.route("/blockade/<name>/chaos", methods=['GET'])
def chaos_status(name):
    if not BlockadeManager.blockade_exists(name):
        abort(404, "The blockade %s does not exist" % name)
    try:
        status = _chaos.status(name)
        return jsonify(status=status)
    except errors.BlockadeUsageError as bue:
        app.logger.error(str(bue))
        return str(bue), 500
