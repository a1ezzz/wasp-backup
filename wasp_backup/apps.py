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

from wasp_launcher.core_scheduler import WSchedulerTaskSourceInstaller, WLauncherTaskSource
from wasp_launcher.core_broker import WCommandKit

from wasp_backup.core import WBackupMeta
from wasp_backup.create import WResponsiveCreateBackupCommand
from wasp_backup.check import WResponsiveCheckBackupCommand


class WBackupBrokerCommandKit(WCommandKit):

	__registry_tag__ = 'com.binblob.wasp-backup.broker-commands'

	@classmethod
	def description(cls):
		return 'backup creation/restoring commands'

	@classmethod
	def commands(cls):
		return WResponsiveCreateBackupCommand(), WResponsiveCheckBackupCommand()


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
