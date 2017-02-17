"""
cache.py : Client-side cache

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

import os
from typing import List

import epc.common.settings as settings
from epc.common.utils import Singleton
import diskcache

CACHE_SETTINGS = dict(
    default_expiration=86400,
    eviction_policy="least-recently-stored",
    tag_index=True
)


class Cache(diskcache.Cache, metaclass=Singleton):
    """Cache Manager"""

    def __init__(self):
        os.makedirs(settings.Config().CACHE_DIR, exist_ok=True)
        super(Cache, self).__init__(
            settings.Config().CACHE_DIR,
            **CACHE_SETTINGS)

    def set(self, key, value, expire=None, read=False, tag=None):
        """Add a configurable default expiration"""
        if not expire:
            expire = CACHE_SETTINGS.get('default_expiration')
        return super(Cache, self).set(key, value, expire, read, tag)

    def get_tag(self, tag: str) -> List[str]:
        """Get all keys for a specific tag"""
        select = (
            'SELECT key FROM Cache WHERE tag = ?'
        )
        rows = self._sql(select, (tag,)).fetchall()
        return [x[0] for x in rows] if rows else []

    def list_tags(self) -> List[str]:
        """Utility function to list all tags in the cache"""
        select = (
            'SELECT DISTINCT tag FROM Cache'
        )
        rows = self._sql(select).fetchall()
        return [x[0] for x in rows] if rows else []
