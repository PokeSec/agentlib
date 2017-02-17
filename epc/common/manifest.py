"""
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

import array
import struct
import zlib
from enum import Enum

from epc.common.kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


class Manifest(KaitaiStruct):
    def __init__(self, _io, _parent=None, _root=None):
        super().__init__(_io)
        self._parent = _parent
        self._root = _root if _root else self
        self.header = self._root.ManifestHeader(self._io, self, self._root)
        self.manifests = [None] * (self.header.count)
        for i in range(self.header.count):
            self.manifests[i] = self._root.ManifestBody(self._io, self, self._root)


    class ManifestHeader(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super().__init__(_io)
            self._parent = _parent
            self._root = _root if _root else self
            self.magic = self._io.ensure_fixed_contents(8, struct.pack('8b', 83, 79, 78, 69, 77, 65, 78, 73))
            self.count = self._io.read_u2le()


    class ManifestBody(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super().__init__(_io)
            self._parent = _parent
            self._root = _root if _root else self
            self.version = self._io.read_u1()
            self.signature_type = self._io.read_u1()
            self.mod_count = self._io.read_u2le()
            self.timestamp = self._io.read_u8le()
            self.signature = self._io.read_bytes(512)
            self.modules = [None] * (self.mod_count)
            for i in range(self.mod_count):
                self.modules[i] = self._root.Module(self._io, self, self._root)



    class Module(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super().__init__(_io)
            self._parent = _parent
            self._root = _root if _root else self
            self.name_hash = self._io.read_bytes(32)
            self.flags = self._io.read_u1()
            self.key = self._io.read_bytes(32)
            self.code_hash = self._io.read_bytes(32)



