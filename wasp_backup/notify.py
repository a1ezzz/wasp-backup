# -*- coding: utf-8 -*-
# wasp_backup/notify.py
#
# Copyright (C) 2018 the wasp-backup authors and contributors
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
import shlex
import sys
import tempfile
from wasp_backup.core import WBackupMeta, WBackupMetaProvider


def notify(notify_data, notify_app, encode_strict_cls=None):
	first_fork_pid = os.fork()
	if first_fork_pid == 0:
		second_fork_pid = os.fork()
		if second_fork_pid == 0:
			binary_meta = WBackupMetaProvider.encode_meta(
				notify_data, strict_cls=encode_strict_cls
			)

			meta_tempfile = tempfile.NamedTemporaryFile(delete=False)
			meta_tempfile.write(binary_meta)
			meta_tempfile.close()

			app_tokens = shlex.split(notify_app)

			os.execvpe(
				app_tokens[0],
				app_tokens,
				{WBackupMeta.__notification_env_var_name__: meta_tempfile.name}
			)
		else:
			sys.exit(0)
	else:
		os.waitpid(first_fork_pid, 0)
