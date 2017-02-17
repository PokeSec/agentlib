"""
utils.py : Python/JNI/Java utils

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
from collections import namedtuple

from jnius import autoclass, PythonJavaClass, java_method

EPCService = autoclass('io.epcontrol.EPCService')
Intent = autoclass('android.content.Intent')
OverlayActivity = autoclass('io.epcontrol.OverlayActivity')
String = autoclass("java.lang.String")

Context = autoclass('android.content.Context')
Secure = autoclass("android.provider.Settings$Secure")
Build = autoclass("android.os.Build")
VERSION = autoclass("android.os.Build$VERSION")


class PythonListIterator(PythonJavaClass):
    """PythonListIterator used to iterate over Java Lists"""
    __javainterfaces__ = ['java/util/ListIterator']

    def __init__(self, collection, index=0):
        super(PythonListIterator, self).__init__()
        self.collection = collection
        self.index = index

    def __iter__(self):
        return self

    # noinspection PyPep8Naming
    def hasNext(self):
        return self.index < self.collection.size() - 1

    @java_method('()Ljava/lang/Object;')
    def __next__(self):
        if not self.hasNext():
            raise StopIteration()
        obj = self.collection.get(self.index)
        self.index += 1
        return obj


def get_device_info() -> namedtuple:
    """Returns a namedtuple containing Android device information"""
    DeviceInfo = namedtuple('DeviceInfo',
                            ('android_version',
                             'security_patch',
                             'serial',
                             'imei',
                             'android_id'))

    android_version = VERSION.RELEASE
    try:
        security_patch = VERSION.SECURITY_PATCH
    except AttributeError:
        security_patch = None
    serial = Build.SERIAL
    imei = EPCService.mService.getSystemService(Context.TELEPHONY_SERVICE).getDeviceId()
    android_id = Secure.getString(EPCService.mService.getContentResolver(), Secure.ANDROID_ID)
    return DeviceInfo(
        android_version,
        security_patch,
        serial,
        imei,
        android_id)


def show_alert(reason):
    """Display an alert in the app"""
    intent = Intent(EPCService.mService, OverlayActivity)
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    intent.putExtra(String("reason"), String(reason))
    EPCService.mService.startActivity(intent)
