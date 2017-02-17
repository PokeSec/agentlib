"""
comm.py : Communication APIs

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
import requests
import random

from epc import __version__
import epc.common.settings as settings


class EPSession(requests.Session):
    """Custom session to provide dynamic routing"""

    def __init__(self):
        super().__init__()
        self.__routes = None
        # Don't trust env for proxies
        self.trust_env = False
        # Add custom anchor
        custom_cert = settings.Config().CA_CERTIFICATE
        if custom_cert:
            self.verify = custom_cert

    def get_route(self, url: str) -> str:
        """Get a route for the specified URL or fragment"""
        if url == settings.Config().ROUTE_URL:
            return settings.Config().ROUTE_URL

        if self.__routes is None:
            req = self.get(settings.Config().ROUTE_URL)
            if req.status_code == 200:
                self.__routes = req.json()

        new_url = self.__routes.get(url) if self.__routes else None
        if not new_url:
            req = self.get(settings.Config().ROUTE_URL, params={'auth': True})
            if req.status_code == 200:
                self.__routes = req.json()
                new_url = self.__routes.get(url)

        if isinstance(new_url, list):
            new_url = random.choice(new_url)

        if not new_url:
            raise requests.exceptions.URLRequired()
        return new_url

    def prepare_request(self, request: requests.Request) -> requests.PreparedRequest:
        """
        Modify the request before sending it:
        * Get the appropriate URL during request preparation
        * Change the user-agent
        """
        if request.url.startswith('http'):
            url_parts = [request.url]
        else:
            url_parts = request.url.split('/')
        part1 = url_parts.pop(0)
        try:
            request.url = self.get_route(part1)
        except requests.RequestException:
            raise CommException("Cannot get route for {}".format(part1))
        if len(url_parts) > 0:
            request.url += '/' + '/'.join(url_parts)

        request.headers['User-Agent'] = 'EPControl/{} ({})'.format(__version__, settings.Config().PLATFORM)

        return super().prepare_request(request)

    def request(self,
                method,
                url,
                params=None,
                data=None,
                headers=None,
                cookies=None,
                files=None,
                auth=None,
                timeout=None,
                allow_redirects=True,
                proxies=None,
                hooks=None,
                stream=None,
                verify=None,
                cert=None,
                json=None) -> requests.Response:
        """
        Prepare the request before sending it:
        * Refuse any communication if INSTANCE_ID is not set
        * Set the proxies according to configuration
        """
        if not settings.Config().INSTANCE_ID:
            # Try to reload config
            settings.Config().reload()
            if not settings.Config().INSTANCE_ID:
                # We really don't have it :(
                raise CommException("No Instance ID...refusing communication")
        proxies = settings.Config().PROXIES

        return super(EPSession, self).request(
            method,
            url,
            params,
            data,
            headers,
            cookies,
            files,
            auth,
            timeout,
            allow_redirects,
            proxies,
            hooks,
            stream,
            verify,
            cert,
            json)


req_sess = EPSession()
CommException = requests.exceptions.RequestException
