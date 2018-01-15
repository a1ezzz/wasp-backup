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
from logging import getLogger

from wasp_general.command.command import WCommandSet, WCommandProto, WCommandPrioritizedSelector, WCommand
from wasp_general.command.result import WPlainCommandResult

from wasp_backup.file_backup import WFileBackupCommand
from wasp_backup.check import WCheckBackupCommand
from wasp_backup.program_backup import WProgramBackupCommand
from wasp_backup.retention import WRetentionBackupCommand


class WCommandHelp(WCommand):

	__help_info__ = '''This utility is able to create file or program backup, to check archive integrity and, \
and is able to rotate archives that resides locally or on a remote location.
Syntax: %s <main_command> [<command argument 1> <command argument 2> <command argument 3>...]

''' % sys.argv[0]

	def __init__(self, command_selector):
		WCommand.__init__(self, 'help')
		self.__command_selector = command_selector

	def _exec(self, *command_tokens, **command_env):
		result = self.__help_info__
		for command in self.__command_selector.commands():
			if isinstance(command, WCommandHelp) is True:
				continue
			result += 'Command "%s" is able to: %s\n' % (command.__command__, command.__description__)
			result += command.command_help()
			result += '\n\n'

		return WPlainCommandResult(result)


if __name__ == '__main__':

	logger = getLogger(os.path.basename(sys.argv[0]))

	command_set = WCommandSet(command_selector=WCommandPrioritizedSelector())
	command_set.commands().add_prioritized(WCommandHelp(command_set), 30)
	command_set.commands().add_prioritized(WFileBackupCommand(logger), 50)
	command_set.commands().add_prioritized(WProgramBackupCommand(logger), 50)
	command_set.commands().add_prioritized(WCheckBackupCommand(logger), 50)
	command_set.commands().add_prioritized(WRetentionBackupCommand(logger), 50)
	print(command_set.exec(WCommandProto.join_tokens(*(sys.argv[1:]))))
