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

import traceback

from wasp_general.verify import verify_type
from wasp_general.command.command import WCommandResult
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode
from wasp_general.task.scheduler.task_source import WInstantTaskSource

from wasp_launcher.core import WCommandKit, WAppsGlobals
from wasp_launcher.core_scheduler import WLauncherScheduleTask, WSchedulerTaskSourceInstaller, WLauncherTaskSource
from wasp_launcher.apps.broker_commands import WBrokerCommand

from wasp_backup.archiver import WBackupTarArchiver, WLVMBackupTarArchiver
from wasp_backup.cipher import WBackupCipher


class WBackupBrokerCommandKit(WCommandKit):

	__registry_tag__ = 'com.binblob.wasp-backup.broker-commands'

	@classmethod
	def description(cls):
		return 'backup creation/restoring commands'

	@classmethod
	def commands(cls):
		return WBackupCommands.Backup(),


class WBackupSchedulerInstaller(WSchedulerTaskSourceInstaller):

	__scheduler_instance__ = 'com.binblob.wasp-backup'

	class InstantTaskSource(WInstantTaskSource, WLauncherTaskSource):

		__task_source_name__ = 'com.binblob.wasp-backup.scheduler.sources.instant_source'

		def __init__(self, scheduler):
			WInstantTaskSource.__init__(self, scheduler, on_drop_callback=self.on_drop)
			WLauncherTaskSource.__init__(self)
			self.__scheduler = scheduler

		def name(self):
			return self.__task_source_name__

		def description(self):
			return 'Backup tasks from broker'

		def add_task(self, task):
			WInstantTaskSource.add_task(self, task)
			self.__scheduler.update(task_source=self)

		@classmethod
		def on_drop(cls, task):
			WAppsGlobals.log.error('Some task was dropped: ' + str(task))

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
				try:
					self.__archiver.stop_event(self.stop_event())
					self.__archiver.archive(
						snapshot_force=self.__snapshot_force,
						snapshot_size=self.__snapshot_size,
						mount_directory=self.__mount_directory
					)
				except Exception as e:
					WAppsGlobals.log.error('Backup failed. Exception was raised: ' + str(e))
					WAppsGlobals.log.error(traceback.format_exc())

			def thread_stopped(self):
				WLauncherScheduleTask.thread_stopped(self)

			def thread_exception(self, raised_exception):
				WLauncherScheduleTask.thread_exception(self, raised_exception)

			def name(self):
				return self.__task_name__

			def description(self):
				return self.__task_description_prefix__ + (', '.join(self.__archiver.backup_sources()))


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

		__scheduler_task_timeout__ = 3

		def __init__(self):
			WBrokerCommand.__init__(self, 'backup', *WBackupCommands.Backup.__arguments__)

		def _exec(self, command_arguments):
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
			if 'snapshot-mount-dir' in command_arguments.keys():
				snapshot_mount_dir = command_arguments['snapshot-mount-dir']

			task_source = WAppsGlobals.scheduler.task_source(
				WBackupSchedulerInstaller.InstantTaskSource.__task_source_name__,
				WBackupSchedulerInstaller.__scheduler_instance__
			)

			if task_source is None:
				return WCommandResult(
					output='Unable to find suitable scheduler. Command rejected', error=1
				)

			scheduler_task = WBackupCommands.Backup.SchedulerTask(
				archiver, command_arguments['force-snapshot'], snapshot_size, snapshot_mount_dir
			)
			task_source.add_task(scheduler_task)

			if scheduler_task.start_event().wait(self.__scheduler_task_timeout__) is False:
				return WCommandResult(
					output='Scheduler is busy at the moment. Backup task is registered and waits '
					'for the scheduler',
					error=1
				)

			uid = None
			for task in task_source.scheduler_service().running_records():
				if task.record().task() == scheduler_task:
					uid = task.task_uid()

			if uid is not None:
				return WCommandResult(output='Backup task is running. Task uid: %s' % str(uid))
			else:
				return WCommandResult(output='Backup seems to be finished. Really fast!')

		def brief_description(self):
			return 'backup data'
