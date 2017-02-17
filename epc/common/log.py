"""
log.py : Logging management

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
import logging.handlers
import os


class FileHandler(logging.FileHandler):
    """Custom handler to ensure the logging directory exists"""

    def __init__(self, filename, mode='a', encoding=None, delay=0):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, mode, encoding, delay)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom handler to ensure the logging directory exists"""

    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)


class TimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Custom handler to ensure the logging directory exists"""

    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False,
                 atTime=None):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime)
