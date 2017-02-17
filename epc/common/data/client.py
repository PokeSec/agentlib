"""
client.py : Data client

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
from .broker import DataBroker
from epc.common.utils import Singleton


class DataException(Exception):
    """Exception for the data module"""

    def __init__(self, message):
        super(DataException, self).__init__(message)


class DataClient(metaclass=Singleton):
    """Data broker"""

    def __init__(self, broker=DataBroker):
        self.__broker = broker()

    def stop(self) -> bool:
        if self.__broker:
            return self.__broker.stop()
        return True

    def flush(self, data_type: str = None) -> bool:
        if self.__broker:
            return self.__broker.flush(data_type)
        return True

    def get(self, data_type: str, key: str, use_cache: bool = True):
        if self.__broker:
            try:
                result = self.__broker.get(data_type, key, use_cache)
                if isinstance(result, Exception):
                    raise result
                return result
            except NotImplementedError:
                raise DataException("Method [get] is not implemented for {}".format(data_type))
        else:
            raise DataException("No broker available")

    def send(self, data_type: str, key: str, data):
        if self.__broker:
            try:
                return self.__broker.send(data_type, key, data)
            except NotImplementedError:
                raise DataException("Method [send] is not implemented for {}".format(data_type))
        else:
            raise DataException("No broker available")

    def notify(self):
        if self.__broker:
            self.__broker.notify()
