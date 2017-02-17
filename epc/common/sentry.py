"""
sentry.py : Sentry error reporting specific code

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
import raven
import epc.common.settings
import epc.common.platform

platform = epc.common.platform.PlatformData().get_data()
platform.pop('token', None)
client = raven.Client(epc.common.settings.Config().SENTRY_DSN)
client.tags_context(epc.common.platform.PlatformData().get_data())
