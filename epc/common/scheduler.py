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
import logging.config
import time
from abc import ABCMeta, abstractmethod
from datetime import timedelta
from threading import Thread
from typing import Dict, Optional
from typing import Tuple

import arrow
import crontab

from epc.common.shell import RemoteShell
from epc.common.cache import Cache
from epc.common.comm import req_sess, CommException
from epc.common.settings import Config

# Internal values from crontab to allow inheritance
from pathlib import Path

MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
WEEK = timedelta(days=7)
MONTH = timedelta(days=28)
YEAR = timedelta(days=365)

PERIODS = dict(
    daily=DAY,
    weekly=WEEK,
    monthly=MONTH
)


def _month_incr(dt, m) -> timedelta:
    odt = dt
    dt += MONTH
    while dt.month == odt.month:
        dt += DAY
    # get to the first of next month, let the backtracking handle it
    dt = dt.replace(day=1)
    return dt - odt


def _year_incr(dt, m) -> timedelta:
    # simple leapyear stuff works for 1970-2099 :)
    mod = dt.year % 4
    if mod == 0 and (dt.month, dt.day) < (2, 29):
        return YEAR + DAY
    if mod == 3 and (dt.month, dt.day) > (2, 29):
        return YEAR + DAY
    return YEAR


_increments = [
    lambda *a: MINUTE,
    lambda *a: HOUR,
    lambda *a: DAY,
    _month_incr,
    lambda *a: DAY,
    _year_incr,
    lambda dt, x: dt.replace(minute=0),
    lambda dt, x: dt.replace(hour=0),
    lambda dt, x: dt.replace(day=1) if x > DAY else dt,
    lambda dt, x: dt.replace(month=1) if x > DAY else dt,
    lambda dt, x: dt,
]


class Crontab(crontab.CronTab):
    def __init__(self, cron, run_asap=False):
        super().__init__(cron)
        self.__asap = run_asap

    def next(self, now=None, increments=_increments, delta=True, default_utc=None) -> arrow.Arrow:
        """Get the next run of crontab"""
        if self.__asap:
            # Force the first run
            self.__asap = False
            return now
        now = arrow.get(now).datetime
        future = now.replace(second=0, microsecond=0) + increments[0]()
        to_test = 5
        while to_test >= 0:
            if not self._test_match(to_test, future):
                inc = increments[to_test](future, self.matchers)
                future += inc
                for i in range(0, to_test):
                    future = increments[6 + i](future, inc)
                to_test = 5
                continue
            to_test -= 1
        return arrow.get(future)


class Task(metaclass=ABCMeta):
    """Base class for tasks"""

    def __init__(self, data):
        self.data = dict()
        self.__cur_config = None
        self.update(data)

    def get_key(self, data=None) -> str:
        """Get a key for dict"""
        if not data:
            data = self.data
        return '{module}'.format(**data)

    def run(self, config: dict):
        """Run the task"""
        self.__cur_config = config

    @abstractmethod
    def stop(self):
        """Stop the task"""
        ...

    @abstractmethod
    def is_running(self):
        """Return if the task is running"""
        ...

    def update(self, data):
        """Update the task configuration"""
        data.setdefault('args', ())
        data.setdefault('kwargs', {})
        self.data.update(data)

    def on_run_finished(self, exitcode: int):
        logging.info("Task %s finished with code [%d]", self.data['app'], exitcode)
        if exitcode != 0:
            return

        if self.__cur_config and self.__cur_config.get('task_id'):
            Cache().set('task_lastrun_{task_id}'.format(**self.__cur_config), arrow.utcnow().timestamp, tag='scheduler')

    def get_last_run(self, config: dict, default=None):
        if not config.get('task_id'):
            return default

        last_run = Cache().get('task_lastrun_{task_id}'.format(**config))
        if not last_run:
            return default

        return last_run

    def must_stop(self) -> bool:
        """Tell if the task _MUST_ stop"""
        if not self.is_running():
            return False
        # if not self.stoppable:
        #    return False
        return True

    def can_start(self, config: dict) -> bool:
        """Tell if the task _CAN_ start"""
        if self.is_running():
            return False

        # Check schedule
        schedule = config.get('_schedule')

        # Tasks with no specific schedule run immediately
        if not schedule or schedule.get('type') == 'force':
            return True
        elif schedule.get('type') == 'runonce' and not self.get_last_run(config):
            return True
        else:
            now = arrow.utcnow()
            if schedule.get('type') == 'crontab':
                crontab = Crontab(schedule.get('value1'), bool(schedule.get('value2', False)))
                next = crontab.next(arrow.get(self.get_last_run(config, arrow.utcnow().timestamp)))
                if now < next:
                    return False
                return True
            elif schedule.get('type') == 'planned':
                run = True
                start_date = schedule.get('value1')
                end_date = schedule.get('value2')
                if start_date and arrow.get(start_date) > now:
                    run = False
                if end_date and arrow.get(end_date) < now:
                    run = False
                if not start_date and not end_date:
                    run = False
                return run
            elif schedule.get('type') == 'period':
                period = schedule.get('value1')
                if not period:
                    return False
                delta = PERIODS.get(period)
                if not delta:
                    return False
                if not self.get_last_run(config):
                    return True
                return arrow.get(self.get_last_run(config)) + delta < now
        return False

    def status_report(self) -> dict:
        return dict(
            status=self.is_running(),
            last_run={config.get('task_id'): self.get_last_run(config) for config in self.data['configs']}
        )

    def get_active_config(self) -> Optional[dict]:
        for config in self.data['configs']:  # type: dict
            if self.can_start(config):
                return {k: v for k, v in config.items() if not k.startswith('_')}
        return None


