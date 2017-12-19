# -*- coding: utf-8 -*-
# wasp_backup/io.py
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
import json
import time
import tarfile
import grp
import math
import pwd
from datetime import datetime
from abc import ABCMeta, abstractmethod

from wasp_general.verify import verify_type
from wasp_general.io import WAESWriter, WHashCalculationWriter, WWriterChain, WThrottlingWriter, WWriterChainLink
from wasp_general.io import WReaderChain, WThrottlingReader, WReaderChainLink
from wasp_general.cli.formatter import data_size_formatter


from wasp_backup.core import WBackupMeta, WArchiverIOMetaProvider, WArchiverIOStatusProvider


class WTarArchivePatcher(io.BufferedWriter):

	def __init__(self, archive_path, inside_archive_name):
		io.BufferedWriter.__init__(self, open(archive_path, mode='wb', buffering=0))
		self.__inside_archive_size = 0
		self.__archive_path = archive_path
		self.__inside_archive_name = inside_archive_name

		self.write(self.tar_header(self.inside_archive_name()))

	def archive_path(self):
		return self.__archive_path

	def inside_archive_name(self):
		return self.__inside_archive_name

	def write(self, b):
		self.__inside_archive_size += len(b)
		return io.BufferedWriter.write(self, b)

	def inside_archive_padding(self):
		archive_padding_size = self.record_size(self.__inside_archive_size - tarfile.BLOCKSIZE)
		return archive_padding_size - (self.__inside_archive_size - tarfile.BLOCKSIZE)

	def patch(self, meta_data):
		if self.closed is False:
			raise RuntimeError('!')

		result_archive_size = os.stat(self.archive_path()).st_size
		inside_archive_size = result_archive_size - tarfile.BLOCKSIZE
		if inside_archive_size != self.record_size(inside_archive_size):
			raise RuntimeError('Logic error!')
		inside_archive_header = self.tar_header(self.inside_archive_name(), size=inside_archive_size)

		f = open(self.archive_path(), 'rb+')
		f.seek(0, os.SEEK_SET)
		f.write(inside_archive_header)

		meta_data = self.process_meta(meta_data)
		json_data = json.dumps(meta_data).encode()

		if len(json_data) > WBackupMeta.Archive.__maximum_meta_filesize__:
			raise RuntimeError('Meta data corrupted - too big')

		meta_header = self.tar_header(WBackupMeta.Archive.__meta_filename__, size=len(json_data))
		result_archive_size += len(meta_header)
		result_archive_size += len(json_data)

		f.seek(0, os.SEEK_END)
		f.write(meta_header)
		f.write(json_data)

		meta_padding = self.block_size(len(json_data))
		delta = meta_padding - len(json_data)
		result_archive_size += delta
		f.write(self.padding(delta))

		archive_end_padding = tarfile.BLOCKSIZE * 2
		result_archive_size += archive_end_padding
		f.write(self.padding(archive_end_padding))

		delta = self.record_size(result_archive_size) - result_archive_size

		f.write(self.padding(delta))
		f.close()

	@classmethod
	def process_meta(cls, meta):
		result = {}
		for meta_key, meta_value in meta.items():
			if isinstance(meta_key, WBackupMeta.Archive.MetaOptions) is False:
				raise TypeError('Invalid meta key spotted')
			result[meta_key.value] = meta_value
		return result

	@classmethod
	def tar_header(cls, name, size=None):
		tar_header = tarfile.TarInfo(name=name)
		if size is not None:
			tar_header.size = size
		tar_header.mtime = time.mktime(datetime.now().timetuple())
		tar_header.mode = WBackupMeta.Archive.__file_mode__
		tar_header.type = tarfile.REGTYPE
		tar_header.uid = os.getuid()
		tar_header.gid = os.getgid()
		tar_header.uname = pwd.getpwuid(tar_header.uid).pw_name
		tar_header.gname = grp.getgrgid(tar_header.gid).gr_name

		return tar_header.tobuf()

	@classmethod
	def align_size(cls, size, chunk_size):
		result = divmod(size, chunk_size)
		return (result[0] if result[1] == 0 else (result[0] + 1)) * chunk_size

	@classmethod
	def record_size(cls, size):
		return cls.align_size(size, tarfile.RECORDSIZE)

	@classmethod
	def block_size(cls, size):
		return cls.align_size(size, tarfile.BLOCKSIZE)

	@classmethod
	def padding(cls, padding_size):
		return tarfile.NUL * padding_size if padding_size > 0 else b''


class WArchiverHashCalculationWriter(WHashCalculationWriter, WArchiverIOMetaProvider):

	def __init__(self, raw):
		WHashCalculationWriter.__init__(self, raw, WBackupMeta.Archive.__hash_generator_name__)
		WArchiverIOMetaProvider.__init__(self)

	def meta(self):
		return {
			WBackupMeta.Archive.MetaOptions.hash_algorithm:
				WBackupMeta.Archive.__hash_generator_name__,
			WBackupMeta.Archive.MetaOptions.hash_value:
				self.hexdigest()
		}


class WArchiverAESCipher(WAESWriter, WArchiverIOMetaProvider):

	def __init__(self, raw, cipher):
		WAESWriter.__init__(self, raw, cipher.aes_cipher())
		WArchiverIOMetaProvider.__init__(self)
		self.__meta = cipher.meta()

	def meta(self):
		return self.__meta


class WArchiverThrottlingWriter(WThrottlingWriter, WArchiverIOMetaProvider, WArchiverIOStatusProvider):

	def __init__(self, raw, write_limit=None):
		WThrottlingWriter.__init__(self, raw, throttling_to=write_limit)
		WArchiverIOMetaProvider.__init__(self)
		WArchiverIOStatusProvider.__init__(self)

	def meta(self):
		return {
			WBackupMeta.Archive.MetaOptions.io_write_rate: math.ceil(self.rate())
		}

	def status(self):
		result = 'Write rate: %s/sec\n' % data_size_formatter(math.ceil(self.rate()))
		result += 'Bytes processed: %i' % self.bytes_processed()
		return result


class WArchiverThrottlingReader(WThrottlingReader, WArchiverIOStatusProvider):

	def __init__(self, raw, read_limit=None):
		WThrottlingReader.__init__(self, raw, throttling_to=read_limit)
		WArchiverIOStatusProvider.__init__(self)

	def status(self):
		result = 'Read rate: %s/sec\n' % data_size_formatter(math.ceil(self.rate()))
		result += 'Bytes processed: %i' % self.bytes_processed()
		return result


class WArchiverStatus(metaclass=ABCMeta):

	def meta(self):
		result = {}
		for link in self:
			if isinstance(link, WArchiverIOMetaProvider) is True:
				result.update(link.meta())
		return result

	def status(self):
		result = []
		for link in self:
			if isinstance(link, WArchiverIOStatusProvider) is True:
				result.append(link.status())
		if len(result) > 0:
			return '\n'.join(result)

	@abstractmethod
	def __iter__(self):
		raise NotImplementedError('This method is abstract')


class WArchiverWriterChain(WWriterChain, WArchiverStatus):

	@verify_type('paranoid', links=WWriterChainLink)
	def __init__(self, last_io_obj, *links):
		WWriterChain.__init__(self, last_io_obj, *links)
		WArchiverStatus.__init__(self)


class WExtractorReaderChain(WReaderChain, WArchiverStatus):

	@verify_type('paranoid', links=WReaderChainLink)
	def __init__(self, last_io_obj, *links):
		WReaderChain.__init__(self, last_io_obj, *links)
		WArchiverStatus.__init__(self)
