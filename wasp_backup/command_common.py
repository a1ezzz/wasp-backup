# -*- coding: utf-8 -*-
# wasp_backup/command_common.py
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

import os
import sys
import tempfile

from wasp_general.verify import verify_type
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode
from wasp_general.command.result import WPlainCommandResult
from wasp_general.command.enhanced import WEnhancedCommand

from wasp_backup.core import WBackupMeta


class WCompressionArgumentHelper(WCommandArgumentDescriptor.ArgumentCastingHelper):

	def __init__(self):
		WCommandArgumentDescriptor.ArgumentCastingHelper.__init__(
			self, casting_fn=self.cast_string
		)

	@staticmethod
	@verify_type(value=str)
	def cast_string(value):
		value = value.lower()
		if value == 'gzip':
			return WBackupMeta.Archive.CompressionMode.gzip
		elif value == 'bzip2':
			return WBackupMeta.Archive.CompressionMode.bzip2
		elif value == 'disabled':
			return
		else:
			raise ValueError('Invalid compression value')


def cipher_name_validation(cipher_name):
	try:
		if WAESMode.parse_cipher_name(cipher_name) is not None:
			return True
	except ValueError:
		pass
	return False


__common_args__ = {
	'backup-archive': WCommandArgumentDescriptor(
		'backup-archive', required=True, multiple_values=False, meta_var='archive_path',
		help_info='backup file path'
	),

	'input-files': WCommandArgumentDescriptor(
		'input-files', required=True, multiple_values=True, meta_var='input_path',
		help_info='files or directories to backup'
	),

	'input-program': WCommandArgumentDescriptor(
		'input-program', required=True, multiple_values=False, meta_var='program_command',
		help_info='program which output will be backed up'
	),

	'compression': WCommandArgumentDescriptor(
		'compression', meta_var='compression_type',
		help_info='compression option. One of: "gzip", "bzip2" or "disabled". It is disabled by default',
		casting_helper=WCompressionArgumentHelper()
	),

	'password': WCommandArgumentDescriptor(
		'password', meta_var='encryption_password',
		help_info='password to encrypt backup. Backup is not encrypted by default'
	),

	'cipher_algorithm': WCommandArgumentDescriptor(
		'cipher_algorithm', meta_var='algorithm_name',
		help_info='cipher that will be used for encrypt (backup will not be encrypted if password was not '
		'set). It is "AES-256-CBC" by default',
		casting_helper=WCommandArgumentDescriptor.StringArgumentCastingHelper(
			validate_fn=cipher_name_validation
		),
		default_value='AES-256-CBC'
	),

	'io-write-rate': WCommandArgumentDescriptor(
		'io-write-rate', meta_var='maximum writing rate',
		help_info='use this parameter to limit disk I/O load (bytes per second). You can use '
		'suffixes like "K" for kibibytes, "M" for mebibytes, "G" for gibibytes, "T" for tebibytes for '
		'convenience ', casting_helper=WCommandArgumentDescriptor.DataSizeArgumentHelper()
	),

	'copy-to': WCommandArgumentDescriptor(
		'copy-to', meta_var='URL', help_info='Location to copy backup archive to'
	),

	'notify-app': WCommandArgumentDescriptor(
		'notify-app', meta_var='app_path', help_info='Application that will be called on archive creation'
	),
}


# noinspection PyAbstractClass
class WBackupCommand(WEnhancedCommand):

	__command__ = None

	__arguments__ = tuple()

	def __init__(self, logger):
		WEnhancedCommand.__init__(self, self.__command__, *self.__arguments__)
		self.__logger = logger
		self.__stop_event = None
		self.__archiver = None

	def logger(self):
		return self.__logger

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event

	def archiver(self):
		return self.__archiver

	def set_archiver(self, value):
		self.__archiver = value

	@classmethod
	def process_backup_result(cls, archiver, command_arguments):
		copy_to = None
		if 'copy-to' in command_arguments.keys():
			copy_to = command_arguments['copy-to']

		notify_app = None
		if 'notify-app' in command_arguments.keys():
			notify_app = command_arguments['notify-app']

		def notify():
			if notify_app is not None:
				first_fork_pid = os.fork()
				if first_fork_pid == 0:
					second_fork_pid = os.fork()
					if second_fork_pid == 0:

						meta_tempfile = tempfile.NamedTemporaryFile(delete=False)
						meta_tempfile.write(archiver.binary_meta())
						meta_tempfile.close()

						os.execlp(
							notify_app,
							os.path.basename(notify_app),
							archiver.archive_path(),
							meta_tempfile.name
						)
					else:
						sys.exit(0)
				else:
					os.waitpid(first_fork_pid, 0)

		def command_result(result):
			notify()
			return WPlainCommandResult(result)

		if copy_to is None:
			return command_result('Archive "%s" was created successfully' % archiver.archive_path())

		if WBackupMeta.__uploader_collection__.upload(copy_to, archiver.archive_path()) is True:
			return command_result(
				'Archive "%s" was created and uploaded successfully' % archiver.archive_path()
			)

		return command_result(
			'Archive "%s" was created successfully. But it fails to upload archive to destination' %
			archiver.archive_path()
		)
