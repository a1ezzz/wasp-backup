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

from enum import Enum


class WBackupMeta:

	class Archive:

		class CompressionMode(Enum):
			gzip = 'gz'
			bzip2 = 'bz2'

		class MetaOptions(Enum):
			inside_filename = 'inside_filename'
			inside_tar = 'inside_tar'
			archived_files = 'archived_files'
			archived_program = 'archived_program'
			compression_mode = 'compression_mode'
			hash_algorithm = 'hash_algorithm'
			hash_value = 'hash_value'
			snapshot_used = 'snapshot_used'
			original_lv_uuid = 'original_lv_uuid'
			io_write_rate = 'io_write_rate'
			pbkdf2_salt = 'pbkdf2_salt'
			pbkdf2_prf = 'pbkdf2_prf'
			pbkdf2_iterations_count = 'pbkdf2_iterations_count'
			cipher_algorithm = 'cipher_algorithm'

		__meta_filename__ = 'meta.json'
		__maximum_meta_filesize__ = 50 * 1024 * 1024
		__basic_inside_filename__ = 'archive'
		__file_mode__ = int('660', base=8)
		__hash_generator_name__ = 'MD5'

	class LVMSnapshot:
		__default_snapshot_size__ = 0.1
		__mount_directory_prefix__ = 'wasp-backup-'

	__scheduler_instance_name__ = 'com.binblob.wasp-backup'
	__task_source_name__ = 'com.binblob.wasp-backup.scheduler.sources.instant_source'


class WArchiverIOMetaProvider:

	def meta(self):
		return {}


class WArchiverIOStatusProvider:

	def status(self):
		return None
