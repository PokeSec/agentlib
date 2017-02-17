"""
service.py : Main module for Android service

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
import locale
import sys
from epc.android.log import LogFile
# Print stdout to Android logs
sys.stdout = sys.stderr = LogFile()
# Patch sys to include argv
setattr(sys, 'argv', [])

import jnius
import logging.config

from epc.common.importer import setup_importer
from epc.common.service import EPCService
from epc.common.settings import Config
from epc.android.scheduler import AndroidScheduler
from epc.common.utils import Singleton


# Force import of encodings modules to workaround bug when using EPCMetaFinder
import encodings.idna
import encodings.hex_codec

# Set the locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')


# Pyjnius classes for Scheduling with FJD
jEPCService = jnius.autoclass("io.epcontrol.EPCService")
EPCJobService = jnius.autoclass("io.epcontrol.EPCJobService")
GooglePlayDriver = jnius.autoclass("com.firebase.jobdispatcher.GooglePlayDriver")
FirebaseJobDispatcher = jnius.autoclass("com.firebase.jobdispatcher.FirebaseJobDispatcher")
Trigger = jnius.autoclass("com.firebase.jobdispatcher.Trigger")
Constraint = jnius.autoclass("com.firebase.jobdispatcher.Constraint")
RetryStrategy = jnius.autoclass("com.firebase.jobdispatcher.RetryStrategy")
Lifetime = jnius.autoclass("com.firebase.jobdispatcher.Lifetime")

try:
    jnius.reflect.Class.forName("com.google.firebase.iid.FirebaseInstanceId")
    FirebaseInstanceId = jnius.autoclass("com.google.firebase.iid.FirebaseInstanceId")
except jnius.JavaException:
    FirebaseInstanceId = None

# Needed so that jnius can find NativeInvocationHandler from threads
jnius.autoclass('org.jnius.NativeInvocationHandler')


class AndroidService(EPCService, metaclass=Singleton):
    """Android Service"""
    def __init__(self):
        super(AndroidService, self).__init__()
        driver = GooglePlayDriver(jEPCService.mService)
        self.__dispatcher = FirebaseJobDispatcher(driver)
        self.__job = self.__dispatcher.newJobBuilder() \
            .setService(EPCJobService) \
            .setTag("EPCService-poll") \
            .setTrigger(Trigger.executionWindow(Config().TASK_POLL, 2 * Config().TASK_POLL)) \
            .setLifetime(Lifetime.FOREVER) \
            .addConstraint(Constraint.ON_ANY_NETWORK) \
            .setRecurring(True) \
            .setReplaceCurrent(True) \
            .setRetryStrategy(RetryStrategy.DEFAULT_LINEAR) \
            .build()
        self.__dispatcher.schedule(self.__job)
        self.scheduler_class = AndroidScheduler
        if FirebaseInstanceId:
            self.firebase_token = FirebaseInstanceId.getInstance().getToken()
        else:
            self.firebase_token = None
        self.firebase_token_synced = False

    def __del__(self):
        self.__dispatcher.cancelAll()

    @EPCService.os.getter
    def os(self):
        return 'android'

    def setup_scheduler(self) -> bool:
        if not setup_importer():
            return False
        self.post_firebase_token()
        return super(AndroidService, self).setup_scheduler()

    def post_firebase_token(self):
        """Send the firebase token to the backend"""
        if not self.firebase_token_synced:
            try:
                # Lazy import DataClient to try and post the Firebase token
                from epc.common.data import DataClient
                report_mode = 'report_state'
                if not DataClient().send(report_mode, 'token', {'token': self.firebase_token}):
                    logging.error("Could not send IOCScan state")
                DataClient().flush(report_mode)
                logging.debug("Firebase token synced : %s", self.firebase_token)
                self.firebase_token_synced = True
            except:
                pass

    def on_action(self, action=None, data_string=None):
        """Application intents"""
        logging.debug("In service, on_action(%s, %s)", action, data_string)
        try:
            Config().reload()
            if action == "UpdateToken":
                if FirebaseInstanceId:
                    self.firebase_token = FirebaseInstanceId.getInstance().getToken()
                self.firebase_token_synced = False
            if self.setup():
                if self.start():
                    self.post_firebase_token()
                    self.scheduler.on_action(action, data_string)
        except Exception:
            logging.exception("Exception caught while calling scheduler.on_action()")
        finally:
            if action == "EPCJobService":
                EPCJobService.mService.jobFinished(self.__job, True)

service = None  # type: AndroidService


def main():
    """Entry point"""
    global service
    service = AndroidService()
    service.on_action()
