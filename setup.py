"""
setup.py : Build script for agentlib

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
import sys
from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

OSNAME = None
if '--os' in sys.argv:
    index = sys.argv.index('--os')
    sys.argv.pop(index)
    OSNAME = sys.argv.pop(index)


def is_mobile(osname):
    """Tell if the os is a mobile one"""
    return osname in ['android', 'ios']


def get_packages():
    """Find_packages alternative"""
    packages = ['epc', 'epc.common', 'epc.common.data']
    if OSNAME:
        packages.append('epc.{}'.format(OSNAME))
        if not is_mobile(OSNAME):
            packages.append('epc.pc')
    return packages


def get_requirements():
    reqs = [
        'requests',
        'requests[socks]',
        'pycrypto',
        'diskcache',
        'psutil',
        'crontab',
        'arrow',
        'socketIO_client',
        'raven'
    ]
    if OSNAME == 'win32':
        reqs.append('pypiwin32')
    
    if OSNAME == 'android':
        reqs += ('six', 'pathtools', 'pyYAML', 'argh')

    if OSNAME == 'unix':
        reqs += ('ld', 'sh')

    return reqs

import epc
setup(

    name='agentlib',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=epc.__version__,

    description='AgentLib',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/PokeSec/agentlib',

    # Author details
    author='Jean-Baptiste Galet and Timothe Aeberhardt',
    author_email='epcontrol@jbgalet.fr',

    # Choose your license
    license='GNU General Public License v3 (GPLv3)',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.5',
    ],

    # What does your project relate to?
    keywords='epcontrol agentlib',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=get_packages(),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=get_requirements(),

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': [],
        'test': [],
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
    },
)
