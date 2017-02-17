"""
auth.py : Authentication routines

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
import requests.auth
from epc.common.comm import req_sess, CommException
import epc.common.settings as settings
from epc.common.platform import PlatformData


class EPCAuth(requests.auth.AuthBase):
    """Custom authentication class. Currently uses JWT"""
    def __init__(self, data):
        self.data = data
        self.token = None

    def authenticate(self):
        """Send the authentication request to the backend"""
        req = req_sess.post('auth', json=self.data)
        if req.ok:
            self.token = req.text
        return req.ok

    def response_hook(self, r, **kwargs):
        """Handle token renewal"""
        if r.status_code == 401:
            if not self.authenticate():
                return r
            # Consume content and release the original connection
            # to allow our new request to reuse the same one.
            r.content  # noqa
            r.raw.release_conn()
            request = r.request.copy()
            request.headers.update({'Authorization': 'Bearer {}'.format(self.token)})
            return r.connection.send(request, kwargs)
        return r

    def __call__(self, r):
        r.headers.update({'Authorization': 'Bearer {}'.format(self.token)})
        r.register_hook('response', self.response_hook)
        return r


def setup_auth(system_name: str) -> bool:
    """Setup the authentication module"""
    import warnings
    warnings.warn("setup_auth is deprecated, use common.service", DeprecationWarning)
    auth_data = PlatformData(system_name).get_data()
    try:
        req = req_sess.post('enroll', json=auth_data)
        if not req.ok:
            return False
        auth_data['token'] = req.text
        settings.Config().add_setting('AGENT_TOKEN', auth_data['token'])
    except CommException:
        return False

    req_sess.auth = EPCAuth(auth_data)
    return True
