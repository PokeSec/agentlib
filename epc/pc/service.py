"""
service.py : PC Agent Service

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
import multiprocessing

import epc.common.service
from epc.common import settings
from epc.pc.scheduler import Scheduler


class EPCService(epc.common.service.EPCService):
    """Subclass of EPCService for MultiProcess-able OSes"""
    def __init__(self):
        super(EPCService, self).__init__()
        multiprocessing.set_executable(settings.Config().SERVICE_EXE)
        multiprocessing.set_start_method('spawn')
        multiprocessing.freeze_support()
        self.scheduler_class = Scheduler
