# -*- coding: utf-8 -*-
# wasp_backup/retention.py
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
import json
from datetime import datetime, timedelta
from enum import Enum
from pytz import timezone

from wasp_general.command.enhanced import WCommandArgumentDescriptor, WCommandArgumentRelationship
from wasp_general.command.result import WPlainCommandResult
from wasp_general.network.clients.base import WCommonNetworkClientCapability
from wasp_general.network.clients.collection import __default_client_collection__
from wasp_general.uri import WURI
from wasp_general.datetime import local_tz

from wasp_backup.command_common import WBackupCommand, __common_args__
from wasp_backup.core import WBackupMeta
from wasp_backup.notify import notify


class WRetentionBackupCommand(WBackupCommand):

	class AgeHelper(Enum):
		name_parsing = 'name-parsing'
		archive_meta = 'archive-meta'
		modification_time = 'modification-time'
		creation_time = 'creation-time'

	class PeriodKeepFilter:

		def __init__(self, from_dt, tz, period_value, period_modifier, archive_number):
			self.__from_dt = from_dt
			self.__tz = tz
			self.__reduce_fn = None

			if period_modifier in ['M', 'H', 'd', 'w']:
				period = int(period_value) * 60  # at least a minute
				if period_modifier != 'M':
					period = period * 60  # at least an hour
					if period_modifier != 'H':
						period = period * 24  # at least a day
						if period_modifier == 'w':
							period = period * 7
				self.__reduce_fn = lambda: self.__from_dt - timedelta(seconds=period)
			elif period_modifier == 'm':

				def reduce_fn():
					year = self.__from_dt.year
					if self.__from_dt.month == 1:
						year -= 1
						month = 12
					else:
						month = self.__from_dt.month - 1

					return datetime(
						year=year, month=month, day=self.__from_dt.day,
						hour=self.__from_dt.hour, minute=self.__from_dt.minute,
						second=self.__from_dt.second, microsecond=self.__from_dt.microsecond
					).replace(tzinfo=self.__tz)
				self.__reduce_fn = reduce_fn
			elif period_modifier == 'y':
				self.__reduce_fn = lambda: datetime(
					year=self.__from_dt.year - 1, month=self.__from_dt.month,
					day=self.__from_dt.day, hour=self.__from_dt.hour,
					minute=self.__from_dt.minute, second=self.__from_dt.second,
					microsecond=self.__from_dt.microsecond
				).replace(tzinfo=self.__tz)
			else:
				raise ValueError('Unknown period_modifier was specified')

			self.__to_dt = self.__reduce_fn()
			self.__archive_number = int(archive_number)

		def __call__(self, check_item):
			if self.__archive_number <= 0:
				return False

			archive_name, creation_date = check_item

			if creation_date > self.__from_dt:
				return False
			if creation_date < self.__to_dt:
				return False

			self.__archive_number -= 1
			self.__from_dt = self.__to_dt
			self.__to_dt = self.__reduce_fn()
			return True

	__command__ = 'retention'
	__description__ = 'rotate archive backups that resides locally or on a remote location'

	__arguments__ = [
		WCommandArgumentDescriptor(
			'backup-location', required=True, multiple_values=False, meta_var='location',
			help_info='Location (network or directory) that has multiple backups to rotate'
		),

		WCommandArgumentDescriptor(
			'period-keep', required=True, multiple_values=True, meta_var='period@number_of_copies',
			help_info='parameter speicifies set of archives that should be kept from deleting. During '
			' the specified value only ONE archive will be kept. The value should be input in the '
			'following format: [period value][period modifier]@[number of periods]. Where '
			'[period modifier] is one of "M", "H", "d", "w", "m", "y" that represent "minute", "hour", '
			'"day", "week", "month", "year" respectively. [number of periods] is number of periods. '
			'For example "2d10" means that there will be 10 archives one archive per 2 days that will '
			'be kept. May be specified multiple times. In that case it works as a union of a single '
			'"period-keep" result',
			casting_helper=WCommandArgumentDescriptor.RegExpArgumentHelper('(\d+)([MHdwmy])@(\d+)')
		),

		WCommandArgumentDescriptor(
			'timezone', required=True, multiple_values=False, meta_var='timezone_name',
			help_info='timezone that will be apply to age-helper. If archive-meta-age-helper is specified '
			'then "UTC" should be used. For other helpers "local" is a good choice'
		),

		WCommandArgumentDescriptor(
			'minimum-archives', required=True, multiple_values=False, meta_var='archives_count',
			help_info='Number of archives that will be kept even if they are expired (the youngest '
			'archives will be selected).',
			casting_helper=WCommandArgumentDescriptor.IntegerArgumentCastingHelper(
				validate_fn=lambda x: x > 0
			)
		),

		WCommandArgumentDescriptor(
			'archive-selection', required=False, multiple_values=False, meta_var='regexp',
			help_info='regular expression that is used to select archives from the backup location',
			default_value='^.*$'
		),

		WCommandArgumentDescriptor(
			'name-parser-age-helper', flag_mode=True, help_info='defines method that will be used for '
			'archive to determine its age. This one will define age by parsing an archive name (dumb but '
			'fast)'
		),

		WCommandArgumentDescriptor(
			'archive-meta-age-helper', flag_mode=True, help_info='defines method that will be used for '
			'archive to determine its age. This one will define age from meta data from an archive (smart '
			'but slow, because archive may be downloaded and because meta data needs to be extracted)'
		),

		WCommandArgumentDescriptor(
			'modification-time-age-helper', flag_mode=True, help_info='defines method that will be used for '
			'archive to determine its age. This one will define age from archive modification time (not '
			'all of the location types supports this type of information, so it may be unavailable)'
		),

		WCommandArgumentDescriptor(
			'creation-time-age-helper', flag_mode=True,
			help_info='defines method that will be used for '
			'archive to determine its age. This one will define age from archive creation time (not '
			'all of the location types supports this type of information, so it may be unavailable)'
		),

		WCommandArgumentDescriptor(
			'date-format', required=False, multiple_values=False, meta_var='format',
			help_info='defines format of a date that will be used to find archive age (format has '
			'the same syntax as strptime python function)'
		),

		WCommandArgumentDescriptor(
			'download-location', required=False, multiple_values=False, meta_var='directory_path',
			help_info='directory where archives should be downloaded to in order to fecth archive meta '
			'data (used with "archive-meta-age-helper" flag)', default_value='/var/tmp'
		),
		__common_args__['notify-app']
	]

	__relationships__ = [
		WCommandArgumentRelationship(
			WCommandArgumentRelationship.Relationship.one_of,
			'name-parser-age-helper',
			'archive-meta-age-helper',
			'modification-time-age-helper',
			'creation-time-age-helper'
		),
		WCommandArgumentRelationship(
			WCommandArgumentRelationship.Relationship.requirement,
			'name-parser-age-helper',
			'date-format'
		),
	]

	def _exec(self, command_arguments, **command_env):
		location = command_arguments['backup-location']
		uri = WURI.parse(location)
		network_client = __default_client_collection__.open(uri)
		archives = network_client.request(WCommonNetworkClientCapability.list_dir)

		archive_selection_re = re.compile(command_arguments['archive-selection'])
		re_selected_archives = tuple(filter(lambda x: archive_selection_re.match(x) is not None, archives))

		if command_arguments['timezone'] != 'local':
			tz = timezone(command_arguments['timezone'])
		else:
			tz = local_tz()
		now = datetime.now(tz=tz)

		age_helper = self.__age_helper(command_arguments, network_client, tz)
		archive_ages = [(x, age_helper(x)) for x in re_selected_archives]

		archive_ages = list(filter(lambda x: (now - x[1]).total_seconds() > 0, archive_ages))  # remove list fn
		archive_ages.sort(key=lambda x: (now - x[1]).total_seconds())
		sorted_archives = [x[0] for x in archive_ages]

		archive_to_keep = set()
		for period_keep in command_arguments['period-keep']:
			archive_to_keep.update(filter(
				WRetentionBackupCommand.PeriodKeepFilter(now, tz, *period_keep), archive_ages
			))

		keep_archives = [x[0] for x in archive_to_keep]

		extra_archives_required = command_arguments['minimum-archives'] - len(keep_archives)
		if extra_archives_required > 0:
			for i in range(len(sorted_archives)):
				archive_name = sorted_archives[i]
				if archive_name not in keep_archives:
					keep_archives.append(archive_name)
					extra_archives_required -= 1

					if extra_archives_required <= 0:
						break

		files_to_remove = set(sorted_archives).difference(keep_archives)

		for file_name in files_to_remove:
			network_client.request(WCommonNetworkClientCapability.remove_file, file_name)

		if 'notify-app' in command_arguments:
			notify(
				{
					WBackupMeta.RetentionNotificationOptions.retention_location: location,
					WBackupMeta.RetentionNotificationOptions.kept_archives: list(keep_archives),
					WBackupMeta.RetentionNotificationOptions.removed_archives: list(files_to_remove)
				},
				command_arguments['notify-app'],
				encode_strict_cls=(WBackupMeta.RetentionNotificationOptions)
			)

		return WPlainCommandResult(
			'Archives deleted - %i, archives kept - %i' %
			(len(files_to_remove), len(set(re_selected_archives).difference(files_to_remove)))
		)

	def __age_helper(self, command_arguments, network_client, tz):
		if command_arguments['name-parser-age-helper'] is True:
			return self.__name_parser_helper(tz, command_arguments['date-format'])
		elif command_arguments['archive-meta-age-helper'] is True:
			return self.__archive_meta_helper(tz, network_client, command_arguments['download-location'])
		elif command_arguments['modification-time-age-helper'] is True:
			return self.__modification_time_helper(tz, network_client)
		elif command_arguments['creation-time-age-helper'] is True:
			return self.__creation_time_helper(tz, network_client)
		raise ValueError('Unknown helper name is specified')

	def __name_parser_helper(self, tz, date_format):
		def helper(archive):
			return datetime.strptime(archive, date_format).replace(tzinfo=tz)
		return helper

	def __archive_meta_helper(self, tz, network_client, download_location):
		# TODO: implement this
		raise NotImplementedError('Not ready')

	def __modification_time_helper(self, tz, network_client):
		# TODO: implement this
		raise NotImplementedError('Not ready')

	def __creation_time_helper(self, tz, network_client):
		# TODO: implement this
		raise NotImplementedError('Not ready')
