"""
data.py : Data APIs

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
from epc.common.data.channel import DataChannel
from epc.common.exceptions import DataError


class DataBroker(object):
    def __init__(self):
        self.__channels = dict()

    def start(self):
        return True

    def stop(self):
        for channel in self.__channels.values():  # type: DataChannel
            channel.flush()
        return True

    def flush(self, data_type=None):
        channels = [self.__get_channel(data_type)] if data_type else [self.__get_channel(x) for x in self.__channels.values()]
        for chan in channels:  # type: DataChannel
            if chan:
                chan.flush()
        return True

    def notify(self):
        for chan in self.__channels.values():  # type: DataChannel
            notify = getattr(chan, 'notify', None)
            if callable(notify):
                notify()

    def __get_channel(self, data_type):
        channel = self.__channels.get(data_type)
        if channel:
            return channel
        # FIXME: [?] Add basic / immutable channels in agentlib to avoid hard dependency to epclib
        # Lazy import from epclib
        try:
            from epclib.transport import channels
            channel_class = channels.get(data_type)
            if channel_class:
                channel = channel_class()
                self.__channels[data_type] = channel
                return channel
        except ImportError:
            pass
        return None

    _marker = object

    def get(self, data_type, key, use_cache=True, default=_marker):
        channel = self.__get_channel(data_type)
        try:
            if channel:
                return channel.get(key, use_cache)
            else:
                raise DataError("No channel available")
        except DataError:
            if default != self._marker:
                return default
            raise
        except Exception as e:
            if default != object:
                return default
            raise DataError("Other exception") from e

    def send(self, data_type, key, data):
        channel = self.__get_channel(data_type)
        if channel:
            try:
                return channel.send(key, data)
            except DataError:
                raise
            except Exception as e:
                raise DataError("Other exception") from e
        raise DataError("No channel available")
