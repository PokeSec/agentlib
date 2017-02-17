"""
service.py : Handle Windows Service

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
from threading import Thread

if __name__ == '__main__':
    import sys
    import site

    sys.path = ['pylib', 'pylib\\lib-dynload', 'pytool']
    site.addsitedir('pytool')

import logging
import epc.common.settings as settings
from epc.pc.service import EPCService
import win32serviceutil
import win32service

class WindowsService(EPCService):
    """Windows specific EPCService"""
    @EPCService.os.getter
    def os(self):
        return 'win32'

    def start_scheduler(self):
        """Launch the scheduler as a thread"""
        self.stop_event = Thread(target=self.scheduler.run)
        self.stop_event.start()
        return True

    # StopEvent
    def start_stop_event(self):
        """Lock the program until the scheduler is stopped"""
        if self.stop_event:
            while self.stop_event.is_alive():
                self.stop_event.join()
            return True
        else:
            return False

    def set_stop_event(self):
        """Do nothng here (stop_event is set in start_scheduler)"""
        return True


class EPControlSvc(win32serviceutil.ServiceFramework):
    """Manages the Windows service"""
    _svc_name_ = settings.Config().SERVICE_NAME
    _svc_display_name_ = settings.Config().SERVICE_DISPLAYNAME

    def __init__(self, args):
        super().__init__(args)
        self.service = WindowsService()

    def _main(self):
        """Real entry point"""
        if self.service.setup():
            logging.debug("Setup complete")
            self.service.start()
        else:
            logging.error('Service startup fail')

    def SvcStop(self):
        """Handle the stop event"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            self.service.set_stop_event()
            logging.info('Stopping service ...')
            self.service.shutdown()
        except:
            logging.exception("Could not stop program")

    def SvcDoRun(self):
        """Run the service"""
        self._main()

if __name__ == '__main__':
    service = WindowsService()
    try:
        if service.setup():
            service.start()
            while True:
                pass
        else:
            logging.error('Service startup fail')
    except (KeyboardInterrupt, SystemExit):
        logging.info('Keyboard interrupt recieved!')
    except:
        logging.exception("Unexpected error")
        sys.exit(1)

    try:
        logging.info('Stopping service ...')
        service.set_stop_event()
        service.shutdown()
    except:
        logging.exception("Could not stop program")
        sys.exit(1)