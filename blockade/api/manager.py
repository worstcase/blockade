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

from blockade.core import Blockade
from blockade.errors import InvalidBlockadeName
from blockade.net import BlockadeNetwork
from blockade.state import BlockadeState

# TODO(pdmars): breaks if server restarts, refactor to be part of BlockadeState
BLOCKADE_CONFIGS = {}
DATA_DIR = "/tmp"


class BlockadeManager:
    """Simple helper for what should eventually be persisted via BlockadeState
    """
    host_exec = None

    @staticmethod
    def set_data_dir(data_dir):
        global DATA_DIR
        DATA_DIR = data_dir

    @staticmethod
    def set_host_exec(host_exec):
        BlockadeManager.host_exec = host_exec

    @staticmethod
    def blockade_exists(name):
        global BLOCKADE_CONFIGS
        return name in BLOCKADE_CONFIGS

    @staticmethod
    def store_config(name, config):
        global BLOCKADE_CONFIGS
        BLOCKADE_CONFIGS[name] = config

    @staticmethod
    def delete_config(name):
        global BLOCKADE_CONFIGS
        if name in BLOCKADE_CONFIGS:
            del BLOCKADE_CONFIGS[name]

    @staticmethod
    def load_state(name):
        global DATA_DIR
        try:
            return BlockadeState(blockade_id=name, data_dir=DATA_DIR)
        except InvalidBlockadeName:
            raise

    @staticmethod
    def get_blockade(name):
        global BLOCKADE_CONFIGS
        config = BLOCKADE_CONFIGS[name]
        host_exec = BlockadeManager.host_exec
        if host_exec is None:
            raise ValueError("host exec not set")
        return Blockade(config,
                        blockade_id=name,
                        state=BlockadeManager.load_state(name),
                        network=BlockadeNetwork(config, host_exec))

    @staticmethod
    def get_all_blockade_names():
        global BLOCKADE_CONFIGS
        return list(BLOCKADE_CONFIGS.keys())
