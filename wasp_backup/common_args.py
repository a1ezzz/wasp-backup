# -*- coding: utf-8 -*-
# wasp_backup/common_args.py
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

from wasp_general.verify import verify_type
from wasp_general.command.enhanced import WCommandArgumentDescriptor
from wasp_general.crypto.aes import WAESMode

from wasp_backup.core import WBackupMeta


class WCompressionArgumentHelper(WCommandArgumentDescriptor.ArgumentCastingHelper):

	def __init__(self):
		WCommandArgumentDescriptor.ArgumentCastingHelper.__init__(
			self, casting_fn=self.cast_string
		)

	@staticmethod
	@verify_type(value=str)
	def cast_string(value):
		value = value.lower()
		if value == 'gzip':
			return WBackupMeta.Archive.CompressionMode.gzip
		elif value == 'bzip2':
			return WBackupMeta.Archive.CompressionMode.bzip2
		elif value == 'disabled':
			return
		else:
			raise ValueError('Invalid compression value')


def cipher_name_validation(cipher_name):
	try:
		if WAESMode.parse_cipher_name(cipher_name) is not None:
			return True
	except ValueError:
		pass
	return False


__common_args__ = {
	'backup-archive': WCommandArgumentDescriptor(
		'backup-archive', required=True, multiple_values=False, meta_var='archive_path',
		help_info='backup file path'
	),

	'input-program': WCommandArgumentDescriptor(
		'input-program', required=True, multiple_values=False, meta_var='program_command',
		help_info='program which output will be backed up'
	),

	'compression': WCommandArgumentDescriptor(
		'compression', meta_var='compression_type',
		help_info='compression option. One of: "gzip", "bzip2" or "disabled". It is disabled by default',
		casting_helper=WCompressionArgumentHelper()
	),

	'password': WCommandArgumentDescriptor(
		'password', meta_var='encryption_password',
		help_info='password to encrypt backup. Backup is not encrypted by default'
	),

	'cipher_algorithm': WCommandArgumentDescriptor(
		'cipher_algorithm', meta_var='algorithm_name',
		help_info='cipher that will be used for encrypt (backup will not be encrypted if password was not '
		'set). It is "AES-256-CBC" by default',
		casting_helper=WCommandArgumentDescriptor.StringArgumentCastingHelper(
			validate_fn=cipher_name_validation
		),
		default_value='AES-256-CBC'
	),

	'io-write-rate': WCommandArgumentDescriptor(
		'io-write-rate', meta_var='maximum writing rate',
		help_info='use this parameter to limit disk I/O load (bytes per second). You can use '
		'suffixes like "K" for kibibytes, "M" for mebibytes, "G" for gibibytes, "T" for tebibytes for '
		'convenience ', casting_helper=WCommandArgumentDescriptor.DataSizeArgumentHelper()
	)
}
