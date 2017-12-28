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

import tarfile
import math
import io
import os
import gzip
import bz2
import time
import pwd
import grp
from datetime import datetime

from abc import ABCMeta, abstractmethod

from wasp_general.verify import verify_type, verify_value
from wasp_general.io import WAESWriter, WHashCalculationWriter, WWriterChain, WThrottlingWriter, WWriterChainLink
from wasp_general.io import WReaderChain, WThrottlingReader, WReaderChainLink, WDiscardWriterResult
from wasp_general.cli.formatter import data_size_formatter

from wasp_backup.core import WBackupMeta, WBackupMetaProvider, WArchiverIOStatusProvider


class WTarPatcher(io.BufferedWriter):

	__default_tar_mode__ = int('440', base=8)

	def __init__(
		self, archive, inside_file_name, patch_header=True, patch_tail=False, compression_mode=None
	):
		self.__original_archive = \
			open(archive, mode='wb', buffering=0) if isinstance(archive, str) is True else archive

		io.BufferedWriter.__init__(self, WDiscardWriterResult(self.__original_archive))

		self.__start_position = self.__original_archive.tell()
		self.__final_position = None
		self.__compression_writer = None

		if patch_header is True:
			self.__original_archive.write(self.tar_header(inside_file_name))

		self.__compression_mode = compression_mode
		if self.__compression_mode is not None:
			if self.__compression_mode == WBackupMeta.Archive.CompressionMode.gzip:
				archive = gzip.GzipFile(fileobj=self.__original_archive)
				self.__compression_writer = archive

			elif self.__compression_mode == WBackupMeta.Archive.CompressionMode.bzip2:
				archive = bz2.BZ2File(self.__original_archive, mode='wb')
				self.__compression_writer = archive
			else:
				raise RuntimeError('Invalid compression mode spotted')

		self.__inside_file_name = inside_file_name
		self.__patch_header = patch_header
		self.__patch_tail = patch_tail

		self.__data_written = 0

	def original_archive(self):
		return self.__original_archive

	def start_position(self):
		return self.__start_position

	def final_position(self):
		return self.__final_position

	def compression_mode(self):
		return self.__compression_mode

	def inside_file_size(self):
		final_position = self.final_position()
		if final_position is None:
			self.flush()
			if self.__compression_writer is not None:
				self.__compression_writer.flush()
			original_archive = self.original_archive()
			original_archive.flush()
			original_archive.seek(0, os.SEEK_END)
			final_position = self.__original_archive.tell()

		result = final_position - self.start_position()
		if self.patch_header() is True:
			result -= tarfile.BLOCKSIZE
		return result

	def inside_file_name(self):
		return self.__inside_file_name

	def patch_header(self):
		return self.__patch_header

	def patch_tail(self):
		return self.__patch_tail

	def data_written(self):
		return self.__data_written

	def write(self, b):
		self.__data_written += len(b)
		writer = self.__compression_writer if self.__compression_writer is not None else self.__original_archive
		writer.write(b)
		return len(b)

	def close(self):
		if self.__compression_writer is not None:
			self.__compression_writer.close()
		self.__original_archive.close()
		io.BufferedWriter.close(self)

	def patch(self):
		if self.__compression_writer is not None:
			self.__compression_writer.flush()
			self.__compression_writer.close()

		self.__original_archive.flush()
		self.__original_archive.seek(0, os.SEEK_END)
		self.__final_position = self.__original_archive.tell()

		if self.patch_tail():
			self._apply_tail_patch()

		if self.patch_header() is True:
			self._apply_header_patch()

	def alignment_padding(self):
		return self.block_size(self.data_written()) - self.data_written()

	def _apply_tail_patch(self):
		file_size = self.inside_file_size() + (tarfile.BLOCKSIZE * 2)
		if self.patch_header() is True:
			file_size += tarfile.BLOCKSIZE

		delta = self.record_size(file_size) - file_size
		self.__original_archive.write(self.padding(delta))

	def _apply_header_patch(self):
		tar_header = self.tar_header(self.inside_file_name(), size=self.inside_file_size())
		self.__original_archive.seek(self.start_position(), os.SEEK_SET)
		self.__original_archive.write(tar_header)

	@classmethod
	def tar_info(cls, name, size=None):
		tar_info = tarfile.TarInfo(name=name)
		if size is not None:
			tar_info.size = size
		tar_info.mtime = time.mktime(datetime.now().timetuple())
		tar_info.mode = cls.__default_tar_mode__
		tar_info.type = tarfile.REGTYPE
		tar_info.uid = os.getuid()
		tar_info.gid = os.getgid()
		tar_info.uname = pwd.getpwuid(tar_info.uid).pw_name
		tar_info.gname = grp.getgrgid(tar_info.gid).gr_name
		return tar_info

	@classmethod
	def tar_header(cls, name, size=None):
		return cls.tar_info(name, size=size).tobuf()

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


