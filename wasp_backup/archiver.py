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

import io
import os
import tarfile
import json
import uuid
import tempfile
from enum import Enum


from wasp_general.verify import verify_type, verify_value
from wasp_general.os.linux.lvm import WLogicalVolume
from wasp_general.os.linux.mounts import WMountPoint
from wasp_general.io import WAESWriter, WHashCalculationWriter, WWriterChainLink, WWriterChain, WResponsiveWriter

from wasp_launcher.core import WAppsGlobals

from wasp_backup.cipher import WBackupCipher


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


class WTarArchivePatcher(io.BufferedWriter):

	__default_meta_name__ = 'meta.json'

	def __init__(self, archive_path, inside_archive_name, meta_name=None):
		io.BufferedWriter.__init__(self, open(archive_path, mode='wb', buffering=0))
		self.__archive_path = archive_path
		self.__inside_archive_name = inside_archive_name
		self.__meta_name = meta_name if meta_name is not None else self.__default_meta_name__

		self.write(self.tar_header(self.inside_archive_name()))

	def archive_path(self):
		return self.__archive_path

	def inside_archive_name(self):
		return self.__inside_archive_name

	def meta_name(self):
		return self.__meta_name

	def patch(self, meta_data):
		if self.closed is False:
			raise RuntimeError('!')

		original_archive_size = os.stat(self.archive_path()).st_size
		archive_padding_size = self.record_size(original_archive_size - tarfile.BLOCKSIZE)
		delta = archive_padding_size - (original_archive_size - tarfile.BLOCKSIZE)
		result_archive_size = original_archive_size + delta
		inside_archive_header = self.tar_header(self.inside_archive_name(), size=archive_padding_size)

		f = open(self.archive_path(), 'rb+')
		f.seek(0, os.SEEK_SET)
		f.write(inside_archive_header)

		f.seek(0, os.SEEK_END)
		f.write(self.padding(delta))

		json_data = json.dumps(meta_data).encode()
		meta_header = self.tar_header(self.meta_name(), size=len(json_data))
		result_archive_size += len(meta_header)

		f.write(meta_header)
		f.write(json_data)

		meta_padding = self.block_size(len(json_data))
		delta = meta_padding - len(json_data)
		result_archive_size += delta
		f.write(self.padding(delta))

		archive_end_padding = tarfile.BLOCKSIZE * 2
		result_archive_size += archive_end_padding
		f.write(self.padding(archive_end_padding))

		f.write(self.padding(self.record_size(result_archive_size)))
		f.close()

	@classmethod
	def tar_header(cls, name, size=None):
		tar_header = tarfile.TarInfo(name=name)
		if size is not None:
			tar_header.size = size
		return tar_header.tobuf()

	@classmethod
	def align_size(cls, size, allign_size):
		result = divmod(size, allign_size)
		return (result[0] if result[1] == 0 else (result[0] + 1)) * allign_size

	@classmethod
	def record_size(cls, size):
		return cls.align_size(size, tarfile.RECORDSIZE)

	@classmethod
	def block_size(cls, size):
		return cls.align_size(size, tarfile.BLOCKSIZE)

	@classmethod
	def padding(cls, padding_size):
		return tarfile.NUL * padding_size if padding_size > 0 else b''


class WArchiverMeta:

	def meta(self):
		return {}


class WArchiverHashCalculator(WHashCalculationWriter, WArchiverMeta):

	def meta(self):
		return {self.hash_name(): self.hexdigest()}


class WArchiverAESCipher(WAESWriter, WArchiverMeta):

	def __init__(self, raw, cipher):
		WAESWriter.__init__(self, raw, cipher.aes_cipher())
		WArchiverMeta.__init__(self)
		self.__meta = cipher.meta()

	def meta(self):
		return self.__meta


class WArchiverChain(WWriterChain):

	def meta(self):
		result = {}
		for link in self:
			if isinstance(link, WArchiverMeta) is True:
				result.update(link.meta())
		return result


