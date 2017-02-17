"""
websocket.py : Remote shell

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
import sys
from code import InteractiveConsole
from contextlib import contextmanager
from io import StringIO
from typing import Optional

from socketIO_client import SocketIO, BaseNamespace

import epc.common.settings as settings
from epc.common.comm import req_sess, CommException


@contextmanager
def _std_redirector(stdin=sys.stdin, stdout=sys.stdin, stderr=sys.stderr):
    tmp_fds = stdin, stdout, stderr
    orig_fds = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = tmp_fds
    yield
    sys.stdin, sys.stdout, sys.stderr = orig_fds


class Interpreter(InteractiveConsole):
    def __init__(self, locals=None, filename="<console>"):
        super().__init__(locals, filename)

    def push(self, command):
        self.output = StringIO()
        more = None
        result = None
        with _std_redirector(stdout=self.output, stderr=self.output):
            try:
                more = InteractiveConsole.push(self, command)
                result = self.output.getvalue()
            except (SyntaxError, OverflowError):
                pass
            return more, result


interpreter = Interpreter()


class RemoteShellNamespace(BaseNamespace):
    """Shell interpreter (WS namespace)"""
    def __init__(self, io, path):
        super().__init__(io, path)
        self.stop_callback = None

    def on_cmd(self, *args):
        """Handle incomming commands"""
        print('on_cmd', args)
        if len(args) > 0:
            msg = args[0].get('msg')
            if msg:
                more, result = interpreter.push(msg)
                print(more, result)
                data = dict(msg=result, more=more)
                self.emit('cmd_rsp', data)
                print(data)

    def on_stop(self, *args):
        """Handle the stop event"""
        logging.info("Stopping the remote interpreter")
        if callable(self.stop_callback):
            self.stop_callback()


class RemoteShell(object):
    """Remote websocket shell"""
    def __init__(self):
        self.__client = None  # type: Optional[SocketIO]

    def start(self) -> bool:
        """Start the shell"""
        if self.__client:
            return False

        kwargs = dict()
        custom_cert = settings.Config().CA_CERTIFICATE
        if custom_cert:
            kwargs['verify'] = custom_cert

        proxies = settings.Config().PROXIES
        if proxies:
            kwargs['proxies'] = proxies

        kwargs['headers'] = {'Authorization': 'Bearer {}'.format(req_sess.auth.token)}
        try:
            url = req_sess.get_route('shell')
        except CommException:
            return False

        try:
            self.__client = SocketIO(url, **kwargs)
            self.__ns = self.__client.define(RemoteShellNamespace, '/shell')  # type: RemoteShellNamespace
            self.__ns.stop_callback = self.stop
            self.__client.wait()
            return True
        except:
            self.__client = None
            return False

    def stop(self) -> bool:
        """Stop the shell"""
        if not self.__client:
            return False
        self.__client.disconnect()
        return True
