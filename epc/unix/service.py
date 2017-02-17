"""
service.py : Main module for Unix service

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
import signal
import logging

from epc.pc.service import EPCService
from epc.common.utils import Singleton


class UnixService(EPCService):
    """Unix main service"""

    def __init__(self):
        super(UnixService, self).__init__()

    @EPCService.os.getter
    def os(self):
        return 'unix'


class Service(metaclass=Singleton):
    """Service class to be used on Unix platforms"""

    def __init__(self):
        self.__service = UnixService()

    def setup(self):
        return self.__service.setup()

    def start(self):
        return self.__service.start()

    def stop(self):
        self.__service.set_stop_event()
        self.__service.shutdown()
        logging.info('Stopping service ...')


def _signal_handler(*_):
    """Unix signal handler"""
    s = Service()
    s.stop()


def main():
    """Entry point"""
    signal.signal(signal.SIGTERM, _signal_handler)
    service = Service()
    try:
        if service.setup():
            service.start()
        else:
            logging.error("Could not start service, exiting")
    except KeyboardInterrupt:
        logging.info("Caught KeyboardInterrupt, stopping service")
        service.stop()

if __name__ == "__main__":
    main()
