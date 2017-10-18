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

import re

from wasp_general.verify import verify_type
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode
from wasp_general.task.scheduler.task_source import WInstantTaskSource
from wasp_general.cli.formatter import na_formatter

from wasp_launcher.core_scheduler import WLauncherScheduleTask, WSchedulerTaskSourceInstaller, WLauncherTaskSource
from wasp_launcher.core_broker import WResponsiveBrokerCommand, WCommandKit

from wasp_backup.archiver import WLVMBackupTarArchiver
from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta


class WBackupBrokerCommandKit(WCommandKit):

	__registry_tag__ = 'com.binblob.wasp-backup.broker-commands'

	@classmethod
	def description(cls):
		return 'backup creation/restoring commands'

	@classmethod
	def commands(cls):
		return WBackupCommands.Create(), WBackupCommands.Check()


class WBackupSchedulerInstaller(WSchedulerTaskSourceInstaller):

	__scheduler_instance__ = 'com.binblob.wasp-backup'

	class InstantTaskSource(WInstantTaskSource, WLauncherTaskSource):

		__task_source_name__ = 'com.binblob.wasp-backup.scheduler.sources.instant_source'

		def __init__(self, scheduler):
			WInstantTaskSource.__init__(self, scheduler)
			WLauncherTaskSource.__init__(self)

		def name(self):
			return self.__task_source_name__

		def description(self):
			return 'Backup tasks from broker'


	__registry_tag__ = 'com.binblob.wasp-backup.scheduler.sources'

	def sources(self):
		return WBackupSchedulerInstaller.InstantTaskSource,


def cipher_name_validation(cipher_name):
	try:
		if WAESMode.parse_cipher_name(cipher_name) is not None:
			return True
	except ValueError:
		pass
	return False


class WBackupCommands:

	__dependency__ = [
		'com.binblob.wasp-backup.scheduler.sources'
	]


	class Create(WResponsiveBrokerCommand):

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

		class WriteRateArgumentHelper(WCommandArgumentDescriptor.ArgumentCastingHelper):

			__write_rate_re__ = re.compile('^(\d+[.\d]*)([KMGT]?)$')

			def __init__(self):
				WCommandArgumentDescriptor.ArgumentCastingHelper.__init__(
					self, casting_fn=self.cast_string
				)

			@staticmethod
			@verify_type(value=str)
			def cast_string(value):
				re_rate = WBackupCommands.Create.WriteRateArgumentHelper.__write_rate_re__.search(value)
				if re_rate is None:
					raise ValueError('Invalid write rate')
				result = float(re_rate.group(1))
				if re_rate.group(2) == 'K':
					result *= (1 << 10)
				elif re_rate.group(2) == 'M':
					result *= (1 << 20)
				elif re_rate.group(2) == 'G':
					result *= (1 << 30)
				elif re_rate.group(2) == 'T':
					result *= (1 << 40)

				return result

		class SchedulerTask(WLauncherScheduleTask):

			__task_name__ = 'archiving task'
			__task_description_prefix__ = 'files that are archiving: '

			def __init__(self, archiver, snapshot_force, snapshot_size, mount_directory):
				WLauncherScheduleTask.__init__(self)
				self.__archiver = archiver
				self.__snapshot_force = snapshot_force
				self.__snapshot_size = snapshot_size
				self.__mount_directory = mount_directory

			def thread_started(self):
				self.__archiver.stop_event(self.stop_event())
				self.__archiver.archive(
					snapshot_force=self.__snapshot_force,
					snapshot_size=self.__snapshot_size,
					mount_directory=self.__mount_directory
				)

			def name(self):
				return self.__task_name__

			def brief_description(self):
				return self.__task_description_prefix__ + (', '.join(self.__archiver.backup_sources()))

			def state_details(self):
				result = 'Archiving file: %s' % na_formatter(self.__archiver.last_file())
				details = self.__archiver.archiving_details()
				if details is not None:
					result += '\n' + details
				return result

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
password was not set). It is "AES-256-CBC" by default',
				casting_helper=WCommandArgumentDescriptor.StringArgumentCastingHelper(
					validate_fn=cipher_name_validation
				),
				default_value='AES-256-CBC'
			),
			WCommandArgumentDescriptor(
				'io-write-rate', meta_var='maximum writing rate',
				help_info='use this parameter to limit disk I/O load (bytes per second). You can use \
suffixes like "K" for kibibytes, "M" for mebibytes, "G" for gibibytes, "T" for tebibytes for convenience ',
				casting_helper=WriteRateArgumentHelper()
			),
		]

		__task_source_name__ = WBackupSchedulerInstaller.InstantTaskSource.__task_source_name__
		__scheduler_instance__ = WBackupSchedulerInstaller.__scheduler_instance__

		def create_task(self, command_arguments, **command_env):
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

			archiver = WLVMBackupTarArchiver(
				command_arguments['output'], *command_arguments['input'],
				compression_mode=compression_mode, sudo=command_arguments['sudo'], cipher=cipher,
				io_write_rate=io_write_rate
			)

			return WBackupCommands.Create.SchedulerTask(
				archiver, command_arguments['force-snapshot'], snapshot_size, snapshot_mount_dir
			)

		def brief_description(self):
			return 'create backup archive of files and directories'

	class Check(WResponsiveBrokerCommand):

		class SchedulerTask(WLauncherScheduleTask):

			def __init__(self, archive):
				WLauncherScheduleTask.__init__(self)
				self.__archive = archive

			def thread_started(self):
				pass

			def name(self):
				return 'Archiving check task'

			def brief_description(self):
				return 'Checking file: ' + self.__archive

			def state_details(self):
				return None

		__command__ = 'check'
		__arguments__ = [
			WCommandArgumentDescriptor(
				'archive', required=True, multiple_values=False, meta_var='archive_path',
				help_info='backup file to check'
			)
		]

		__task_source_name__ = WBackupSchedulerInstaller.InstantTaskSource.__task_source_name__
		__scheduler_instance__ = WBackupSchedulerInstaller.__scheduler_instance__

		def create_task(self, command_arguments, **command_env):
			return WBackupCommands.Check.SchedulerTask(command_arguments['archive'])

		def brief_description(self):
			return 'check backup archive for integrity'
