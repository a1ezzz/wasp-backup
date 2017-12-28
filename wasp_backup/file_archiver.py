# -*- coding: utf-8 -*-
# wasp_backup/file_archiver.py
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

import io

from wasp_general.verify import verify_type, verify_value

from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta
from wasp_backup.archiver import WBasicArchiveCreator


class WFileArchiveCreator(WBasicArchiveCreator):

	@verify_type('paranoid', archive_path=str, io_write_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_write_rate=lambda x: x is None or x > 0)
	@verify_type(cipher=(WBackupCipher, None), compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	def __init__(
		self, backup_source, archive_path, logger, stop_event=None, io_write_rate=None, compression_mode=None,
		cipher=None, buffer_size=io.DEFAULT_BUFFER_SIZE
	):
		WBasicArchiveCreator.__init__(
			self, archive_path, logger, stop_event=stop_event, io_write_rate=io_write_rate,
			compression_mode=compression_mode, cipher=cipher
		)
		self.__backup_source = backup_source
		self.__buffer_size = buffer_size

	def backup_source(self):
		return self.__backup_source

	def buffer_size(self):
		return self.__buffer_size

	def write_archive(self, fo, archive):
		backup_source = self.backup_source()
		buffer_size = self.buffer_size()

		read_buffer = backup_source.read(buffer_size)
		while len(read_buffer) > 0:
			fo.write(read_buffer)
			read_buffer = backup_source.read(buffer_size)

	def meta(self):
		result = WBasicArchiveCreator.meta(self)
		result[WBackupMeta.Archive.MetaOptions.archived_files] = self.backup_source()
		return result
