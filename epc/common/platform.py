"""
platform.py : Get the platform data

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
import platform
from pathlib import Path
from epc import __version__
from epc.common.settings import Config
from epc.common.utils import Singleton


class PlatformData(metaclass=Singleton):
    """Basic OS informations"""
    def __init__(self, platform_name=Config().PLATFORM):
        self.__data = None
        self.__platform_name = platform_name

    def get_data(self, force=False) -> dict:
        """Get Platform data"""
        if not self.__data or force:
            plat = platform.uname()

            self.__data = dict()
            self.__data['instance'] = Config().INSTANCE_ID
            self.__data['token'] = Config().AGENT_TOKEN
            self.__data['os'] = self.__platform_name
            self.__data["version"] = __version__

            if self.__platform_name == 'win32':
                import win32api
                from ctypes import windll, byref, Structure, sizeof
                from ctypes.wintypes import DWORD, WCHAR, WORD, BYTE

                class OSVERSIONINFOEX(Structure):
                    _fields_ = [
                        ('dwOSVersionInfoSize', DWORD),
                        ('dwMajorVersion', DWORD),
                        ('dwMinorVersion', DWORD),
                        ('dwBuildNumber', DWORD),
                        ('dwPlatformId', DWORD),
                        ('szCSDVersion', WCHAR * 128),
                        ('wServicePackMajor', WORD),
                        ('wServicePackMinor', WORD),
                        ('wSuiteMask', WORD),
                        ('wProductType', BYTE),
                        ('wReserved', BYTE),
                    ]

                osvi = OSVERSIONINFOEX()
                osvi.dwOSVersionInfoSize = sizeof(OSVERSIONINFOEX)
                windll.kernel32.GetVersionExW(byref(osvi))

                self.__data['hostname'] = win32api.GetComputerNameEx(3)  # FQDN
                self.__data['osversion'] = plat.version
                self.__data['ostype'] = 'workstation' if osvi.wProductType == 1 else 'server'
                self.__data['arch'] = 'x64' if plat.machine == 'AMD64' else 'x86'

            elif self.__platform_name == 'unix':
                import ld
                linux_version = ld.info()
                self.__data['hostname'] = plat.node
                if linux_version['id']:
                    self.__data['osversion'] = '{}{}'.format(linux_version['id'], linux_version['version'])
                    self.__data['ostype'] = 'server'
                elif plat.system.lower() == 'darwin':
                    self.__data['osversion'] = 'osx'
                    server_plist = Path('/System/Library/CoreServices/SystemVersion.plist')
                    self.__data['ostype'] = 'server' if server_plist.exists() else 'workstation'
                else:
                    self.__data['osversion'] = 'unk_linux'
                    self.__data['ostype'] = 'server'
                self.__data['arch'] = 'x64' if plat.machine == 'x86_64' else 'x86'

            elif self.__platform_name == 'android':
                from epc.android.utils import get_device_info
                info = get_device_info()
                self.__data['hostname'] = info.imei if info.imei else info.android_id
                self.__data['osversion'] = info.android_version
                self.__data['ostype'] = 'mobile'
                self.__data['arch'] = plat.machine

        if Config().OS_TYPE is not None:
            self.__data['ostype'] = Config().OS_TYPE
        return self.__data
