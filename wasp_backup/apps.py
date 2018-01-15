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

from wasp_general.task.scheduler.task_source import WInstantTaskSource
from wasp_general.cli.formatter import na_formatter

from wasp_launcher.core import WAppsGlobals
from wasp_launcher.core_scheduler import WSchedulerTaskSourceInstaller, WLauncherTaskSource
from wasp_launcher.core_broker import WCommandKit, WBrokerCommand, WResponsiveBrokerCommand

from wasp_backup.core import WBackupMeta
from wasp_backup.file_backup import WFileBackupCommand
from wasp_backup.check import WCheckBackupCommand
from wasp_backup.program_backup import WProgramBackupCommand
from wasp_backup.retention import WRetentionBackupCommand


class WResponsiveCreateBackupCommand(WResponsiveBrokerCommand):

	class FileBackupCommand(WFileBackupCommand, WBrokerCommand):

		def __init__(self):
			WFileBackupCommand.__init__(self, WAppsGlobals.log)
			WBrokerCommand.__init__(
				self, self.command_token(), *self.argument_descriptors(),
				relationships=self.relationships()
			)

		def brief_description(self):
			return self.__description__

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

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WResponsiveCreateBackupCommand.FileBackupCommand(),
			scheduled_task_cls=WResponsiveCreateBackupCommand.ScheduledTask
		)


class WResponsiveCheckBackupCommand(WResponsiveBrokerCommand):

	class CheckBackupCommand(WCheckBackupCommand, WBrokerCommand):

		def __init__(self):
			WCheckBackupCommand.__init__(self, WAppsGlobals.log)
			WBrokerCommand.__init__(
				self, self.command_token(), *self.argument_descriptors(),
				relationships=self.relationships()
			)

		def brief_description(self):
			return self.__description__

	class ScheduledTask(WResponsiveBrokerCommand.ScheduledTask):

		def state_details(self):
			checker = self.basic_command().checker()
			if checker is not None:
				details = checker.check_details()
				if details is not None:
					return '\n' + details

			return 'Checking is not running. May be finalizing'

		def thread_started(self):
			self.basic_command().stop_event(self.stop_event())
			WResponsiveBrokerCommand.ScheduledTask.thread_started(self)

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WResponsiveCheckBackupCommand.CheckBackupCommand(),
			scheduled_task_cls=WResponsiveCheckBackupCommand.ScheduledTask
		)


class WResponsiveProgramBackupCommand(WResponsiveBrokerCommand):

	class ProgramBackupCommand(WProgramBackupCommand, WBrokerCommand):

		def __init__(self):
			WProgramBackupCommand.__init__(self, WAppsGlobals.log)
			WBrokerCommand.__init__(
				self, self.command_token(), *self.argument_descriptors(),
				relationships=self.relationships()
			)

		def brief_description(self):
			return self.__description__

	class ScheduledTask(WResponsiveBrokerCommand.ScheduledTask):

		def state_details(self):
			archiver = self.basic_command().archiver()
			if archiver is not None:
				return 'Archiving is not running. May be finalizing'

			result = ''
			details = archiver.archiving_details()
			if details is not None:
				result += '\n' + details
			return result

		def thread_started(self):
			self.basic_command().stop_event(self.stop_event())
			WResponsiveBrokerCommand.ScheduledTask.thread_started(self)

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WResponsiveProgramBackupCommand.ProgramBackupCommand(),
			scheduled_task_cls=WResponsiveProgramBackupCommand.ScheduledTask
		)


class WResponsiveRetentionCommand(WResponsiveBrokerCommand):

	class RetentionCommand(WRetentionBackupCommand, WBrokerCommand):

		def __init__(self):
			WRetentionBackupCommand.__init__(self, WAppsGlobals.log)
			WBrokerCommand.__init__(
				self, self.command_token(), *self.argument_descriptors(),
				relationships=self.relationships()
			)

		def brief_description(self):
			return self.__description__

	class ScheduledTask(WResponsiveBrokerCommand.ScheduledTask):

		def state_details(self):
			# TODO: make it more descriptive!
			return 'Task is running?!'

		def thread_started(self):
			# TODO: make it more responsive!
			#self.basic_command().stop_event(self.stop_event())
			WResponsiveBrokerCommand.ScheduledTask.thread_started(self)

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WResponsiveRetentionCommand.RetentionCommand(),
			scheduled_task_cls=WResponsiveRetentionCommand.ScheduledTask
		)


class WBackupBrokerCommandKit(WCommandKit):

	__registry_tag__ = 'com.binblob.wasp-backup.broker-commands'

	@classmethod
	def description(cls):
		return 'backup creation/restoring commands'

	@classmethod
	def commands(cls):
		return (
			WResponsiveCreateBackupCommand(),
			WResponsiveCheckBackupCommand(),
			WResponsiveProgramBackupCommand(),
			WResponsiveRetentionCommand()
		)


class WBackupSchedulerInstaller(WSchedulerTaskSourceInstaller):

	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

	class InstantTaskSource(WInstantTaskSource, WLauncherTaskSource):

		__task_source_name__ = WBackupMeta.__task_source_name__

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
