# -*- coding: utf-8 -*-
# wasp_backup/apps.py
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

from wasp_general.verify import verify_type
from wasp_general.command.command import WCommandResult
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode

from wasp_launcher.apps import WCommandKit
from wasp_launcher.host_apps.broker_commands import WBrokerCommand

from wasp_backup.archiver import WBackupTarArchiver, WLVMBackupTarArchiver
from wasp_backup.cipher import WBackupCipher


class WBackupBrokerCommandKit(WCommandKit):

	__kit_name__ = 'com.binblob.wasp-backup.broker-commands'

	@classmethod
	def name(cls):
		return cls.__kit_name__

	@classmethod
	def brief_description(cls):
		return 'backup creation/restoring commands'

	@classmethod
	def commands(cls):
		return WBackupCommands.Backup(),


def cipher_name_validation(cipher_name):
	try:
		if WAESMode.parse_cipher_name(cipher_name) is not None:
			return True
	except ValueError:
		pass
	return False


class WBackupCommands:

	class Backup(WBrokerCommand):

		class CompressionArgumentHelper(WCommandArgumentDescriptor.ArgumentCastingHelper):

			def __init__(self):
				WCommandArgumentDescriptor.ArgumentCastingHelper.__init__(
					self, casting_fn=self.cast_string
				)

			@staticmethod
			@verify_type(value=str)
			def cast_string(value):
				value = value.lower()
				if value == 'gzip':
					return WBackupTarArchiver.CompressMode.gzip
				elif value == 'bzip2':
					return WBackupTarArchiver.CompressMode.bzip2
				elif value == 'disabled':
					return
				else:
					raise ValueError('Invalid compression value')

		__arguments__ = [
			WCommandArgumentDescriptor(
				'input', required=True, multiple_values=True, meta_var='input_path',
				help_info='files or directories to backup'
			),
			WCommandArgumentDescriptor(
				'output', required=True, meta_var='output_filename', help_info='backup file path'
			),
			WCommandArgumentDescriptor(
				'sudo', flag_mode=True,
				help_info='use "sudo" command for privilege promotion. "sudo" may be used for snapshot \
creation, partition mounting and un-mounting'
			),
			WCommandArgumentDescriptor(
				'force-snapshot', flag_mode=True, help_info='force to use snapshot for backup. \
By default, backup will try to make snapshot for input files, if it is unable to do so - then backup copy files as is. \
			With this flag, if snapshot can not be created - backup will stop'
			),
			WCommandArgumentDescriptor(
				'snapshot-volume-size', meta_var='fraction_size',
				help_info='snapshot volume size as fraction of original volume size',
				casting_helper=WCommandArgumentDescriptor.FloatArgumentCastingHelper(
					validate_fn=lambda x: x > 0
				)
			),
			WCommandArgumentDescriptor(
				'snapshot-mount-dir', meta_var='mount_path',
				help_info='path where snapshot volume should be mount. It is random directory by \
default'
			),
			WCommandArgumentDescriptor(
				'compression', meta_var='compression_type',
				help_info='compression option. One of: "gzip", "bzip2" or "disabled". It is disabled \
by default', casting_helper=CompressionArgumentHelper()
			),
			WCommandArgumentDescriptor(
				'password', meta_var='encryption_password',
				help_info='password to encrypt backup. Backup is not encrypted by default'
			),
			WCommandArgumentDescriptor(
				'cipher_algorithm', meta_var='algorithm_name',
				help_info='cipher that will be used for encrypt (backup won\'nt be encrypted if \
password wasn\'t set). It is "AES-256-CBC" by default',
				casting_helper=WCommandArgumentDescriptor.StringArgumentCastingHelper(
					validate_fn=cipher_name_validation
				),
				default_value='AES-256-CBC'
			)
		]

		def __init__(self):
			WBrokerCommand.__init__(self, 'backup', *WBackupCommands.Backup.__arguments__)

		def _exec(self, command_arguments):
			import datetime
			output = 'backup. now - ' + str(datetime.datetime.now()) + ': ' + str(command_arguments)

			compress_mode = None
			if 'compression' in command_arguments.keys():
				compress_mode = command_arguments['compression']

			cipher = None
			if 'password' in command_arguments:
				cipher = WBackupCipher(
					command_arguments['cipher_algorithm'], command_arguments['password']
				)

			archiver = WLVMBackupTarArchiver(
				command_arguments['output'], *command_arguments['input'], compress_mode=compress_mode,
				sudo=command_arguments['sudo'], cipher=cipher
			)

			snapshot_size = None
			if 'snapshot-volume-size' in command_arguments.keys():
				snapshot_size = command_arguments['snapshot-volume-size']

			snapshot_mount_dir = None
			if 'snapshot-volume-size' in command_arguments.keys():
				snapshot_mount_dir = command_arguments['snapshot-mount-dir']

			import threading

			def archiver_thread():
				archiver.archive(
					snapshot_force=command_arguments['force-snapshot'], snapshot_size=snapshot_size,
					mount_directory=snapshot_mount_dir
				)
				archiver.write_meta()

			threading.Thread(target=archiver_thread).start()

			return WCommandResult(output=output)

		def brief_description(self):
			return 'backup data'
