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
import json
import math
from time import mktime
from datetime import datetime

from wasp_general.verify import verify_type, verify_value
from wasp_general.io import WWriterChainLink, WReaderChainLink, WThrottlingReader, WResponsiveWriter, WResponsiveIO
from wasp_general.io import WResponsiveReader, WHashCalculationReader, WDiscardReaderResult, WReaderChain, WGzipReader
from wasp_general.io import WBzip2Reader

from wasp_backup.cipher import WBackupCipher
from wasp_backup.core import WBackupMeta
from wasp_backup.io import WMetaTarPatcher, WArchiverThrottlingWriter, WArchiverHashCalculationWriter
from wasp_backup.io import WArchiverAESCipher, WArchiverThrottlingReader
from wasp_backup.io import WArchiverWriterChain, WExtractorReaderChain, WBackupMetaProvider, WBasicArchiverIO
from wasp_backup.io import WArchiverDataCounter


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


class WBasicArchiveCreator(WBasicArchiverIO, WBackupMetaProvider):

	@verify_type('paranoid', archive_path=str, io_write_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_write_rate=lambda x: x is None or x > 0)
	@verify_type(cipher=(WBackupCipher, None), compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	def __init__(
		self, archive_path, logger, stop_event=None, io_write_rate=None, compression_mode=None,
		cipher=None
	):
		WBasicArchiverIO.__init__(self, archive_path, logger, stop_event=stop_event, io_rate=io_write_rate)
		WBackupMetaProvider.__init__(self)
		self.__compression_mode = compression_mode
		self.__cipher = cipher
		self.__writer_chain = None
		self.__last_archive_creation_time = None

	def io_write_rate(self):
		return self.io_rate()

	def compression_mode(self):
		return self.__compression_mode

	def cipher(self):
		return self.__cipher

	def file_object(self):
		return self.__writer_chain

	def archiving_details(self):
		if self.__writer_chain is not None:
			return self.__writer_chain.status()

	def inside_filename(self):
		result = WBackupMeta.Archive.__basic_inside_file_name__
		compression_mode = self.compression_mode()
		if compression_mode is not None:
			result += '.' + compression_mode.value
		return result

	def write_chain(self):
		inside_archive_name = self.inside_filename()

		chain = [
			open(self.archive_path(), mode='wb'),
			WWriterChainLink(WArchiverThrottlingWriter, write_limit=self.io_write_rate()),
			WWriterChainLink(
				WMetaTarPatcher, inside_archive_name, self, compression_mode=self.compression_mode()
			),
			WWriterChainLink(WArchiverDataCounter),
			WWriterChainLink(WArchiverHashCalculationWriter)
		]

		cipher = self.cipher()
		if cipher is not None:
			chain.append(WWriterChainLink(WArchiverAESCipher, cipher))

		stop_event = self.stop_event()
		if stop_event is not None:
			chain.append(WWriterChainLink(WResponsiveWriter, stop_event))

		return WArchiverWriterChain(*chain)

	def archive(self):
		archive_path = self.archive_path()
		self.__writer_chain = self.write_chain()
		self.__last_archive_creation_time = self.__utc_unix_time()
		archive_instance = self.__writer_chain.instance(WMetaTarPatcher)

		try:
			self.write_archive(self.__writer_chain, archive_instance)
			self.__writer_chain.flush()
			archive_instance.patch()
			self.__writer_chain.close()
			self.logger().info('Archive "%s" was created and patched successfully' % archive_path)

		except WResponsiveIO.IOTerminated:
			os.unlink(archive_path)
			self.logger().error(
				'Unable to create archive "%s" - task terminated, changes discarded' % archive_path
			)
			return
		except Exception:
			os.unlink(archive_path)
			self.logger().error('Unable to create archive "%s". Changes discarded' % archive_path)
			raise

	@classmethod
	def __utc_unix_time(cls):
		utc_datetime = datetime.utcnow()
		utc_unix_time = mktime(utc_datetime.timetuple())
		return math.floor(utc_unix_time)

	def write_archive(self, fo, archive):
		pass

	def meta(self):
		result = self.__writer_chain.meta() if self.__writer_chain is not None else {}

		compression_mode = self.compression_mode()
		if compression_mode is not None:
			compression_mode = compression_mode.value

		result.update({
			WBackupMeta.Archive.MetaOptions.inside_filename: self.inside_filename(),
			WBackupMeta.Archive.MetaOptions.compression_mode: compression_mode,
			WBackupMeta.Archive.MetaOptions.creation_time: self.__last_archive_creation_time
		})
		return result


class WBasicInsideTarArchiveCreator(WBasicArchiveCreator):

	@verify_type('paranoid', archive_path=str, io_write_rate=(float, int, None))
	@verify_type('paranoid', cipher=(WBackupCipher, None), compression_mode=(WBackupMeta.Archive.CompressionMode, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_write_rate=lambda x: x is None or x > 0)
	def __init__(self, archive_path, logger, compression_mode=None, cipher=None, stop_event=None, io_write_rate=None):
		WBasicArchiveCreator.__init__(
			self, archive_path, logger, stop_event=stop_event, io_write_rate=io_write_rate,
			compression_mode=compression_mode, cipher=cipher
		)

		self.__compression_mode = compression_mode
		self.__cipher = cipher
		self.__writer_chain = None

	def write_archive(self, fo, archive):
		tar = tarfile.open(fileobj=fo, mode='w:')
		self._populate_archive(tar)
		fo.flush()

		data_written = archive.data_written()
		padding_size = archive.record_size(data_written + (tarfile.BLOCKSIZE * 2)) - data_written
		fo.write(archive.padding(padding_size))

	def _populate_archive(self, tar_archive):
		pass


class WBasicArchiveExtractor(WBasicArchiverIO):

	@verify_type('paranoid', archive_path=str, io_read_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_read_rate=lambda x: x is None or x > 0)
	def __init__(self, archive_path, logger, stop_event=None, io_read_rate=None):
		WBasicArchiverIO.__init__(self, archive_path, logger, stop_event=stop_event, io_rate=io_read_rate)

	def io_read_rate(self):
		return self.io_rate()

	@verify_type(file_name=str)
	@verify_value(file_name=lambda x: len(x) > 0)
	def open_file(self, file_name):
		chain = [
			open(self.archive_path(), 'rb'),
			WReaderChainLink(WThrottlingReader, throttling_to=self.io_read_rate()),
		]

		stop_event = self.stop_event()
		if stop_event is not None:
			chain.append(WReaderChainLink(WResponsiveReader, stop_event))

		reader_chain = WReaderChain(*chain)

		tar = tarfile.open(fileobj=reader_chain, mode='r:')
		extracted_file = tar.extractfile(file_name)
		if extracted_file is None:
			raise RuntimeError(
				'File "%s" was not found in archive "%s"' % (file_name, self.archive_path())
			)
		return extracted_file

	def open_meta(self):
		return self.open_file(WBackupMeta.Archive.__meta_filename__)


class WArchiveIntegrityChecker(WBasicArchiveExtractor):

	@verify_type('paranoid', archive_path=str, io_read_rate=(float, int, None))
	@verify_value('paranoid', archive_path=lambda x: len(x) > 0, io_read_rate=lambda x: x is None or x > 0)
	def __init__(self, archive_path, logger, stop_event=None, io_read_rate=None):
		WBasicArchiveExtractor.__init__(self, archive_path, logger, stop_event=stop_event, io_read_rate=io_read_rate)
		self.__reader_chain = None

	def reader_chain(self):
		return self.__reader_chain

	def check_details(self):
		if self.__reader_chain is not None:
			return self.__reader_chain.status()

	def check_archive(self):
		try:
			meta_file_data = self.open_meta()
			json_raw_data = meta_file_data.read()
			meta_file_data.close()
			json_data = json.loads(json_raw_data.decode())
			inside_archive_name = json_data[WBackupMeta.Archive.MetaOptions.inside_filename.value]

			chain = [self.open_file(inside_archive_name)]

			if WBackupMeta.Archive.MetaOptions.compression_mode.value in json_data:
				compression_mode = json_data[WBackupMeta.Archive.MetaOptions.compression_mode.value]
				if compression_mode is not None:
					if compression_mode == WBackupMeta.Archive.CompressionMode.gzip.value:
						chain.append(WReaderChainLink(WGzipReader))
					elif compression_mode == WBackupMeta.Archive.CompressionMode.bzip2.value:
						chain.append(WReaderChainLink(WBzip2Reader))
					else:
						raise RuntimeError(
							'Unsupported compression mode spotted: "%s"' % compression_mode
						)

			chain.extend([
				WReaderChainLink(
					WHashCalculationReader,
					json_data[WBackupMeta.Archive.MetaOptions.hash_algorithm.value]
				),
				WReaderChainLink(WArchiverThrottlingReader),
				WReaderChainLink(WDiscardReaderResult)
			])
			self.__reader_chain = WExtractorReaderChain(*chain)
			self.__reader_chain.read()
			calc_instance = self.__reader_chain.instance(WHashCalculationReader)
			self.__reader_chain.close()

			original_hash = json_data[WBackupMeta.Archive.MetaOptions.hash_value.value].upper()
			calculated_hash = calc_instance.hexdigest().upper()
			return original_hash == calculated_hash, original_hash, calculated_hash
		except WResponsiveIO.IOTerminated:
			self.logger().error(
				'Unable to check archive "%s" - task terminated' % self.archive_path()
			)
			return
		finally:
			self.__reader_chain = None


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
