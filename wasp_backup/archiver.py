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

from wasp_general.verify import verify_type, verify_value
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

	@verify_type(archive_path=str, cipher=(WBackupCipher, None))
	@verify_type(compression_mode=(WBackupMeta.Archive.CompressionMode, None), io_write_rate=(float, int, None))
	@verify_value(archive_path=lambda x: len(x) > 0, io_write_rate=lambda x: x is None or x > 0)
	def __init__(self, archive_path, compression_mode=None, cipher=None, stop_event=None, io_write_rate=None):
		self.__archive_path = archive_path
		self.__compression_mode = compression_mode
		self.__cipher = cipher
		self.__stop_event = stop_event
		self.__io_write_rate = io_write_rate
		self.__writer_chain = None

	def archive_path(self):
		return self.__archive_path

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

	def archiving_details(self):
		if self.__writer_chain is not None:
			return self.__writer_chain.status()

	def tar_mode(self):
		compress_mode = self.compression_mode()
		return 'w:%s' % (compress_mode.value if compress_mode is not None else '')

	def archive(self):
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

		try:
			try:

				tar = tarfile.open(fileobj=self.__writer_chain, mode=self.tar_mode())
				self._populate_archive(tar)

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

	def _populate_archive(self, tar_archive):
		pass

	def meta(self):
		result = {
			WBackupMeta.Archive.MetaOptions.inside_archive_filename:
				WBackupMeta.Archive.inside_archive_filename(self.compression_mode()),
		}
		if self.__writer_chain is not None:
			result.update(self.__writer_chain.meta())
		return result


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
