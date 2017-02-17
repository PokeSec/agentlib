"""
service.py : Agent Service

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
import logging
import logging.config
import time
from enum import Enum

import epc.common.settings as settings
from epc.common.auth import EPCAuth
from epc.common.comm import req_sess, CommException
from epc.common.platform import PlatformData
from epc.common.scheduler import Scheduler


class EPCService(object):
    """Base class for the Service"""
    class State(Enum):
        """States of modules"""
        unknown = 0
        initializing = 1
        initialized = 2
        starting = 3
        started = 4
        stopping = 5
        stopped = 6
        initialization_failed = 100
        startup_failed = 101
        shutdown_failed = 102

    def __init__(self):
        self._is_setup = False
        self._is_started = False
        self._stopping = False

        self.states = dict(
            logger=self.State.unknown,
            scheduler=self.State.unknown,
            stop_event=self.State.unknown,
            auth=self.State.unknown,
        )

        self.setup_tasks = [
            'logger',
            'auth',
            'scheduler',
            'stop_event'
        ]
        self.start_tasks = [
            'logger',
            'scheduler',  # Scheduler should lock the program
            'stop_event'  # Set the event afer the scheduler stopped
        ]
        self.shutdown_tasks = [
            'scheduler',
            'logger',
            'stop_event'
        ]

        # Classes and methods
        self.scheduler_class = Scheduler

        self.scheduler = None  # type: Scheduler
        self.stop_event = None

    @property
    def os(self):
        """Get the OS name - MUST be overridden in subclasses"""
        return None

    # Logger
    def setup_logger(self) -> bool:
        try:
            logging.config.dictConfig(settings.Config().LOGGER_CONF)
            return True
        except (ValueError, TypeError, AttributeError, ImportError):
            return False

    def start_logger(self) -> bool:
        return True

    def stop_logger(self) -> bool:
        return True

    # Scheduler
    def setup_scheduler(self) -> bool:
        self.scheduler = self.scheduler_class()
        return True

    def start_scheduler(self) -> bool:
        if self.scheduler:
            self.scheduler.run()
        return True

    def stop_scheduler(self) -> bool:
        if self.scheduler and not self.scheduler.stop():
            logging.warning("Scheduler didn't stop properly, killing ...")
        return True

    # StopEvent
    def setup_stop_event(self) -> bool:
        return True

    def start_stop_event(self) -> bool:
        return True

    def stop_stop_event(self) -> bool:
        return True

    def set_stop_event(self) -> bool:
        return True

    # Auth
    def setup_auth(self) -> bool:
        if not settings.Config().INSTANCE_ID:
            return False

        if not settings.Config().AGENT_TOKEN:
            while not self._stopping:
                if self._stopping:
                    return False
                if not self.enroll():
                    logging.info("Could not enroll, waiting")
                    time.sleep(settings.Config().get("ENROLL_WAIT", 10))
                else:
                    break

        if not settings.Config().AGENT_TOKEN:
            return False

        authenticator = EPCAuth(PlatformData(self.os).get_data(force=True))

        while not self._stopping:
            try:
                if authenticator.authenticate():
                    req_sess.auth = authenticator
                    return True
            except CommException:
                pass
            # FIXME: Handle error
            except:
                return False
            settings.Config().reload()
            logging.info("Could not auth, waiting")
            time.sleep(settings.Config().get("AUTH_WAIT", 10))

    def enroll(self) -> bool:
        """Enroll the gent with the backend"""
        auth_data = PlatformData(self.os).get_data()
        try:
            req = req_sess.post('enroll', json=auth_data)
            if not req.ok:
                return False
            auth_data['token'] = req.text
            return settings.Config().add_setting('AGENT_TOKEN', auth_data['token'])
        except CommException:
            logging.exception("Communication error during enrollment")
            return False

    def report_status(self, task: str, state: State):
        if task in self.states:
            # Cosmetic patch to avoid stop_event to be reported as started after shutdown...
            if self.states[task] == self.State.stopped and state == self.State.started:
                return
            logging.info("[%s] : %s", task, state.name)
            self.states[task] = state

    # Launchers
    def setup(self) -> bool:
        """Launch all setup tasks"""
        if self._is_setup:
            return True
        for task in self.setup_tasks:
            func = getattr(self, "setup_{}".format(task))
            if func and callable(func):
                self.report_status(task, self.State.initializing)
                result = func()
                if not result:
                    self.report_status(task, self.State.initialization_failed)
                    return False
                else:
                    self.report_status(task, self.State.initialized)
        self._is_setup = True
        return True

    def start(self) -> bool:
        """Start all tasks"""
        if self._is_started:
            return True
        for task in self.start_tasks:
            func = getattr(self, "start_{}".format(task))
            if func and callable(func):
                self.report_status(task, self.State.starting)
                result = func()
                if not result:
                    self.report_status(task, self.State.startup_failed)
                    return False
                else:
                    self.report_status(task, self.State.started)
        self._is_started = True
        return True

    def shutdown(self) -> bool:
        """Stop all tasks"""
        result = True
        self._stopping = True
        for task in self.shutdown_tasks:
            func = getattr(self, "stop_{}".format(task))
            if func and callable(func):
                self.report_status(task, self.State.stopping)
                presult = func()
                if not presult:
                    self.report_status(task, self.State.shutdown_failed)
                else:
                    self.report_status(task, self.State.stopped)
                result &= presult
        return result