class WMetaTarPatcher(WTarPatcher):

	def __init__(self, archive_path, inside_archive_name, meta_provider, compression_mode=None):
		WTarPatcher.__init__(
			self, archive_path, inside_archive_name, patch_tail=True, compression_mode=compression_mode
		)
		self.__meta_provider = meta_provider

	def meta_provider(self):
		return self.__meta_provider

	def _apply_tail_patch(self):
		original_archive = self.original_archive()
		inside_file_size = original_archive.tell() - self.start_position()
		inside_data_block_delta = self.block_size(inside_file_size) - inside_file_size
		original_archive.write(self.padding(inside_data_block_delta))
		inside_file_size += inside_data_block_delta

		meta_provider = self.meta_provider()
		meta_data = meta_provider.encode_meta(meta_provider.meta(), strict_cls=WBackupMeta.Archive.MetaOptions)

		if len(meta_data) > WBackupMeta.Archive.__maximum_meta_file_size__:
			raise RuntimeError('Meta data corrupted - too big')

		meta_header = self.tar_header(WBackupMeta.Archive.__meta_filename__, size=len(meta_data))
		original_archive.write(meta_header)
		inside_file_size += len(meta_header)

		original_archive.write(meta_data)
		inside_file_size += len(meta_data)

		meta_padding = self.block_size(len(meta_data)) - len(meta_data)
		inside_file_size += meta_padding
		original_archive.write(self.padding(meta_padding))

		delta = self.record_size(inside_file_size + (tarfile.BLOCKSIZE * 2)) - inside_file_size
		original_archive.write(self.padding(delta))

	@classmethod
	def process_meta(cls, meta):
		result = {}
		for meta_key, meta_value in meta.items():
			if isinstance(meta_key, WBackupMeta.Archive.MetaOptions) is False:
				raise TypeError('Invalid meta key spotted')
			result[meta_key.value] = meta_value
		return result


class WArchiverHashCalculationWriter(WHashCalculationWriter, WBackupMetaProvider):

	def __init__(self, raw):
		WHashCalculationWriter.__init__(self, raw, WBackupMeta.Archive.__hash_generator_name__)
		WBackupMetaProvider.__init__(self)

	def meta(self):
		return {
			WBackupMeta.Archive.MetaOptions.hash_algorithm:
				WBackupMeta.Archive.__hash_generator_name__,
			WBackupMeta.Archive.MetaOptions.hash_value:
				self.hexdigest()
		}


class WArchiverAESCipher(WAESWriter, WBackupMetaProvider):

	def __init__(self, raw, cipher):
		WAESWriter.__init__(self, raw, cipher.aes_cipher())
		WBackupMetaProvider.__init__(self)
		self.__meta = cipher.meta()

	def meta(self):
		return self.__meta


class WArchiverThrottlingWriter(WThrottlingWriter, WBackupMetaProvider, WArchiverIOStatusProvider):

	def __init__(self, raw, write_limit=None):
		WThrottlingWriter.__init__(self, raw, throttling_to=write_limit)
		WBackupMetaProvider.__init__(self)
		WArchiverIOStatusProvider.__init__(self)

	def meta(self):
		return {
			WBackupMeta.Archive.MetaOptions.io_write_rate: math.ceil(self.rate())
		}

	def status(self):
		result = 'Write rate: %s/sec\n' % data_size_formatter(math.ceil(self.rate()))
		result += 'Bytes processed: %i' % self.bytes_processed()
		return result


class WArchiverDataCounter(WThrottlingWriter, WBackupMetaProvider):

	def __init__(self, raw):
		WThrottlingWriter.__init__(self, raw)
		WBackupMetaProvider.__init__(self)

	def meta(self):
		return {
			WBackupMeta.Archive.MetaOptions.uncompressed_archive_size: self.bytes_processed()
		}


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
			if isinstance(link, WBackupMetaProvider) is True:
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


class WBasicArchiverIO:

	@verify_type(archive_path=str, io_rate=(float, int, None))
	@verify_value(archive_path=lambda x: len(x) > 0, io_rate=lambda x: x is None or x > 0)
	def __init__(self, archive_path, logger, stop_event=None, io_rate=None):
		self.__archive_path = archive_path
		self.__logger = logger
		self.__stop_event = stop_event
		self.__io_rate = io_rate

	def archive_path(self):
		return self.__archive_path

	def logger(self):
		return self.__logger

	def io_rate(self):
		return self.__io_rate

	def stop_event(self, value=None):
		if value is not None:
			self.__stop_event = value
		return self.__stop_event
