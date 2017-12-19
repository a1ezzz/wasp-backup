#!/usr/bin/python3
# -*- coding: utf-8 -*-
# wasp-backup.py
#
# Copyright (C) 2016 the wasp-backup authors and contributors
# <see AUTHORS file>
#
# This file is part of wasp-backup.
#
# Wasp-backup is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Wasp-backup is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with wasp-backup.  If not, see <http://www.gnu.org/licenses/>.

# noinspection PyUnresolvedReferences
from wasp_backup.version import __author__, __version__, __credits__, __license__, __copyright__, __email__
# noinspection PyUnresolvedReferences
from wasp_backup.version import __status__

import sys
import os
import signal

from wasp_general.command.command import WCommandSet, WCommandProto

from wasp_launcher.bootstrap import WLauncherBootstrap
from wasp_launcher.core import WAppRegistry

from wasp_backup.create import WCreateBackupCommand
from wasp_backup.check import WCheckBackupCommand

import wasp_backup


if __name__ == '__main__':

	backup_app_config = os.path.join(os.path.dirname(wasp_backup.__file__), 'config', 'wasp-backup-cli.ini')
	os.environ['WASP_LAUNCHER_CONFIG_FILE'] = backup_app_config

	bootstrap = WLauncherBootstrap()
	bootstrap.load_configuration()

	command_set = WCommandSet()
	command_set.commands().add(WCreateBackupCommand())
	command_set.commands().add(WCheckBackupCommand())

	print(command_set.exec(WCommandProto.join_tokens(*(sys.argv[1:]))))

	def shutdown_signal(signum, frame):
		WAppRegistry.all_stop()

	signal.signal(signal.SIGTERM, shutdown_signal)
	signal.signal(signal.SIGINT, shutdown_signal)
