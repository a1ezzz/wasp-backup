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

import os
import tarfile
import uuid
import tempfile

from wasp_general.verify import verify_type, verify_value
from wasp_general.os.linux.lvm import WLogicalVolume
from wasp_general.os.linux.mounts import WMountPoint
from wasp_general.io import WWriterChainLink, WResponsiveWriter

from wasp_launcher.core import WAppsGlobals

from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta
from wasp_backup.io import WTarArchivePatcher, WArchiverThrottling, WArchiverHashCalculator, WArchiverAESCipher
from wasp_backup.io import WArchiverChain


"""

archiving:

(lvm snapshot)
	|
	|
	| ->  tar( + compression) -> (encryption ->) hashing
							|
							|-> single tar archive -> (throttling ->) file object
							|                               |
archive meta information -------------------------------|     (may be automatic split because of target fs limitation?)
											|
											|-> splitter object
												|
												| -> file object 1
												|
												| -> file object 2
												|
												...
												| -> file object n
"""


class WBackupTarArchiver:

	@verify_type(archive_path=str, backup_sources=str, cipher=(WBackupCipher, None))
	@verify_type(compression_mode=(WBackupMeta.Archive.CompressionMode, None), io_write_rate=(float, int, None))
	@verify_value(archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	@verify_value(io_write_rate=lambda x: x is None or x > 0)
	def __init__(
		self, archive_path, *backup_sources, compression_mode=None, cipher=None, stop_event=None,
		io_write_rate=None
	):
		self.__archive_path = archive_path
		self.__backup_sources = list(backup_sources)
		self.__compression_mode = compression_mode
		self.__cipher = cipher
		self.__stop_event = stop_event
		self.__io_write_rate = io_write_rate
		self.__writer_chain = None
		self.__last_file = None

	def archive_path(self):
		return self.__archive_path

	def backup_sources(self):
		return self.__backup_sources.copy()

	def compression_mode(self):
		return self.__compression_mode

	def cipher(self):
		return self.__cipher

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event

	def io_write_rate(self):
		return self.__io_write_rate

	def last_file(self):
		return self.__last_file

	def archiving_details(self):
		if self.__writer_chain is not None:
			return self.__writer_chain.status()

	def tar_mode(self):
		compress_mode = self.compression_mode()
		return 'w:%s' % (compress_mode.value if compress_mode is not None else '')

	@verify_type(abs_path=bool)
	def _archive(self, abs_path=True):
		self.__last_file = None

		archive_path = self.archive_path()
		inside_archive_name = WBackupMeta.Archive.inside_archive_filename(self.compression_mode())
		backup_tar = WTarArchivePatcher(archive_path, inside_archive_name=inside_archive_name)

		chain = [
			backup_tar,
			WWriterChainLink(WArchiverThrottling, write_limit=self.io_write_rate()),
			WWriterChainLink(WArchiverHashCalculator)
		]

		cipher = self.cipher()
		if cipher is not None:
			chain.append(WWriterChainLink(WArchiverAESCipher, cipher))

		stop_event = self.stop_event()
		if stop_event is not None:
			chain.append(WWriterChainLink(WResponsiveWriter, stop_event))

		self.__writer_chain = WArchiverChain(*chain)

		def last_file_tracking(tarinfo):
			self.__last_file = tarinfo.name
			return tarinfo

		try:
			try:

				tar = tarfile.open(fileobj=self.__writer_chain, mode=self.tar_mode())
				for entry in self.backup_sources():
					if abs_path is True:
						entry = os.path.abspath(entry)
					tar.add(entry, recursive=True, filter=last_file_tracking)

				self.__writer_chain.flush()
				self.__writer_chain.write(backup_tar.padding(backup_tar.inside_archive_padding()))
			finally:
				self.__writer_chain.flush()
				self.__writer_chain.close()

			WAppsGlobals.log.info(
				'Archive "%s" was created successfully. Patching archive with meta...' % archive_path
			)
			backup_tar.patch(self.meta())
			WAppsGlobals.log.info('Archive "%s" was successfully patched' % archive_path)

		except WResponsiveWriter.WriterTerminated:
			os.unlink(archive_path)
			WAppsGlobals.log.error(
				'Unable to create archive "%s" - task terminated, changes discarded' % archive_path
			)
			return
		except Exception:
			os.unlink(archive_path)
			WAppsGlobals.log.error('Unable to create archive "%s". Changes discarded' % archive_path)
			raise


	def archive(self):
		self._archive()

	def meta(self):
		result = {
			WBackupMeta.Archive.MetaOptions.inside_archive_filename:
				WBackupMeta.Archive.inside_archive_filename(self.compression_mode()),
			WBackupMeta.Archive.MetaOptions.archived_files:
				self.backup_sources()
		}
		if self.__writer_chain is not None:
			result.update(self.__writer_chain.meta())
		return result


class WLVMBackupTarArchiver(WBackupTarArchiver):

	__default_snapshot_size__ = 0.1
	__mount_directory_prefix__ = 'wasp-backup-'

	@verify_type('paranoid', archive_path=str, backup_sources=str)
	@verify_type('paranoid', compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	@verify_type('paranoid', cipher=(WBackupCipher, None), io_write_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	@verify_value('paranoid', io_write_rate=lambda x: x is None or x > 0)
	@verify_type(sudo=bool)
	def __init__(
		self, archive_path, *backup_sources, compression_mode=None, sudo=False, cipher=None, stop_event=None,
		io_write_rate=None
	):
		WBackupTarArchiver.__init__(
			self, archive_path, *backup_sources, compression_mode=compression_mode, cipher=cipher,
			stop_event=stop_event, io_write_rate=io_write_rate
		)
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
				snapshot_volume.volume_path(), mount_directory, fs=mount_fs, options=mount_options,
				sudo=self.sudo()
			)
			directory_mounted = True

			mount_directory_length = len(mount_directory)
			for i in range(len(backup_sources)):
				backup_sources[i] = backup_sources[i][mount_directory_length:]

			os.chdir(mount_directory)
			self._archive(abs_path=False)

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
		meta = WBackupTarArchiver.meta(self)
		meta[WBackupMeta.Archive.MetaOptions.snapshot_used] = self.__snapshot
		meta[WBackupMeta.Archive.MetaOptions.original_lv_uuid] = \
			self.__logical_volume_uuid if self.__logical_volume_uuid is not None else ''
		return meta


"""
__openssl_mode_re__ = re.compile('aes-([0-9]+)-(.+)')
bits, mode = __openssl_mode_re__.search(cipher.lower()).groups()
key_size = int(int(bits) / 8)
mode = 'AES-%s' % mode.upper()
'''

'''
import hmac
import hashlib
import Crypto.Protocol.KDF
fn = lambda x,y: hmac.new(x,msg=y,digestmod=hashlib.sha256).digest()
salt = b'\x01\x02\x03\x04\x05\x06\x07\x08'
Crypto.Protocol.KDF.PBKDF2('password', salt, prf=fn)

echo -en password | nettle-pbkdf2 -i 1000 -l 16 --hex-salt 0102030405060708
openssl enc -aes-256-cbc -d -in 1.tar.gz.aes -out 1.tar.gz -K \
	"c057f2deac4cba660f5463b8346ee67961948a598e0f4f72e7ad46d2ffeecd39" -iv "4084a32c07fb808e8dfc679c3cde6480" \
	-nosalt -nopad
"""
