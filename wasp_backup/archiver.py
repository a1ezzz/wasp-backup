# -*- coding: utf-8 -*-
# wasp_backup/archiver.py
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

import hashlib
import os
import tarfile
import json
from enum import Enum

from wasp_general.verify import verify_type, verify_value

from wasp_launcher.apps import WAppsGlobals


class WBackupTarArchiver:

	__meta_suffix__ = '.wb-meta'

	class CompressMode(Enum):
		gzip = 'gz'
		bzip2 = 'bz2'

	@verify_type(archive_path=str)
	@verify_value(archive_path=lambda x: len(x) > 0)
	def __init__(self, archive_path, *backup_sources, compress_mode=None):
		self.__archive_path = archive_path
		self.__backup_sources = list(backup_sources)

		self.__compress_mode = None
		if compress_mode is not None and isinstance(compress_mode, WBackupTarArchiver.CompressMode) is False:
			raise TypeError('Invalid compress mode')
		else:
			self.__compress_mode = compress_mode

	def archive_path(self):
		return self.__archive_path

	def backup_sources(self):
		return self.__backup_sources

	def compress_mode(self):
		return self.__compress_mode

	def tar_mode(self):
		compress_mode = self.compress_mode()
		return 'w:%s' % (compress_mode if compress_mode is not None else '')

	@classmethod
	def _verbose_filter(cls, tarinfo):
		WAppsGlobals.log.debug('Compressing: %s', tarinfo.name)
		return tarinfo

	@verify_type(abs_path=bool)
	def _archive(self, abs_path=True):
		tar = tarfile.open(name=self.archive_path(), mode=self.tar_mode())
		for entry in self.backup_sources():
			if abs_path is True:
				entry = os.path.abspath(entry)
			tar.add(entry, recursive=True, filter=self._verbose_filter)
		tar.close()

	def archive(self):
		self._archive()

	@classmethod
	@verify_type(filename=str)
	@verify_value(filename=lambda x: len(x) > 0)
	def _md5sum(cls, filename, block_size=65536):
		hash_fn = hashlib.md5()
		with open(filename, "rb") as f:
			for block in iter(lambda: f.read(block_size), b""):
				hash_fn.update(block)
		return hash_fn.hexdigest()

	def meta(self):
		return {'md5sum': self._md5sum(self.archive_path())}

	def write_meta(self):
		meta_file_name = self.archive_path() + self.__class__.__meta_suffix__
		WAppsGlobals.log.debug('Creating meta file: %s' % meta_file_name)
		meta_file = open(meta_file_name, 'w')
		meta_data = self.meta()
		meta_file.write(json.dumps(meta_data))
		meta_file.close()

		meta_data_keys = list(meta_data.keys())
		meta_data_keys.sort()
		for key in meta_data_keys:
			WAppsGlobals.log.debug('Archive meta information. %s: %s', str(key), str(meta_data[key]))
