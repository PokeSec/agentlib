"""
settings.py : Project configuration

This file is part of EPControl.

Copyright (C) 2016  Jean-Baptiste Galet & Timothe Aeberhardt

EPControl is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

EPControl is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with EPControl.  If not, see <http://www.gnu.org/licenses/>.
"""
import json
import base64
from typing import Optional

from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA512
from Crypto.PublicKey import RSA

from epc.common.utils import Singleton


class Config(metaclass=Singleton):
    """Config class"""
    def __init__(self):
        self.__data = dict()
        self.__user_data = dict()
        self.__load_config()
        self.pub_key = None
        self.pub_key = open('settings_sign.pem', 'r').read()  # may raise OSError - expected behavior

    def __load_config(self):
        """Load the config from files"""
        try:
            self.__load_config_file('settings.json', 'system', '*')
        except:
            raise
            # pass

        for config_file in self.EXTRA_CONFIG:
            try:
                self.__load_config_file(config_file['file'], config_file['type'], config_file['parameters'])
            except:
                pass

    def __load_config_file(self, filename: str, config_type: str, allowed_parameters: Optional[list] = None):
        """Load a config file"""
        if not allowed_parameters:
            allowed_parameters = []

        with open(filename, 'r') as ifile:
            contents = json.load(ifile)
            if config_type == 'user':
                for key, val in contents.items():
                    if key in allowed_parameters or allowed_parameters == '*':
                        self.__user_data[key] = val
            else:
                signature = contents.get('sign')
                data = contents.get('data')
                if not signature or not data:
                    raise RuntimeError('Invalid configuration')
                signature = base64.b64decode(signature)
                if not self.__verify_signature(signature, data.encode('utf-8')):
                    raise RuntimeError('Invalid configuration signature')
                contents_data = json.loads(base64.b64decode(data).decode('utf-8'))
                for key, val in contents_data.items():
                    if key in allowed_parameters or allowed_parameters == '*':
                        self.__data[key] = val

    def __verify_signature(self, signature: bytes, data: bytes) -> bool:
        """Check the config signature"""
        key = RSA.importKey(self.pub_key)
        hashalgo = SHA512.new()
        hashalgo.update(data)
        verifier = PKCS1_PSS.new(key)
        return verifier.verify(hashalgo, signature)

    def reload(self):
        """Reload the configuration"""
        self.__load_config()

    def add_setting(self, key: str, value) -> bool:
        """Add a configuration parameter"""
        if not self.EXTRA_CONFIG:
            return False
        self.__user_data[key] = value
        for config_file in self.EXTRA_CONFIG:
            if config_file['type'] == 'user':
                try:
                    with open(config_file['file'], 'w') as ofile:
                        json.dump(self.__user_data, ofile)
                        return True
                except:
                    continue
        return False

    def __getattr__(self, key: str):
        extra = self.__user_data.get(key)
        if extra is not None:
            return extra
        return self.__data.get(key)

    def get(self, key: str, default=None):
        """Get a parameter with an optional default value"""
        extra = self.__user_data.get(key)
        if extra is not None:
            return extra
        return self.__data.get(key, default)
