# -*- coding: utf-8 -*-
# wasp_backup/file_backup.py
#
# Copyright (C) 2017 the wasp-backup authors and contributors
# <see AUTHORS file>
#
# This file is part of wasp-backup.
#
# wasp-backup is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wasp-backup is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with wasp-backup.  If not, see <http://www.gnu.org/licenses/>.

# TODO: document the code
# TODO: write tests for the code

# noinspection PyUnresolvedReferences
from wasp_backup.version import __author__, __version__, __credits__, __license__, __copyright__, __email__
# noinspection PyUnresolvedReferences
from wasp_backup.version import __status__

from wasp_general.command.enhanced import WCommandArgumentDescriptor

from wasp_backup.cipher import WBackupCipher
from wasp_backup.popen_archiver import WPopenArchiveCreator
from wasp_backup.command_common import __common_args__, WCreateBackupCommand


class WProgramBackupCommand(WCreateBackupCommand):

	__command__ = 'program-backup'
	__description__ = 'create backup archive of stdout of program'

	__arguments__ = (
		__common_args__['backup-archive'],
		WCommandArgumentDescriptor(
			'input-program', required=True, multiple_values=False, meta_var='program_command',
			help_info='program which output will be backed up'
		),
		__common_args__['compression'],
		__common_args__['password'],
		__common_args__['cipher_algorithm'],
		__common_args__['io-write-rate'],
		__common_args__['copy-to'],
		__common_args__['copy-fail'],
		__common_args__['notify-app']
	)

	def _exec(self, command_arguments, **command_env):
		compression_mode = None
		if 'compression' in command_arguments.keys():
			compression_mode = command_arguments['compression']

		cipher = None
		if 'password' in command_arguments:
			cipher = WBackupCipher(
				command_arguments['cipher_algorithm'], command_arguments['password']
			)

		io_write_rate = None
		if 'io-write-rate' in command_arguments.keys():
			io_write_rate = command_arguments['io-write-rate']

		backup_archive = command_arguments['backup-archive']
		archiver = WPopenArchiveCreator(
			command_arguments['input-program'], backup_archive, self.logger(),
			compression_mode=compression_mode, cipher=cipher, io_write_rate=io_write_rate,
			stop_event=self.stop_event()
		)
		self.set_archiver(archiver)
		return self._create_backup(command_arguments)