class Scheduler(metaclass=ABCMeta):
    """Schedule tasks"""
    _class_task = Task

    def __init__(self):
        self.poll_delay = Config().TASK_POLL
        self.tasks = dict()  # type: Dict[str, Task]
        self.to_notify = []
        self.remote_shell = RemoteShell()
        self.remote_shell_thread = None

    @abstractmethod
    def run(self):
        """Run the scheduler"""
        ...

    @abstractmethod
    def stop(self):
        """Stop the scheduler"""
        ...

    # Response handlers
    def handle_rsp_poll_delay(self, value):
        """Change the poll delay"""
        self.poll_delay = value if value else Config().TASK_POLL

    def handle_rsp_logger_config(self, value):
        """Change the logger configuration"""
        if value:
            try:
                logging.config.dictConfig(value)
            except (ValueError, TypeError, AttributeError, ImportError):
                logging.error("Cannot update config")

    def __create_tasks(self, data: dict):
        # Create the tasks objects
        for app_name, active_item in data.items():
            if not app_name in self.tasks:
                self.tasks[app_name] = self._class_task(active_item)
            else:
                self.tasks[app_name].update(active_item)

    def handle_rsp_active(self, value):
        """Activate tasks"""
        # Put the recieved data in cache
        Cache().set('tasks', value, tag='scheduler')
        self.__create_tasks(value)

    def handle_rsp_stop(self, value):
        """Stop tasks"""
        self.stopped_tasks = dict()
        if value:
            for stop_item in value:  # type: str
                # Remove from active tasks
                task = self.tasks.pop(stop_item, None)  # type: Task
                if task:
                    self.stopped_tasks[stop_item] = task

                # Remove from cached tasks
                cache_tasks = Cache().get('tasks')  # type: dict
                task = cache_tasks.pop(stop_item, None)
                if task:
                    Cache().set('tasks', cache_tasks, tag='scheduler')

    def handle_rsp_shell(self, value):
        """Launch the Remote shell websocket listener"""
        if value:
            if not self.remote_shell_thread:
                logging.info("Remote shell enabled")
                self.remote_shell_thread = Thread(target=self.remote_shell.start)
                self.remote_shell_thread.start()
        else:
            if self.remote_shell_thread:
                logging.info("Remote shell disabled")
                self.remote_shell.stop()
                self.remote_shell_thread.join(1)
                self.remote_shell_thread = None

    def handle_rsp_preview_upload(self, value):
        """Temporary task during preview to grab files"""
        # For obvious ethics reason, we only grab files under the program directory
        base = Path('.')
        path = base / value
        try:
            path = path.relative_to(base)
        except ValueError:
            return

        if path.exists():
            try:
                with path.open('rb') as ifile:
                    req_sess.post('debug', data=ifile)
            except CommException:
                return

    def handle_rsp_preview_download(self, value):
        base = Path('.')
        path = base / value['path']
        try:
            path = path.relative_to(base)
        except ValueError:
            return

        try:
            req = req_sess.get('debug/{}'.format(value['key']))
            if req.status_code == 200:
                path.write_bytes(req.content)
        except:
            return

    def handle_rsp_preview_run_command(self, value):
        if Config().PLATFORM == 'android':
            return  # Unsupported on Android
        import subprocess
        try:
            subprocess.run(value)
        except:
            return

    def handle_rsp_preview_cleancache(self, value):
        try:
            Cache().evict(value)
        except:
            return

    def fetch(self) -> Tuple[dict, dict]:
        """Get tasks to activate and stop from the server (if available)"""
        status_report = {k: v.status_report() for k, v in self.tasks.items()}
        try:
            req = req_sess.post('task', json=status_report)
            rsp = req.json() if req.status_code == 200 else {}
        except CommException as comm_exc:
            logging.warning("Could not poll tasks from server : %s", comm_exc)
            cache_tasks = Cache().get('tasks')  # type: dict
            self.__create_tasks(cache_tasks)
            return self.tasks, dict()

        # On debug, allow to start arbitrary tasks from local fetch.json
        if Config().DEBUG:
            try:
                import json
                rsp = json.load(open('fetch.json', 'r'))
            except:
                pass

        for key, val in rsp.items():
            func = getattr(self, 'handle_rsp_{}'.format(key), None)
            if callable(func):
                func(val)

        return self.tasks, self.stopped_tasks

    def _stop_tasks(self, tasks):
        for _ in range(Config().STOP_TRIES):
            run_count = 0
            for task in tasks.values():
                if task.is_running():
                    run_count += 1
                    task.stop()
            if run_count == 0:
                return True
            time.sleep(1)
        return False

    def _launch_tasks(self) -> list:
        logging.debug("Scheduler running")

        for item in self.to_notify:
            notifier = getattr(item, 'notify', None)
            if callable(notifier):
                notifier()

        task_handles = []
        active_tasks, stopped_tasks = self.fetch()

        # First step: stop old tasks
        if not self._stop_tasks(stopped_tasks):
            logging.error("Could not stop tasks")

        # Second step: launch the tasks
        for task in active_tasks.values():
            task_config = task.get_active_config()
            if task_config:
                tmp = task.run(task_config)
                if tmp:
                    task_handles.append(tmp)
        return task_handles
