# -*- coding: utf-8 -*-
# wasp_backup/inside_tar_archiver.py
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

import os
import uuid
import tempfile

from wasp_general.verify import verify_type, verify_value
from wasp_general.os.linux.lvm import WLogicalVolume
from wasp_general.os.linux.mounts import WMountPoint

from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta
from wasp_backup.archiver import WBasicInsideTarArchiveCreator


class WInsideTarArchiveCreator(WBasicInsideTarArchiveCreator):

	@verify_type('paranoid', archive_path=str, cipher=(WBackupCipher, None))
	@verify_type('paranoid', compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	@verify_type('paranoid', io_write_rate=(float, int, None))
	@verify_type(backup_sources=str, abs_path=bool)
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_write_rate=lambda x: x is None or x > 0)
	@verify_value(backup_sources=lambda x: len(x) > 0)
	def __init__(
		self, archive_path, logger, *backup_sources, compression_mode=None, cipher=None, stop_event=None,
		io_write_rate=None, abs_path=False
	):
		WBasicInsideTarArchiveCreator.__init__(
			self, archive_path, logger, compression_mode=compression_mode, cipher=cipher, stop_event=stop_event,
			io_write_rate=io_write_rate
		)

		self.__backup_sources = list(backup_sources)
		self.__abs_path = abs_path
		self.__last_file = None

	def backup_sources(self):
		return self.__backup_sources.copy()

	def abs_path(self):
		return self.__abs_path

	def last_file(self):
		return self.__last_file

	def inside_filename(self):
		result = WBackupMeta.Archive.__basic_inside_file_name__ + '.tar'
		compression_mode = self.compression_mode()
		if compression_mode is not None:
			result += '.' + compression_mode.value
		return result

	def archive(self):
		self.__last_file = None
		WBasicInsideTarArchiveCreator.archive(self)

	def _populate_archive(self, tar_archive):
		def last_file_tracking(tarinfo):
			self.__last_file = tarinfo.name
			return tarinfo

		for entry in self.backup_sources():
			if self.abs_path() is True:
				entry = os.path.abspath(entry)
			tar_archive.add(entry, recursive=True, filter=last_file_tracking)

	def meta(self):
		result = WBasicInsideTarArchiveCreator.meta(self)
		result.update({
			WBackupMeta.Archive.MetaOptions.inside_tar: True,
			WBackupMeta.Archive.MetaOptions.archived_files: self.backup_sources(),
		})
		return result


class WLVMArchiveCreator(WInsideTarArchiveCreator):

	@verify_type('paranoid', archive_path=str, backup_sources=str)
	@verify_type('paranoid', compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	@verify_type('paranoid', cipher=(WBackupCipher, None), io_write_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	@verify_value('paranoid', io_write_rate=lambda x: x is None or x > 0)
	@verify_type(sudo=bool)
	def __init__(
		self, archive_path, logger, *backup_sources, compression_mode=None, sudo=False, cipher=None, stop_event=None,
		io_write_rate=None
	):
		WInsideTarArchiveCreator.__init__(
			self, archive_path, logger, *backup_sources, compression_mode=compression_mode, cipher=cipher,
			stop_event=stop_event, io_write_rate=io_write_rate, abs_path=True
		)
		self.__sudo = sudo
		self.__logical_volume_uuid = None
		self.__snapshot = False

	def sudo(self):
		return self.__sudo

	@verify_type(disable_snapshot=bool, snapshot_force=bool, snapshot_size=(int, float, None), mount_directory=(str, None))
	@verify_type(mount_fs=(str, None), mount_options=(list, tuple, set, None))
	def archive(
		self, disable_snapshot=False, snapshot_force=False, snapshot_size=None, mount_directory=None,
		mount_fs=None, mount_options=None
	):
		if disable_snapshot is True and snapshot_force is True:
			raise ValueError('Conflict flags "disable_snapshot" and "snapshot_force" was specified')

		self.__logical_volume_uuid = None
		self.__snapshot = False

		logical_volume = None
		backup_sources = self.backup_sources()

		if len(backup_sources) == 0:
			if snapshot_force is True:
				raise RuntimeError('Unable to create snapshot for empty archive')
			else:
				WBasicInsideTarArchiveCreator.archive(self)
				return

		if disable_snapshot is False:
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
			WBasicInsideTarArchiveCreator.archive(self)
			return

		if snapshot_size is None:
			snapshot_size = WBackupMeta.LVMSnapshot.__default_snapshot_size__

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
					suffix=snapshot_suffix,
					prefix=WBackupMeta.LVMSnapshot.__mount_directory_prefix__
				)
				remove_directory = True
			if mount_options is None:
				mount_options = []
			mount_options.insert(0, 'ro')

			WMountPoint.mount(
				snapshot_volume.volume_path(), mount_directory, fs=mount_fs, options=mount_options,
				sudo=self.sudo()
			)
			directory_mounted = True

			mount_directory_length = len(mount_directory)
			for i in range(len(backup_sources)):
				backup_sources[i] = backup_sources[i][mount_directory_length:]

			os.chdir(mount_directory)
			WInsideTarArchiveCreator.archive(self)

		except Exception:
			self.__logical_volume_uuid = None
			self.__snapshot = False
			raise
		finally:
			os.chdir(current_cwd)

			if directory_mounted is True:
				WMountPoint.umount(snapshot_volume.volume_path(), sudo=self.sudo())

			if remove_directory is True:
				os.removedirs(mount_directory)

			if snapshot_volume is not None:
				snapshot_volume.remove_volume()

	def meta(self):
		meta = WInsideTarArchiveCreator.meta(self)
		meta[WBackupMeta.Archive.MetaOptions.snapshot_used] = self.__snapshot
		meta[WBackupMeta.Archive.MetaOptions.original_lv_uuid] = \
			self.__logical_volume_uuid if self.__logical_volume_uuid is not None else ''
		return meta
