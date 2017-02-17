"""
command_services.py : Run command line services for the Linux agent

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
import argparse
import logging
import logging.config
import os
import zipfile
from pathlib import Path

import epc.common.settings as settings
import sh


def run() -> int:
    """Main function"""
    parser = argparse.ArgumentParser(description="Run command line services")
    subparsers = parser.add_subparsers(help='sub-command help', dest='command')

    parser_update = subparsers.add_parser('update', help='Update help')  # type: argparse.ArgumentParser
    parser_update.add_argument('--package', help='Update package')

    parser_configure = subparsers.add_parser('configure', help='Configure help')  # type: argparse.ArgumentParser
    parser_configure.add_argument('--token', help='Client token')
    parser_configure.add_argument('--proxy', help='Client token', default='')

    try:
        args = parser.parse_args()
    except SystemExit:
        return -1

    if not os.getuid() == 0:
        print("You must be root to run this command")
        return -1

    if args.command == 'configure':
        return run_configure(args)
    elif args.command == 'update':
        return run_updater(args)
    return -1


def run_configure(args) -> int:
    token = args.token.strip()
    proxy = args.proxy.strip()
    settings.Config().add_setting('INSTANCE_ID', token)
    settings.Config().add_setting('PROXIES', dict(http=proxy, https=proxy) if len(proxy) > 0 else None)
    return 0


WAIT_SEC = 1
PLIST_PATH = '/Library/LaunchDaemons/io.epcontrol.plist'


def run_updater(args) -> int:
    """Launch the update process"""
    # Create the logger object to ensure logging is setup
    try:
        logging.config.dictConfig(settings.Config().LOGGER_CONF)
    except (ValueError, TypeError, AttributeError, ImportError):
        pass
    logger = logging.getLogger("updater")
    logger.info("Running updater")

    def start_service():
        """Start the unix service"""
        try:
            if Path('/sbin/initctl').exists() and 'upstart' in sh.Command('/sbin/initctl')('version'):  # using upstart
                logger.info(sh.Command('/usr/sbin/service')('epcontrol', 'start'))
            elif Path('/sbin/systemctl').exists():                                                      # using systemd
                logger.info(sh.Command('/usr/sbin/systemctl')('start', 'epcontrol'))
            elif Path('/etc/init.d/epcontrol').exists():                                               # using init.d
                logger.info(sh.Command('/etc/init.d/epcontrol')('start'))
            elif Path('/bin/launchctl').exists() and Path(PLIST_PATH).exists():                         # MacOSX
                logger.info(sh.Command('/bin/launchctl')('load', PLIST_PATH))
            else:
                raise RuntimeError("Could not find a way to start the service")
            return True
        except (sh.SignalException, sh.TimeoutException, sh.ErrorReturnCode, RuntimeError):
            logger.exception("Cannot start service")
            return False

    package = Path(args.package)
    if not package.exists():
        logger.error("Package %s does not exists", args.package)
        return 1

    if package.suffix not in ['.zip']:
        logger.error("Invalid package extension")
        return 1

    try:
        package.relative_to('.')
    except ValueError:
        logger.error("Package is not on the product directory")
        return 1

    logger.info("Stopping service")

    try:
        if Path('/sbin/initctl').exists() and 'upstart' in sh.Command('/sbin/initctl')('version'):  # using upstart
            logger.info(sh.Command('/usr/sbin/service')('epcontrol', 'stop', _timeout=WAIT_SEC))
        elif Path('/sbin/systemctl').exists():                                                      # using systemd
            logger.info(sh.Command('/usr/sbin/systemctl')('stop', 'epcontrol', _timeout=WAIT_SEC))
        elif Path('/etc/init.d/epcontrol').exists():                                               # using init.d
            logger.info(sh.Command('/etc/init.d/epcontrol')('stop', _timeout=WAIT_SEC))
        elif Path('/bin/launchctl').exists() and Path(PLIST_PATH).exists():                         # MacOSX
            logger.info(sh.Command('/bin/launchctl')('unload', PLIST_PATH))
        else:
            raise RuntimeError("Could not find a way to stop the service")
    except (sh.SignalException, sh.TimeoutException, sh.ErrorReturnCode, RuntimeError):
        logger.exception("Cannot stop service")
        return 1

    logger.info("Service is stopped")

    if package.suffix == '.zip':
        try:
            with zipfile.ZipFile(str(package.absolute())) as zfile:
                zfile.extractall()
        except (zipfile.BadZipfile, RuntimeError):
            logger.error("Zip is invalid")
        finally:
            start_service()
    logger.info("Update process done")
    return 0
