# -*- coding: utf-8 -*-
# wasp_backup/core.py
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

import json
from enum import Enum


class WBackupMeta:

	class Archive:

		class CompressionMode(Enum):
			gzip = 'gz'
			bzip2 = 'bz2'

		class MetaOptions(Enum):
			creation_time = 'creation_time'  # unix time of archive creation (for UTC timezone)
			inside_filename = 'inside_filename'
			inside_tar = 'inside_tar'
			archived_files = 'archived_files'
			archived_program = 'archived_program'
			uncompressed_archive_size = 'uncompressed_archive_size'  # size of uncompressed data
			# (for inside_tar archive, this is a size of uncompressed inside tar, which is rounded to 10240)
			compression_mode = 'compression_mode'
			hash_algorithm = 'hash_algorithm'
			hash_value = 'hash_value'  # hash value of uncompressed inside archive (for
			# inside_tar archive, this is a hash of uncompressed inside tar)
			snapshot_used = 'snapshot_used'
			original_lv_uuid = 'original_lv_uuid'
			io_write_rate = 'io_write_rate'
			pbkdf2_salt = 'pbkdf2_salt'
			pbkdf2_prf = 'pbkdf2_prf'
			pbkdf2_iterations_count = 'pbkdf2_iterations_count'
			cipher_algorithm = 'cipher_algorithm'

		__meta_filename__ = 'meta.json'
		__maximum_meta_file_size__ = 50 * 1024 * 1024
		__basic_inside_file_name__ = 'archive'
		__file_mode__ = int('660', base=8)
		__hash_generator_name__ = 'MD5'

	class BackupNotificationOptions(Enum):
		created_archive = 'created_archive'
		backup_duration = 'backup_duration'
		copy_to = 'copy_to'
		copy_completion = 'copy_completion'
		copy_duration = 'copy_duration'
		total_archive_size = 'total_archive_size'

	class RetentionNotificationOptions(Enum):
		retention_location = 'retention_location'
		kept_archives = 'kept_archives'
		removed_archives = 'removed_archives'

	class LVMSnapshot:
		__default_snapshot_size__ = 0.1
		__mount_directory_prefix__ = 'wasp-backup-'

	__scheduler_instance_name__ = 'com.binblob.wasp-backup'
	__task_source_name__ = 'com.binblob.wasp-backup.scheduler.sources.instant_source'
	__notification_env_var_name__ = 'WASP_NOTIFICATION_META_FILE'


class WBackupMetaProvider:

	def meta(self):
		return {}

	@classmethod
	def encode_meta(cls, meta, strict_cls=None):
		result = {}
		for meta_key, meta_value in meta.items():
			if strict_cls is not None:
				if isinstance(meta_key, strict_cls) is True:
					result[meta_key.value] = meta_value
				else:
					raise TypeError('Invalid meta key spotted')
			else:
				result[meta_key] = meta_value

		return json.dumps(result).encode()


class WArchiverIOStatusProvider:

	def status(self):
		return None
