# -*- coding: utf-8 -*-
# wasp_backup/create.py
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
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.cli.formatter import na_formatter
from wasp_general.command.result import WPlainCommandResult

from wasp_launcher.core_broker import WBrokerCommand, WResponsiveBrokerCommand

from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta, cipher_name_validation
from wasp_backup.file_archiver import WBackupLVMFileArchiver


class WCreateBackupCommand(WBrokerCommand):

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
				return WBackupMeta.Archive.CompressionMode.gzip
			elif value == 'bzip2':
				return WBackupMeta.Archive.CompressionMode.bzip2
			elif value == 'disabled':
				return
			else:
				raise ValueError('Invalid compression value')

	class ArchivingTask:

		def __init__(self, archiver, snapshot_force, snapshot_size, mount_directory):
			self.__archiver = archiver
			self.__snapshot_force = snapshot_force
			self.__snapshot_size = snapshot_size
			self.__mount_directory = mount_directory

		def archiver(self):
			return self.__archiver

		def archive(self):
			self.archiver().archive(
				snapshot_force=self.__snapshot_force,
				snapshot_size=self.__snapshot_size,
				mount_directory=self.__mount_directory
			)
			return WPlainCommandResult(
				'Archive "%s" was created successfully' % self.archiver().archive_path()
			)

	__command__ = 'create'

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
			help_info='use "sudo" command for privilege promotion. "sudo" may be used for snapshot '
			'creation, partition mounting and un-mounting'
		),
		WCommandArgumentDescriptor(
			'force-snapshot', flag_mode=True, help_info='force to use snapshot for backup. '
			'By default, backup will try to make snapshot for input files, if it is unable to do so - then '
			'backup copy files as is. With this flag, if snapshot can not be created - backup will fail'
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
			help_info='path where snapshot volume should be mount. It is random directory by default'
		),
		WCommandArgumentDescriptor(
			'compression', meta_var='compression_type',
			help_info='compression option. One of: "gzip", "bzip2" or "disabled". It is disabled '
			'by default', casting_helper=CompressionArgumentHelper()
		),
		WCommandArgumentDescriptor(
			'password', meta_var='encryption_password',
			help_info='password to encrypt backup. Backup is not encrypted by default'
		),
		WCommandArgumentDescriptor(
			'cipher_algorithm', meta_var='algorithm_name',
			help_info='cipher that will be used for encrypt (backup will not be encrypted if '
			'password was not set). It is "AES-256-CBC" by default',
			casting_helper=WCommandArgumentDescriptor.StringArgumentCastingHelper(
				validate_fn=cipher_name_validation
			),
			default_value='AES-256-CBC'
		),
		WCommandArgumentDescriptor(
			'io-write-rate', meta_var='maximum writing rate',
			help_info='use this parameter to limit disk I/O load (bytes per second). You can use '
			'suffixes like "K" for kibibytes, "M" for mebibytes, "G" for gibibytes, "T" for tebibytes for '
			'convenience ', casting_helper=WCommandArgumentDescriptor.DataSizeArgumentHelper()
		),
	]

	def __init__(self):
		WBrokerCommand.__init__(self, self.__command__, *self.__arguments__)
		self.__archiver = None
		self.__stop_event = None

	def archiver(self):
		return self.__archiver

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event

	def _exec(self, command_arguments, **command_env):
		compression_mode = None
		if 'compression' in command_arguments.keys():
			compression_mode = command_arguments['compression']

		cipher = None
		if 'password' in command_arguments:
			cipher = WBackupCipher(
				command_arguments['cipher_algorithm'], command_arguments['password']
			)

		snapshot_size = None
		if 'snapshot-volume-size' in command_arguments.keys():
			snapshot_size = command_arguments['snapshot-volume-size']

		snapshot_mount_dir = None
		if 'snapshot-mount-dir' in command_arguments.keys():
			snapshot_mount_dir = command_arguments['snapshot-mount-dir']

		io_write_rate = None
		if 'io-write-rate' in command_arguments.keys():
			io_write_rate = command_arguments['io-write-rate']

		self.__archiver = WBackupLVMFileArchiver(
			command_arguments['output'], *command_arguments['input'],
			compression_mode=compression_mode, sudo=command_arguments['sudo'], cipher=cipher,
			io_write_rate=io_write_rate, stop_event=self.stop_event()
		)

		try:
			self.__archiver.archive(
				snapshot_force=command_arguments['force-snapshot'],
				snapshot_size=snapshot_size,
				mount_directory=snapshot_mount_dir
			)
			return WPlainCommandResult(
				'Archive "%s" was created successfully' % self.__archiver.archive_path()
			)
		finally:
			self.__archiver = None

	def brief_description(self):
		return 'create backup archive of files and directories'


class WResponsiveCreateBackupCommand(WResponsiveBrokerCommand):

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	class ScheduledTask(WResponsiveBrokerCommand.ScheduledTask):

		def state_details(self):
			archiver = self.basic_command().archiver()
			if archiver is not None:
				return 'Archiving is not running. May be finalizing'

			result = 'Archiving file: %s' % na_formatter(archiver.last_file())
			details = archiver.archiving_details()
			if details is not None:
				result += '\n' + details
			return result

		def thread_started(self):
			self.basic_command().stop_event(self.stop_event())
			WResponsiveBrokerCommand.ScheduledTask.thread_started(self)

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WCreateBackupCommand(), scheduled_task_cls=WResponsiveCreateBackupCommand.ScheduledTask
		)
