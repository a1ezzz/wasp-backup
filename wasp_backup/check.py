# -*- coding: utf-8 -*-
# wasp_backup/check.py
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

from wasp_general.command.result import WPlainCommandResult
from wasp_launcher.core_broker import WBrokerCommand, WResponsiveBrokerCommand

from wasp_backup.core import WBackupMeta
from wasp_backup.archiver import WBackupTarChecker


class WCheckBackupCommand(WBrokerCommand):

	__command__ = 'check'
	__arguments__ = [
		WCommandArgumentDescriptor(
			'archive', required=True, multiple_values=False, meta_var='archive_path',
			help_info='backup file to check'
		),
		WCommandArgumentDescriptor(
			'io-read-rate', meta_var='maximum reading rate',
			help_info='use this parameter to limit disk I/O load (bytes per second). You can use '
			'suffixes like "K" for kibibytes, "M" for mebibytes, "G" for gibibytes, "T" for tebibytes for '
			'convenience ', casting_helper=WCommandArgumentDescriptor.DataSizeArgumentHelper()
		)
	]

	def __init__(self):
		WBrokerCommand.__init__(self, self.__command__, *self.__arguments__)
		self.__stop_event = None
		self.__checker = None

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event

	def checker(self):
		return self.__checker

	def _exec(self, command_arguments, **command_env):
		archive = command_arguments['archive']
		io_read_rate = None
		if 'io-read-rate' in command_arguments.keys():
			io_read_rate = command_arguments['io-read-rate']

		try:
			self.__checker = WBackupTarChecker(
				archive, stop_event=self.stop_event(), io_read_rate=io_read_rate
			)
			result, original_hash, calculated_hash = self.__checker.check_archive()
		finally:
			self.__checker = None

		if result is True:
			return WPlainCommandResult('Archive "%s" is OK' % archive)
		return WPlainCommandResult.error(
			'Archive "%s" is corrupted. Calculated hash - "%s". Original hash - "%s"' %
			(archive, calculated_hash, original_hash)
		)

	def brief_description(self):
		return 'check backup archive for integrity'


class WResponsiveCheckBackupCommand(WResponsiveBrokerCommand):

	__task_source_name__ = WBackupMeta.__task_source_name__
	__scheduler_instance__ = WBackupMeta.__scheduler_instance_name__

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

	def __init__(self):
		WResponsiveBrokerCommand.__init__(
			self, WCheckBackupCommand(), scheduled_task_cls=WResponsiveCheckBackupCommand.ScheduledTask
		)