class WBackupTarArchiver:

	__meta_suffix__ = '.wb-meta'
	__default_hash_generator_name__ = 'MD5'

	class CompressMode(Enum):
		gzip = 'gz'
		bzip2 = 'bz2'

	@verify_type(archive_path=str, backup_sources=str, cipher=(WBackupCipher, None))
	@verify_value(archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	def __init__(self, archive_path, *backup_sources, compress_mode=None, cipher=None, hash_name=None, stop_event=None):
		self.__archive_path = archive_path
		self.__backup_sources = list(backup_sources)
		self.__cipher = cipher
		self.__hash_name = hash_name if hash_name is not None else self.__default_hash_generator_name__
		self.__stop_event = stop_event
		self.__writer_chain = None

		self.__compress_mode = None
		if compress_mode is not None and isinstance(compress_mode, WBackupTarArchiver.CompressMode) is False:
			raise TypeError('Invalid compress mode')
		else:
			self.__compress_mode = compress_mode

	def archive_path(self):
		return self.__archive_path

	def backup_sources(self):
		return self.__backup_sources.copy()

	def compress_mode(self):
		return self.__compress_mode

	def cipher(self):
		return self.__cipher

	def hash_name(self):
		return self.__hash_name

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event

	def tar_mode(self):
		compress_mode = self.compress_mode()
		return 'w:%s' % (compress_mode.value if compress_mode is not None else '')

	def inside_archive_name(self):
		return 'archive.tar'

	@classmethod
	def _verbose_filter(cls, tarinfo):
		WAppsGlobals.log.debug('Compressing: %s', tarinfo.name)
		return tarinfo

	@verify_type(abs_path=bool)
	def _archive(self, abs_path=True):

		backup_tar = WTarArchivePatcher(self.archive_path(), inside_archive_name=self.inside_archive_name())

		chain = [
			backup_tar,
			WWriterChainLink(WArchiverHashCalculator, self.hash_name())
		]

		cipher = self.cipher()
		if cipher is not None:
			chain.append(WWriterChainLink(WArchiverAESCipher, cipher))

		stop_event = self.stop_event()
		if stop_event is not None:
			chain.append(WWriterChainLink(WResponsiveWriter, stop_event))

		self.__writer_chain = WArchiverChain(*chain)

		try:
			tar = tarfile.open(fileobj=self.__writer_chain, mode=self.tar_mode())
			for entry in self.backup_sources():
				if abs_path is True:
					entry = os.path.abspath(entry)
				tar.add(entry, recursive=True, filter=self._verbose_filter)
		finally:
			self.__writer_chain.flush()
			self.__writer_chain.close()

		WAppsGlobals.log.debug('Archive "%s" was created successfully. Patching...' % self.archive_path())
		backup_tar.patch(self.meta())
		WAppsGlobals.log.debug('Archive "%s" was successfully patched' % self.archive_path())

	def archive(self):
		self._archive()

	def meta(self):
		result = {'archive': self.inside_archive_name()}
		if self.__writer_chain is not None:
			result.update(self.__writer_chain.meta())
		return result


class WLVMBackupTarArchiver(WBackupTarArchiver):

	__default_snapshot_size__ = 0.1
	__mount_directory_prefix__ = 'wasp-backup-'

	@verify_type('paranoid', archive_path=str, backup_sources=str)
	@verify_type('paranoid', compress_mode=(WBackupTarArchiver.CompressMode, None), cipher=(WBackupCipher, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, backup_sources=lambda x: len(x) > 0)
	@verify_type(sudo=bool)
	def __init__(self, archive_path, *backup_sources, compress_mode=None, sudo=False, cipher=None, stop_event=None):
		WBackupTarArchiver.__init__(
			self, archive_path, *backup_sources, compress_mode=compress_mode, cipher=cipher,
			stop_event=stop_event
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
		meta['snapshot'] = self.__snapshot
		meta['lv_uuid'] = self.__logical_volume_uuid if self.__logical_volume_uuid is not None else ''
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
