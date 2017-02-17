"""
log.py : Android specific logging setup

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
import androidembed


class LogFile:
    """LogFile class used to pipe stdout/stderr to Android log"""
    def __init__(self):
        self.buffer = ''

    def write(self, s): 
        s = self.buffer + s 
        lines = s.split('\n')
        for l in lines[:-1]:
            androidembed.log(l)
        self.buffer = lines[-1]

    @staticmethod
    def flush():
        return
