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

from blockade.config import BlockadeConfig
from blockade.core import Blockade
from blockade.errors import BlockadeNotFound
from blockade.errors import InvalidBlockadeName
from blockade.net import BlockadeNetwork
from blockade.state import BlockadeState

import os
import yaml


DATA_DIR = "/tmp"
BASE_BLOCKADE_DIR = os.path.join(DATA_DIR, ".blockade")
REST_STATE_FILE = os.path.join(BASE_BLOCKADE_DIR, "rest_state.yaml")


class BlockadeManager:
    """Simple helper to persist Blockade configurations managed via REST API
    """

    @staticmethod
    def set_data_dir(data_dir):
        global DATA_DIR
        DATA_DIR = data_dir
        BASE_BLOCKADE_DIR = os.path.join(DATA_DIR, ".blockade")
        REST_STATE_FILE = os.path.join(BASE_BLOCKADE_DIR, "rest_state.yaml")


    @staticmethod
    def init_base_blockade_dir():
        if not os.path.isdir(BASE_BLOCKADE_DIR):
            os.makedirs(BASE_BLOCKADE_DIR)

    @staticmethod
    def read_rest_state():
        BlockadeManager.init_base_blockade_dir()
        rest_state = {}
        if os.path.exists(REST_STATE_FILE):
            with open(REST_STATE_FILE, "r") as f:
                rest_state = yaml.safe_load(f) or {}
        return rest_state

    @staticmethod
    def write_rest_state(rest_state):
        BlockadeManager.init_base_blockade_dir()
        with open(REST_STATE_FILE, "w") as f:
            yaml.safe_dump(rest_state, f)

    @staticmethod
    def blockade_exists(name):
        rest_state = BlockadeManager.read_rest_state()
        return name in rest_state

    @staticmethod
    def store_config(name, config):
        rest_state = BlockadeManager.read_rest_state()
        rest_state[name] = config
        BlockadeManager.write_rest_state(rest_state)

    @staticmethod
    def delete_config(name):
        rest_state = BlockadeManager.read_rest_state()
        if name in rest_state:
            del rest_state[name]
        else:
            raise BlockadeNotFound()
        BlockadeManager.write_rest_state(rest_state)

    @staticmethod
    def get_blockade(name):
        rest_state = BlockadeManager.read_rest_state()
        blockade_state = BlockadeManager.load_blockade_state(name)
        if name not in rest_state:
            raise BlockadeNotFound()
        config = BlockadeConfig.from_dict(rest_state[name])
        return Blockade(config,
                        blockade_id=name,
                        state=blockade_state,
                        network=BlockadeNetwork(config))

    @staticmethod
    def get_all_blockade_names():
        rest_state = BlockadeManager.read_rest_state()
        return list(rest_state.keys())

    @staticmethod
    def load_blockade_state(name):
        global DATA_DIR
        try:
            return BlockadeState(blockade_id=name, data_dir=DATA_DIR)
        except InvalidBlockadeName:
            raise
