"""
launch_worker.py : Launch a standalone worker

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
import site
import sys

sys.path = ['pylib', 'pylib\\lib-dynload', 'pytool']
site.addsitedir('pytool')

import json
import multiprocessing

from epc.common.auth import EPCAuth
from epc.common.platform import PlatformData
from epc.pc import worker


def main():
    mode = 'direct'
    # Set the multiprocessing settings
    multiprocessing.set_start_method('spawn')
    multiprocessing.freeze_support()

    # Authenticate
    authenticator = EPCAuth(PlatformData().get_data(force=True))
    if not authenticator.authenticate():
        print("Cannot authenticate")
        sys.exit(1)

    # Get the data
    # Format:
    # {
    #    "module": "dummy.dummy1",
    #    "config": {"LETTER": "X"}
    # }
    try:
        run_data = json.load(open(sys.argv[1]))
    except:
        print("Cannot load task data")
        sys.exit(1)

    # Prepare the worker
    stop_events = [multiprocessing.Event(), multiprocessing.Event()]
    data = dict(
        args=(),
        kwargs=dict()
    )
    data['kwargs']['__module'] = run_data['module']
    data['kwargs']['__stop'] = stop_events
    data['kwargs']['__auth_token'] = authenticator.token
    data['kwargs']['config'] = run_data.get('config')

    if mode == 'process':
        app_handle = multiprocessing.Process(
            target=worker.run,
            args=data['args'],
            kwargs=data['kwargs'])

        # Start the worker
        try:
            app_handle.start()
        except:
            import traceback
            traceback.print_exc()

        try:
            app_handle.join()
        except:
            pass
    else:
        worker.run(*data['args'], **data['kwargs'])

if __name__ == '__main__':
    main()
