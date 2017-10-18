# -*- coding: utf-8 -*-
# wasp_backup/cipher.py
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

from wasp_general.crypto.aes import WAES, WAESMode, WZeroPadding
from wasp_general.crypto.kdf import WPBKDF2
from wasp_general.crypto.hmac import WHMAC

from wasp_backup.core import WBackupMeta


class WBackupCipher:

	__pbkdf2_iterations_count__ = 10000
	__hmac_hash_generator_name__ = 'SHA256'

	def __init__(self, cipher_name, password):
		self.__cipher_name = cipher_name
		aes_key_size, aes_mode = WAESMode.parse_cipher_name(cipher_name)
		init_seq_length = WAESMode.init_sequence_length(aes_key_size, aes_mode)
		kdf = WPBKDF2(
			password, derived_key_length=init_seq_length,
			hmac=WHMAC(self.__hmac_hash_generator_name__), iterations_count=self.__pbkdf2_iterations_count__
		)
		self.__salt = kdf.salt()
		self.__aes = WAES(WAESMode(aes_key_size, aes_mode, kdf.derived_key(), padding=WZeroPadding()))

	def cipher_name(self):
		return self.__cipher_name

	def salt(self):
		return self.__salt

	def aes_cipher(self):
		return self.__aes

	def meta(self):
		salt = ''
		for salt_byte in self.salt():
			salt += "{:02x}".format(salt_byte)

		return {
			WBackupMeta.Archive.MetaOptions.cipher_algorithm:
				self.cipher_name(),
			WBackupMeta.Archive.MetaOptions.pbkdf2_salt:
				salt,
			WBackupMeta.Archive.MetaOptions.pbkdf2_iterations_count:
				self.__pbkdf2_iterations_count__,
			WBackupMeta.Archive.MetaOptions.pbkdf2_prf:
				('HMAC-%s' % self.__hmac_hash_generator_name__)
		}
