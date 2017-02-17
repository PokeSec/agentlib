"""
worker.py : Entry point for worker processes

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
import importlib
import logging
import logging.config
from threading import Thread

import epc.common.settings as settings
from epc.common.auth import EPCAuth
from epc.common.comm import req_sess
from epc.common.importer import setup_importer
from epc.common.sentry import client


class Worker(object):
    """Worker class"""
    def __init__(self, *args, **kwargs):
        self.__local_env = {}

        self.data = {
            'module': kwargs.pop('__module')
        }
        self.__stop_events = kwargs.pop('__stop')

        # Setup the authenticator in the app itself
        authenticator = EPCAuth(None)
        authenticator.token = kwargs.pop('__auth_token', None)
        req_sess.auth = authenticator

        try:
            logging.config.dictConfig(settings.Config().LOGGER_CONF)
        except (ValueError, TypeError, AttributeError, ImportError):
            pass

        setup_importer()

        self.args = args
        self.kwargs = kwargs
        self.app = None

    def run(self) -> int:
        """Run the worker"""
        try:
            module = importlib.import_module('apps.{}'.format(self.data['module']))
        except ImportError:
            client.captureException()
            logging.exception("Import error while importing app")
            return -2
        self.app = module.APPCLASS(platform=settings.Config().PLATFORM)
        if not self.app:
            client.captureMessage("Attempt to run an empty class")
            logging.warning("App is empty")
            return -2

        # Setup the logger
        logger = logging.getLogger('{}'.format(self.data['module']))
        self.app.logger = logger

        # Start the stop thread
        stop_thread = Thread(target=self.__stop_worker)
        stop_thread.start()

        ret = -1

        # Run the target code
        try:
            ret = self.app.run(args=self.args, kwargs=self.kwargs)
        except KeyboardInterrupt:
            logger.warning("Execution aborted")
            ret = False
        except:
            logging.exception("Uncaught exception in app code")
            client.captureException()
        finally:
            self.__stop_events[0].set()
            stop_thread.join()
            return ret

    def __stop_worker(self):
        """Stop the worker"""
        self.__stop_events[0].wait()
        if self.app:
            self.app.stop()
        self.__stop_events[1].set()


def run(*args, **kwargs) -> int:
    """Main function of the worker"""
    try:
        worker = Worker(*args, **kwargs)
        return worker.run()
    except:
        client.captureException()
        logging.exception("Uncaught exception in worker")
        return -1
