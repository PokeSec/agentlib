"""
command_Services.py : Run command line services for the Windows agent

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
import win32service
from pathlib import Path
from subprocess import Popen, PIPE
from zipfile import ZipFile, BadZipfile

import epc.common.settings as settings
import pywintypes
import win32serviceutil
import winerror
from win32com.shell import shell


def run() -> int:
    """Main function"""
    parser = argparse.ArgumentParser(description="Run command line services")
    subparsers = parser.add_subparsers(help='sub-command help', dest='command')

    subparsers.add_parser('install', help='Install help')  # type: argparse.ArgumentParser

    parser_update = subparsers.add_parser('update', help='Update help')  # type: argparse.ArgumentParser
    parser_update.add_argument('--package', help='Update package')

    parser_configure = subparsers.add_parser('configure', help='Configure help')  # type: argparse.ArgumentParser
    parser_configure.add_argument('--token', help='Client token')
    parser_configure.add_argument('--proxy', help='Client token', default='')

    try:
        args = parser.parse_args()
    except SystemExit:
        return -1

    if args.command == 'install':
        return run_installer(args)
    elif args.command == 'update':
        return run_updater(args)
    elif args.command == 'configure':
        return run_configure(args)
    return -1


def InstallService(pythonClassString,
                   serviceName,
                   displayName,
                   startType=None,
                   errorControl=None,
                   bRunInteractive=0,
                   serviceDeps=None,
                   userName=None,
                   password=None,
                   exeName=None,
                   exeArgs=None,
                   description=None):
    """
    Custom version of win32serviceutil.InstallService without unnecessary stuff
    """
    # Handle the default arguments.
    if startType is None:
        startType = win32service.SERVICE_DEMAND_START
    serviceType = win32service.SERVICE_WIN32_OWN_PROCESS
    if bRunInteractive:
        serviceType = serviceType | win32service.SERVICE_INTERACTIVE_PROCESS
    if errorControl is None:
        errorControl = win32service.SERVICE_ERROR_NORMAL

    exeName = '"%s"' % win32serviceutil.LocatePythonServiceExe(exeName)  # None here means use default PythonService.exe
    commandLine = win32serviceutil._GetCommandLine(exeName, exeArgs)
    hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    try:
        hs = win32service.CreateService(hscm,
                                        serviceName,
                                        displayName,
                                        win32service.SERVICE_ALL_ACCESS,
                                        serviceType,
                                        startType,
                                        errorControl,
                                        commandLine,
                                        None,
                                        0,
                                        serviceDeps,
                                        userName,
                                        password)
        if description is not None:
            try:
                win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_DESCRIPTION, description)
            except NotImplementedError:
                pass
        win32service.CloseServiceHandle(hs)
    finally:
        win32service.CloseServiceHandle(hscm)


def run_installer(args) -> int:
    """Install the program as a Windows Service"""
    if not shell.IsUserAnAdmin():
        print("You must have admin privileges to run this command")
        return 1

    try:
        InstallService(
            'EPControlSvc',
            settings.Config().SERVICE_NAME,
            settings.Config().SERVICE_DISPLAYNAME,
            startType=win32service.SERVICE_AUTO_START,
            errorControl=win32service.SERVICE_ERROR_NORMAL,
            bRunInteractive=False,
            exeName=settings.Config().SERVICE_EXE,
            description=settings.Config().SERVICE_DESCRIPTION)
    except win32service.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_EXISTS:
            print("Service is already installed")
            return 0
        else:
            print("Error installing service: %s (%d)" % (exc.strerror, exc.winerror))
    print("Service installed")
    return 0


def run_configure(args) -> int:
    """Set the token and the proxies in the configuration"""
    token = args.token.strip()
    proxy = args.proxy.strip()
    settings.Config().add_setting('INSTANCE_ID', token)
    settings.Config().add_setting('PROXIES', dict(http=proxy, https=proxy) if len(proxy) > 0 else None)
    return 0


WAIT_SEC = 30


def run_updater(args) -> int:
    """Launch the update process"""
    if not shell.IsUserAnAdmin():
        print("You must have admin privileges to run this command")
        return 1

    # Create the logger object to ensure logging is setup
    try:
        logging.config.dictConfig(settings.Config().LOGGER_CONF)
    except (ValueError, TypeError, AttributeError, ImportError):
        pass
    logger = logging.getLogger("updater")
    logger.info("Running updater")

    def start_service():
        """Launch the Windows service"""
        try:
            win32serviceutil.StartService(settings.Config().SERVICE_NAME)
            return True
        except Exception as exc:
            logger.debug("Cannot start service: %s", exc)
            return False

    package = Path(args.package)
    if not package.exists():
        logger.error("Package %s does not exists", args.package)
        return 1

    if package.suffix not in ['.zip', '.msi']:
        logger.error("Invalid package extension")
        return 1

    try:
        package.relative_to('.')
    except ValueError:
        logger.error("Package is not on the product directory")
        return 1

    logger.info("Stopping service")

    try:
        try:
            win32serviceutil.StopService(settings.Config().SERVICE_NAME)
        except pywintypes.error as exc:
            if exc.winerror != winerror.ERROR_SERVICE_NOT_ACTIVE:
                raise
            logger.debug("Service is not running")

        try:
            win32serviceutil.WaitForServiceStatus(
                settings.Config().SERVICE_NAME,
                win32service.SERVICE_STOPPED,
                WAIT_SEC)
        except pywintypes.error as exc:
            if exc.winerror != winerror.ERROR_SERVICE_REQUEST_TIMEOUT:
                raise
            logger.error("Service is not stopped after {}s".format(WAIT_SEC))
    except:
        pass

    logger.info("Service is stopped")

    if package.suffix == '.zip':
        try:
            with ZipFile(str(package.absolute())) as zfile:
                zfile.extractall()
        except (BadZipfile, RuntimeError):
            logger.error("Zip is invalid")
        finally:
            start_service()

    elif package.suffix == '.msi':
        with Popen([
            'msiexec',
            '/i', str(package.absolute()),
            '/quiet', '/qn', '/norestart'
        ],
                stdout=PIPE
        ) as proc:
            logger.info(proc.stdout.read())
            # MSI restart the service itself

    logger.info("Update process done")
    return 0
