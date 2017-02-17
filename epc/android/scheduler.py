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
import importlib
import logging
import threading
import json
from typing import Optional, Any, Tuple

import jnius
import epc.common.sentry
from epc.common.scheduler import Task, Scheduler

EPCService = jnius.autoclass("io.epcontrol.EPCService")
EPCJobService = jnius.autoclass("io.epcontrol.EPCJobService")
GooglePlayDriver = jnius.autoclass("com.firebase.jobdispatcher.GooglePlayDriver")
FirebaseJobDispatcher = jnius.autoclass("com.firebase.jobdispatcher.FirebaseJobDispatcher")
Trigger = jnius.autoclass("com.firebase.jobdispatcher.Trigger")
Constraint = jnius.autoclass("com.firebase.jobdispatcher.Constraint")
RetryStrategy = jnius.autoclass("com.firebase.jobdispatcher.RetryStrategy")
Lifetime = jnius.autoclass("com.firebase.jobdispatcher.Lifetime")

# Pyjnius classes for Device Administration
EPCDeviceAdminReceiver = jnius.autoclass("io.epcontrol.EPCDeviceAdminReceiver")
Context = jnius.autoclass('android.content.Context')
Intent = jnius.autoclass('android.content.Intent')
ComponentName = jnius.autoclass('android.content.ComponentName')

# Pyjnius classes for Permissions checking
ContextCompat = jnius.autoclass('android.support.v4.content.ContextCompat')
PackageManager = jnius.autoclass('android.content.pm.PackageManager')
PackageInfo = jnius.autoclass('android.content.pm.PackageInfo')

# Pyjnius classes for Notifications
PendingIntent = jnius.autoclass('android.app.PendingIntent')
NotificationBuilder = jnius.autoclass('android.support.v4.app.NotificationCompat$Builder')
drawable = jnius.autoclass('io.epcontrol.R$drawable')
String = jnius.autoclass("java.lang.String")
MainActivity = jnius.autoclass("io.epcontrol.MainActivity")
NOTIFICATION_ID = 0


class AndroidTask(Task):
    """Task object"""

    def __init__(self, data):
        super(AndroidTask, self).__init__(data)
        self.app = None
        self.__thread = None  # type: Optional[threading.Thread]

    def run(self, config: dict) -> Tuple[Task, Optional[threading.Thread]]:
        """Run the task"""
        super(AndroidTask, self).run(config)
        logging.info("Launching task {} | {}".format(self.data['module'], self.data))
        try:
            module = importlib.import_module('apps.{}'.format(self.data['module']))
            self.app = module.APPCLASS(platform='android')
            self.app.logger = logging
            self.data['kwargs']['config'] = config
            self.__thread = self.app.run(args=self.data['args'], kwargs=self.data['kwargs'])
            return self, self.__thread
        except ImportError:
            epc.common.sentry.client.captureException()
            logging.exception("Exception caught while running task")
            self.app = None
            return self, None

    def stop(self) -> bool:
        """Stop the task"""
        logging.info("Stopping task {}".format(self.data))
        if not self.app:
            return False

        if not self.is_running():
            return False

        self.app.stop()
        return True

    def is_running(self) -> bool:
        """Return if the task is running"""
        if not self.app:
            return False

        return self.app.is_running

    def __repr__(self):
        return '<AndroidTask {module}({args}{kwargs}) | {is_running}>'.format(
            **self.data,
            is_running=self.is_running())


