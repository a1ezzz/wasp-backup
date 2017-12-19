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

from wasp_general.crypto.aes import WAESMode


class WBackupMeta:

	class Archive:

		class CompressionMode(Enum):
			gzip = 'gz'
			bzip2 = 'bz2'

		class MetaOptions(Enum):
			inside_archive_filename = 'inside_archive_filename'
			archived_files = 'archived_files'
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
		__inside_archive_basic_filename__ = 'archive'
		__file_mode__ = int('660', base=8)
		__hash_generator_name__ = 'MD5'

		@classmethod
		def inside_archive_filename(cls, compression_mode):
			if compression_mode is None:
				return WBackupMeta.Archive.__inside_archive_basic_filename__ + '.tar'
			if isinstance(compression_mode, WBackupMeta.Archive.CompressionMode) is True:
				suffix = compression_mode.value
				return WBackupMeta.Archive.__inside_archive_basic_filename__ + '.tar.' + suffix
			raise TypeError('Invalid compression mode')

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


def cipher_name_validation(cipher_name):
	try:
		if WAESMode.parse_cipher_name(cipher_name) is not None:
			return True
	except ValueError:
		pass
	return False
