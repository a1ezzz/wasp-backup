# -*- coding: utf-8 -*-
# wasp_backup/popen_archiver.py
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
from wasp_backup.archiver import WBasicArchiveCreator
# noinspection PyUnresolvedReferences
from wasp_backup.version import __status__

import shlex
import subprocess

from wasp_backup.file_archiver import WFileArchiveCreator
from wasp_backup.core import WBackupMeta


class WPopenArchiveCreator(WFileArchiveCreator):

	def write_archive(self, fo, archive):
		with subprocess.Popen(shlex.split(self.backup_source()), stdout=subprocess.PIPE) as pipe:
			buffer_size = self.buffer_size()
			read_buffer = pipe.stdout.read(buffer_size)
			while len(read_buffer) > 0:
				fo.write(read_buffer)
				read_buffer = pipe.stdout.read(buffer_size)

	def meta(self):
		result = WFileArchiveCreator.meta(self)
		if WBackupMeta.Archive.MetaOptions.archived_files in result:
			result.pop(WBackupMeta.Archive.MetaOptions.archived_files)
		result[WBackupMeta.Archive.MetaOptions.archived_program] = self.backup_source()
		return result
