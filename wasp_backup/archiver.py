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
import uuid
import tempfile
from enum import Enum

from wasp_general.verify import verify_type, verify_value
from wasp_general.os.linux.lvm import WLogicalVolume
from wasp_general.os.linux.mounts import WMountPoint

from wasp_launcher.apps import WAppsGlobals


class WBackupTarArchiver:

	__meta_suffix__ = '.wb-meta'

	class CompressMode(Enum):
		gzip = 'gz'
		bzip2 = 'bz2'

	@verify_type(archive_path=str, backup_sources=str)
	@verify_value(archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
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


class WLVMBackupTarArchiver(WBackupTarArchiver):

	__default_snapshot_size__ = 0.1
	__mount_directory_prefix__ = 'wasp-backup-'

	@verify_type('paranoid', archive_path=str, backup_sources=str, compress_mode=WBackupTarArchiver.CompressMode)
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	@verify_type(sudo=bool)
	def __init__(self, archive_path, *backup_sources, compress_mode=None, sudo=False):
		WBackupTarArchiver.__init__(self, archive_path, *backup_sources, compress_mode=compress_mode)
		self.__sudo = sudo
		self.__logical_volume_uuid = None
		self.__snapshot = False

	def sudo(self):
		return self.__sudo

	@verify_type(snapshot_force=bool, snapshot_size=(int, float, None), mount_directory=(str, None))
	@verify_type(mount_fs=(str, None), mount_options=(list, tuple, set, None))
	def archive(
		self, snapshot_force=False, snapshot_size=None, mount_directory=None, mount_fs=None, mount_options=None
	):
		self.__logical_volume_uuid = None
		self.__snapshot = False

		logical_volume = None
		backup_sources = self.backup_sources()

		if len(backup_sources) == 0:
			if snapshot_force is True:
				raise RuntimeError('Unable to create snapshot for empty archive')
			else:
				WBackupTarArchiver.archive(self)
				return

		for source in backup_sources:
			lv = WLogicalVolume.logical_volume(source, sudo=self.sudo())
			if lv is None:
				if snapshot_force is True:
					raise RuntimeError('Unable to create snapshot for non-LVM volume')
				logical_volume = None
				break
			if logical_volume is None:
				logical_volume = lv
			elif os.path.realpath(logical_volume.volume_path()) == os.path.realpath(lv.volume_path()):
				pass
			else:
				if snapshot_force is True:
					raise RuntimeError(
						'Unable to create snapshot - files reside on different volumes'
					)
				logical_volume = None
				break

		if logical_volume is None:
			if snapshot_force is True:
				raise RuntimeError('Unable to create snapshot for unknown reason')
			WBackupTarArchiver.archive(self)
			return

		if snapshot_size is None:
			snapshot_size = self.__class__.__default_snapshot_size__

		snapshot_suffix = '-snapshot-%s' % str(uuid.uuid4())
		snapshot_volume = None
		remove_directory = False
		directory_mounted = False
		current_cwd = os.getcwd()

		try:
			snapshot_volume = logical_volume.create_snapshot(snapshot_size, snapshot_suffix)
			self.__logical_volume_uuid = logical_volume.uuid()
			self.__snapshot = True

			if mount_directory is None:
				mount_directory = tempfile.mkdtemp(
					suffix=snapshot_suffix, prefix=self.__class__.__mount_directory_prefix__
				)
				remove_directory = True
			if mount_options is None:
				mount_options = []
			mount_options.insert(0, 'ro')

			WMountPoint.mount(
				logical_volume.volume_path(), mount_directory, fs=mount_fs, options=mount_options,
				sudo=self.sudo()
			)
			directory_mounted = True

			mount_directory_length = len(mount_directory)
			for i in range(len(backup_sources)):
				backup_sources[i] = backup_sources[i][mount_directory_length:]

			os.chdir(mount_directory)
			self._archive(abs_path=False)

		except:
			self.__logical_volume_uuid = None
			self.__snapshot = False
			raise
		finally:
			os.chdir(current_cwd)

			if directory_mounted is True:
				WMountPoint.umount(logical_volume.volume_path(), sudo=self.sudo())

			if remove_directory is True:
				os.removedirs(mount_directory)

			if snapshot_volume is not None:
				snapshot_volume.remove_volume()

	def meta(self):
		meta = WBackupTarArchiver.meta(self)
		meta['snapshot'] = self.__snapshot
		meta['lv_uuid'] = self.__logical_volume_uuid if self.__logical_volume_uuid is not None else ''
		return meta
