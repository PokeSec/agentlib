"""
log_handler.py : Unix Log Handler

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
import sys
from logging import Handler
from logging.handlers import SysLogHandler
try:
    import systemd.daemon
    from systemd.journal import JournalHandler
    if systemd.daemon.booted():
        SYSTEMD = True
    else:
        SYSTEMD = False
except ImportError:
    SYSTEMD = False


class UnixLogHandler(Handler):
    """Dispatcher class used to return a correct log handler depending on the platform"""

    def emit(self, record):
        raise NotImplementedError()

    def __new__(cls, *args, **kwargs):
        if SYSTEMD:
            return JournalHandler(*args, **kwargs)
        else:
            if sys.platform.startswith('darwin'):
                kwargs['address'] = '/var/run/syslog'
            return SysLogHandler(*args, **kwargs)
