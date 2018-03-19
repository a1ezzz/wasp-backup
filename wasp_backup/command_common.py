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
import shlex
from datetime import datetime
import tempfile

from wasp_general.verify import verify_type
from wasp_general.uri import WURI
from wasp_general.network.clients.proto import WNetworkClientProto
from wasp_general.network.clients.base import WCommonNetworkClientCapability
from wasp_general.network.clients.collection import __default_client_collection__
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode
from wasp_general.command.result import WPlainCommandResult
from wasp_general.command.enhanced import WEnhancedCommand

from wasp_backup.core import WBackupMeta, WBackupMetaProvider
from wasp_backup.notify import notify


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

	'copy-fail': WCommandArgumentDescriptor(
		'copy-fail', flag_mode=True, help_info='If specified, then backup will fail if copy operation fails. '
		'(But local archive would not be deleted any way)',
	),

	'notify-app': WCommandArgumentDescriptor(
		'notify-app', meta_var='app_path', help_info='Application that will be called as a handler'
	),
}


# noinspection PyAbstractClass
class WBackupCommand(WEnhancedCommand):

	__command__ = None

	__arguments__ = tuple()
	__relationships__ = None

	def __init__(self, logger):
		WEnhancedCommand.__init__(
			self, self.__command__, *self.__arguments__, relationships=self.__relationships__
		)
		self.__logger = logger
		self.__stop_event = None

	def logger(self):
		return self.__logger

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event


# noinspection PyAbstractClass
class WCreateBackupCommand(WBackupCommand):

	class UploadFailed(Exception):
		pass

	def __init__(self, logger):
		WBackupCommand.__init__(self, logger)
		self.__archiver = None

	def archiver(self):
		return self.__archiver

	def set_archiver(self, value):
		self.__archiver = value

	def _create_backup(self, command_arguments, *args, **kwargs):
		archiver = self.archiver()
		if archiver is None:
			raise RuntimeError('Archiver must be set before call')

		try:
			backup_started_at = datetime.utcnow()
			archiver.archive(*args, **kwargs)
			backup_duration = (datetime.utcnow() - backup_started_at).seconds

			copy_to = None
			if 'copy-to' in command_arguments.keys():
				copy_to = command_arguments['copy-to']

			notify_app = None
			if 'notify-app' in command_arguments.keys():
				notify_app = command_arguments['notify-app']

			copy_fail = False
			if 'copy-fail' in command_arguments.keys():
				copy_fail = command_arguments['copy-fail']

			if copy_to is None:
				return self.__handle_backup_result(
					'Archive "%s" was created successfully' % archiver.archive_path(),
					notify_app=notify_app,
					backup_duration=backup_duration
				)

			copy_result, copy_duration = self.__copy(archiver.archive_path(), copy_to)

			if copy_result is True:
				backup_result = \
					'Archive "%s" was created and uploaded successfully' % archiver.archive_path()
			elif copy_fail is False:
				backup_result = \
					'Archive "%s" was created successfully. But it fails to upload archive to ' \
					'destination' % archiver.archive_path()
			else:
				raise WCreateBackupCommand.UploadFailed(
					'Unable to upload archive "%s"' % archiver.archive_path()
				)

			return self.__handle_backup_result(
				backup_result,
				notify_app=notify_app,
				backup_duration=backup_duration,
				copy_to=copy_to,
				copy_complete=copy_result,
				copy_duration=copy_duration
			)

		finally:
			self.set_archiver(None)

	def __copy(self, archive_path, copy_to):
		try:
			copy_started_at = datetime.utcnow()
			uri = WURI.parse(copy_to)
			if uri.path() is not None:
				dir_name, file_name = os.path.split(uri.path())
				uri.component(WURI.Component.path, dir_name)

				network_client = __default_client_collection__.open(uri)
				with open(archive_path, 'rb') as f:
					copy_result = network_client.request(WCommonNetworkClientCapability.upload_file, file_name, f)
				copy_duration = (datetime.utcnow() - copy_started_at).total_seconds()
				return copy_result, copy_duration
		except WNetworkClientProto.ConnectionError:
			pass
		return False, -1

	def __handle_backup_result(
		self, str_result, notify_app=None, backup_duration=None, copy_to=None, copy_complete=None,
		copy_duration=None
	):
		archiver = self.archiver()
		if archiver is None:
			raise RuntimeError('Archiver must be set before call')

		if notify_app is None:
			return WPlainCommandResult(str_result)

		meta_data = archiver.meta()
		meta_data[WBackupMeta.BackupNotificationOptions.created_archive] = archiver.archive_path()
		meta_data[WBackupMeta.BackupNotificationOptions.backup_duration] = backup_duration
		meta_data[WBackupMeta.BackupNotificationOptions.total_archive_size] = os.stat(archiver.archive_path()).st_size
		meta_data[WBackupMeta.BackupNotificationOptions.copy_to] = copy_to
		meta_data[WBackupMeta.BackupNotificationOptions.copy_completion] = copy_complete
		meta_data[WBackupMeta.BackupNotificationOptions.copy_duration] = copy_duration

		notify(
			meta_data, notify_app,
			encode_strict_cls=(WBackupMeta.Archive.MetaOptions, WBackupMeta.BackupNotificationOptions)
		)
		return WPlainCommandResult(str_result)
