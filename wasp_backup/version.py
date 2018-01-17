# -*- coding: utf-8 -*-
# wasp_backup/version.py
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

import os
import json
import subprocess


with open(os.path.join(os.path.dirname(__file__), 'package.json'), 'r') as f:
	__package_data__ = json.load(f)


def package_version():

	result = __package_data__['numeric_version']
	if __package_data__['dev_suffix'] is True:
		try:

			cwd = os.getcwd()
			try:
				os.chdir(os.path.dirname(__file__))
				# check_output is function that defined in python3 and python2
				with open(os.devnull, 'w') as f:  # python2 does not have subprocess.DEVNULL
					output = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=f)

				# check_output in python3 returns bytes, python2 - str
				if isinstance(output, bytes) is True:
					output = output.decode()
				result += '.dev%s' % output[:7]
			finally:
				os.chdir(cwd)

		except (subprocess.CalledProcessError, OSError):
			result += '--'
	return result


__author__ = __package_data__['author']
__email__ = __package_data__['author_email']
__credits__ = __package_data__['credits']
__license__ = __package_data__['license']
__copyright__ = __package_data__['copyright']
__status__ = __package_data__['status']
__version__ = package_version()