class AndroidScheduler(Scheduler):
    """
    Application scheduling singleton class, using Firebase Job Dispatcher to regularly fetch apps to start/stop
    Implements a callback registration feature, dispatching received "actions" (Broadcast events for instance) to apps
    """
    _class_task = AndroidTask

    def __init__(self):
        """Initialize scheduler using Firebase Job Dispatcher"""
        super(AndroidScheduler, self).__init__()
        self.__action_callbacks = {}
        self.__action_callbacks_lock = threading.Lock()
        self.__tasks_lock = threading.Lock()

    def __is_all_permissions_ok(self) -> bool:
        """Returns True if app is Device Admin and all permissions are set"""
        return self.__is_device_admin() and self.__is_permissions_ok()

    @staticmethod
    def __is_device_admin() -> bool:
        """Check that the application is a Device Administrator or ask for the permission"""
        # noinspection PyPep8Naming
        DevicePolicyManager = EPCService.mService.getSystemService(Context.DEVICE_POLICY_SERVICE)
        device_admin_component_name = ComponentName(EPCService.mService, EPCDeviceAdminReceiver)
        return DevicePolicyManager.isAdminActive(device_admin_component_name)

    @staticmethod
    def __is_permissions_ok() -> bool:
        """Check that the application has all needed permissions or ask for them"""
        pm = EPCService.mService.getPackageManager()
        info = pm.getPackageInfo(EPCService.mService.getPackageName(), PackageManager.GET_PERMISSIONS)
        for perm in info.requestedPermissions:
            if ContextCompat.checkSelfPermission(EPCService.mService, perm) != PackageManager.PERMISSION_GRANTED:
                return False
        return True

    def __check_permissions(self) -> bool:
        """Show a notification if some permissions are missing"""
        notification_service = EPCService.mService.getSystemService(Context.NOTIFICATION_SERVICE)

        if not self.__is_all_permissions_ok():
            logging.warning("Missing permissions, showing notification to user")

            notification_builder = NotificationBuilder(EPCService.mService)
            notification_intent = Intent(EPCService.mService, MainActivity)
            notification_intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            intent = PendingIntent.getActivity(EPCService.mService, 0, notification_intent, 0)

            notification_builder.setSmallIcon(getattr(drawable, "ic_stat_logo"))
            notification_builder.setContentTitle(String("Missing mandatory permissions"))
            notification_builder.setContentText(String("Please open the EPControl app to fix missing permissions"))
            notification_builder.setContentIntent(intent)
            notification_builder.setAutoCancel(False)
            notification_builder.setOngoing(True)

            notification_service.notify(NOTIFICATION_ID, notification_builder.build())

            return False

        else:
            notification_service.cancel(NOTIFICATION_ID)
            return True

    def run(self):
        return

    def stop(self):
        logging.info("Stopping running tasks")
        return self._stop_tasks(self.tasks)

    def _launch_tasks(self):
        """Overridden to join() running threads"""
        threads = super(AndroidScheduler, self)._launch_tasks()

        while threads:
            cur_threads = threads
            for task, thread in cur_threads:
                ret = thread.join(timeout=1)
                if ret is not None:  # Only stop task when its thread's _run() target has returned
                    task.stop()
                    task.on_run_finished(ret)
                    threads.remove((task, thread))
        logging.info("All tasks done")

    def on_action(self, action=None, data_string=None):
        """Dispatch received Android actions"""
        logging.debug("Received action : %s", action)

        if self.__check_permissions():
            if action in ("EPCJobService", "ForceRefreshTasks"):
                self._launch_tasks()
            elif action == "FCMMessage":
                try:
                    data = json.loads(data_string)
                    if data["type"] == "refresh":
                        self._launch_tasks()
                except json.JSONDecodeError:
                    logging.warning("FCMMessage data not in JSON format : %s", data_string)
                except KeyError:
                    logging.warning("Malformed pushed data")
            elif action in self.__action_callbacks:
                    for callback in self.__action_callbacks[action]:
                        callback(action=action, data=data_string)
        else:
            logging.warning("Permissions missing, refusing to execute action")

    def register_action(self, action, callback):
        """Register an app callback for an action"""
        logging.debug("Registering action %s with callback %s", action, callback)
        with self.__action_callbacks_lock:
            try:
                self.__action_callbacks[action].add(callback)
            except KeyError:
                self.__action_callbacks[action] = {callback}

    def unregister_action(self, action, callback):
        """Unregister an app callback for an action"""
        with self.__action_callbacks_lock:
            try:
                self.__action_callbacks[action].remove(callback)
            except (KeyError, ValueError):
                logging.warning("Unregister callback {} failed for action {}".format(callback, action))
