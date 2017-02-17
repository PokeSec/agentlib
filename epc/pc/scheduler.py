"""
scheduler.py : Task scheduler

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
import multiprocessing
import multiprocessing.connection
import time
from multiprocessing import Process
from threading import Thread

import epc.common.scheduler
import epc.common.sentry
import epc.pc.worker as worker
import psutil
from epc.common.comm import req_sess
from epc.common.settings import Config


class Task(epc.common.scheduler.Task):
    """Task object"""

    def __init__(self, data):
        super(Task, self).__init__(data)
        self.stop_events = [multiprocessing.Event(), multiprocessing.Event()]
        self.app_handle = None
        self.exitcode = multiprocessing.Value('i', -1)

    def run(self, config: dict):
        """Run the task"""
        super(Task, self).run(config)
        self.data['kwargs']['__module'] = self.data['module']
        self.data['kwargs']['__stop'] = self.stop_events
        self.data['kwargs']['__auth_token'] = req_sess.auth.token
        self.data['kwargs']['config'] = config

        logging.info("Launching task {} | {}".format(self.data['module'], config))
        self.app_handle = multiprocessing.Process(
            target=worker.run,
            name=self.data['app'],
            args=(self.exitcode,),
            kwargs=self.data['kwargs'])
        self.app_handle.start()
        psprocess = psutil.Process(pid=self.app_handle.pid)
        if Config().PLATFORM == 'win32':
            psprocess.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            psprocess.ionice(1)  # Low
        else:
            psprocess.nice(5)
            try:
                psprocess.ionice(psutil.IOPRIO_CLASS_IDLE)
            except AttributeError:  # macOS does not have ionice, this is ok since it uses nice for IO priorities
                pass
        return self.app_handle

    def stop(self) -> bool:
        """Stop the task"""
        logging.info("Stopping task {}".format(self.data['module']))
        if not self.app_handle:
            return True

        if not self.is_running():
            return True

        self.stop_events[0].set()
        if not self.stop_events[1].wait(Config().WORKER_TERMINATE_GRACE):
            logging.warning("Graceful shutdown of task {} has failed".format(self.data['module']))

        if self.app_handle.is_alive():
            logging.info("App {} is alive, killing...".format(self.data['module']))
            self.app_handle.terminate()

        return True

    def is_running(self) -> bool:
        """Return if the task is running"""
        if not self.app_handle:
            return False

        return self.app_handle.is_alive()

    def __eq__(self, other):
        if isinstance(other, dict):
            ret = self.data['module'] == other.get('module')
            return ret
        else:
            return super(Task, self).__eq__(other)

    def __repr__(self):
        return '<Task {module}({args}{kwargs}) | running={is_running}>'.format(
            **self.data,
            is_running=self.is_running())


class Scheduler(epc.common.scheduler.Scheduler):
    """Schedule tasks"""
    _class_task = Task

    def __init__(self):
        super(Scheduler, self).__init__()
        self.__run = False
        self.__process_handles = dict()
        self.__wait_process_thread = None

    def __wait_process(self):
        while self.__run:
            if not self.__process_handles:
                time.sleep(0.5)
            waited_handles = multiprocessing.connection.wait(self.__process_handles.keys(), timeout=0.5)
            for handle in waited_handles:
                process = self.__process_handles.pop(handle)  # type: Process
                task = self.tasks.get(process.name)  # type: Task
                if task:
                    task.on_run_finished(task.exitcode.value)

    def run(self):
        """Run the scheduler"""
        self.__run = True

        self.__wait_process_thread = Thread(target=self.__wait_process)
        self.__wait_process_thread.start()

        while self.__run:
            try:
                handles = self._launch_tasks()
                self.__process_handles.update({h.sentinel: h for h in handles})
            except (KeyboardInterrupt, SystemExit):
                # Raise the standard exit conditions
                raise
            except:
                epc.common.sentry.client.captureException()
                logging.exception("Unknown exception in scheduler")
            time.sleep(self.poll_delay)

        self.__wait_process_thread.join()

    def stop(self):
        """Stop the scheduler"""
        self.__run = False
        return self._stop_tasks(self.tasks)
