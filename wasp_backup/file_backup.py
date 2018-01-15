# -*- coding: utf-8 -*-
# wasp_backup/file_backup.py
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

from enum import Enum

from wasp_general.command.enhanced import WCommandArgumentDescriptor

from wasp_backup.cipher import WBackupCipher
from wasp_backup.inside_tar_archiver import WLVMArchiveCreator
from wasp_backup.command_common import __common_args__, WCreateBackupCommand


class WFileBackupCommand(WCreateBackupCommand):

	class SnapshotUsage(Enum):
		auto = 'auto'
		forced = 'forced'
		disabled = 'disabled'

	__command__ = 'file-backup'
	__description__ = 'create backup archive of files and directories'

	__arguments__ = (
		__common_args__['backup-archive'],
		__common_args__['input-files'],
		WCommandArgumentDescriptor(
			'sudo', flag_mode=True,
			help_info='use "sudo" command for privilege promotion. "sudo" may be used for snapshot '
			'creation, partition mounting and un-mounting'
		),
		WCommandArgumentDescriptor(
			'snapshot', help_info='whether to create snapshot before backup or not. '
			'One of: "auto" (backup will try to make snapshot for input files), '
			'"forced" (if snapshot can not be created - backup will fail), '
			'"disabled" (backup will not try to create a snapshot)',
			casting_helper=WCommandArgumentDescriptor.EnumArgumentHelper(SnapshotUsage),
			default_value=SnapshotUsage.auto.value
		),
		WCommandArgumentDescriptor(
			'snapshot-volume-size', meta_var='fraction_size',
			help_info='snapshot volume size as fraction of original volume size',
			casting_helper=WCommandArgumentDescriptor.FloatArgumentCastingHelper(
				validate_fn=lambda x: x > 0
			)
		),
		WCommandArgumentDescriptor(
			'snapshot-mount-dir', meta_var='mount_path',
			help_info='path where snapshot volume should be mount. It is random directory by default'
		),
		__common_args__['compression'],
		__common_args__['password'],
		__common_args__['cipher_algorithm'],
		__common_args__['io-write-rate'],
		__common_args__['copy-to'],
		__common_args__['copy-fail'],
		__common_args__['notify-app']
	)

	def _exec(self, command_arguments, **command_env):
		compression_mode = None
		if 'compression' in command_arguments.keys():
			compression_mode = command_arguments['compression']

		cipher = None
		if 'password' in command_arguments:
			cipher = WBackupCipher(
				command_arguments['cipher_algorithm'], command_arguments['password']
			)

		snapshot_size = None
		if 'snapshot-volume-size' in command_arguments.keys():
			snapshot_size = command_arguments['snapshot-volume-size']

		snapshot_mount_dir = None
		if 'snapshot-mount-dir' in command_arguments.keys():
			snapshot_mount_dir = command_arguments['snapshot-mount-dir']

		io_write_rate = None
		if 'io-write-rate' in command_arguments.keys():
			io_write_rate = command_arguments['io-write-rate']

		backup_archive = command_arguments['backup-archive']

		archiver = WLVMArchiveCreator(
			backup_archive, self.logger(), *command_arguments['input-files'],
			compression_mode=compression_mode, sudo=command_arguments['sudo'], cipher=cipher,
			io_write_rate=io_write_rate, stop_event=self.stop_event()
		)

		snapshot_disabled = (command_arguments['snapshot'] == WFileBackupCommand.SnapshotUsage.disabled)
		snapshot_force = (command_arguments['snapshot'] == WFileBackupCommand.SnapshotUsage.forced)

		self.set_archiver(archiver)
		return self._create_backup(
			command_arguments,
			disable_snapshot=snapshot_disabled,
			snapshot_force=snapshot_force,
			snapshot_size=snapshot_size,
			mount_directory=snapshot_mount_dir
		)
