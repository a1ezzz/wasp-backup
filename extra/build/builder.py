#!/usr/bin/python
# -*- coding: utf-8 -*-
# builder.py
#
# Copyright (C) 2018 the builder.py authors and contributors
# <see AUTHORS file>
#
# builder.py is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# builder.py is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with builder.py.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import sys
import shutil
import re
import json

# common vars
__script_dir__ = os.path.abspath(os.path.dirname(__file__))
__root_dir__ = os.path.abspath(os.path.join(__script_dir__, '..', '..'))
__package_json_file_name__ = 'package.json'
__requirements_file_name__ = 'requirements.txt'

# clone vars
__exclude_clone_dirs__ = ('extra/build',)

# pypi build vars
__pypi_build_dir_name__ = 'pypi_build'
__pypi_build_dir__ = os.path.join(__script_dir__, __pypi_build_dir_name__)
__pypi_suggested_repo__ = ('pypi', 'pypitest')
__pypi_built_command__ = 'sdist'

# debian build vars
__debian_build_dir_name__ = 'debian_build'
__debian_build_dir__ = os.path.join(__script_dir__, __debian_build_dir_name__)
__debian_pkg_dir_name__ = 'debian_pkg'
__debian_pkg_dir__ = os.path.join(__script_dir__, __debian_pkg_dir_name__)

# centos build vars
__centos_build_dir_name__ = 'centos_build'
__centos_build_dir__ = os.path.join(__script_dir__, __centos_build_dir_name__)
__centos_build_required_directories__ = ('BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS', 'PACKAGING')
__centos_pkg_dir_name__ = 'centos_pkg'
__centos_pkg_dir__ = os.path.join(__script_dir__, __centos_pkg_dir_name__)
__centos_spec_file_re__ = re.compile('(.+)\.spec', re.IGNORECASE)
__centos_package_version_suffix__ = '-0.0.2'
__centos_package_file__ = 'v0.0.2.tar.gz'

# clear vars
__build_dirs__ = (__pypi_build_dir_name__, __debian_build_dir_name__, __centos_build_dir_name__)


def clear_build_dirs(*dir_names):
	cleared = False
	for dir_name in dir_names:
		dir_path = os.path.abspath(os.path.join(__script_dir__, dir_name))
		if os.path.exists(dir_path):
			print('Removing directory: %s' % dir_path)
			shutil.rmtree(dir_path)
			cleared = True

	if cleared is False:
		print('Nothing to clear')


def clone_dir(source_dir, target_dir, parent_dir=None):
	if os.path.isdir(source_dir) is False:
		raise ValueError('Source path does not points to a directory: %s' % source_dir)
	if os.path.isdir(target_dir) is False:
		raise ValueError('Target path does not points to a directory: %s' % target_dir)

	print('Cloning %s' % source_dir)

	for entry in os.listdir(source_dir):
		source_file = os.path.join(source_dir, entry)
		target_file = os.path.join(target_dir, entry)

		if os.path.isfile(source_file) is True:
			os.link(source_file, target_file)
		elif os.path.isdir(source_file) is False:
			shutil.copyfile(source_file, target_file)

	for entry in os.listdir(source_dir):
		source_file = os.path.join(source_dir, entry)
		target_file = os.path.join(target_dir, entry)

		if os.path.isdir(source_file) is True:
			if parent_dir is None:
				source_file_project_path = entry
			else:
				source_file_project_path = os.path.join(parent_dir, entry)
			if source_file_project_path not in __exclude_clone_dirs__:
				os.mkdir(target_file)
				clone_dir(source_file, target_file, parent_dir=source_file_project_path)


def find_package_file(source_dir):
	result = None
	for root, dirs, files in os.walk(source_dir):
		if __package_json_file_name__ in files:
			if result is not None:
				raise RuntimeError('Multiple package files was found')
			result = root
	return result


def prepare_build_dir(build_dir, package_patch=None):
	clone_dir(__root_dir__, build_dir)

	package_json_dir = find_package_file(build_dir)
	with open(os.path.join(package_json_dir, __package_json_file_name__), 'r') as f:
		package_json = json.load(f)

	if package_patch is not None:

		with open(package_patch, 'r') as f:
			json_patch = json.load(f)

		# removing original hardlink and creating ordinary file
		build_package_json = os.path.join(package_json_dir, __package_json_file_name__)
		print('Unlinking package json: %s' % build_package_json)
		os.unlink(build_package_json)

		if "pypi" in json_patch:
			package_json["pypi"].update(json_patch.pop("pypi"))
		package_json.update(json_patch)

		with open(build_package_json, 'w') as f:
			f.write(json.dumps(package_json))

	if 'exclude_requirements' in package_json['pypi'] and len(package_json['pypi']['exclude_requirements']) > 0:
		with open(os.path.join(__root_dir__, __requirements_file_name__), mode='r') as f:
			requirements = set(f.read().splitlines())

		# removing original hardlink and creating ordinary file
		build_requirements_file = os.path.join(build_dir, __requirements_file_name__)
		print('Unlinking requirementx.txt: %s' % build_requirements_file)
		os.unlink(build_requirements_file)

		exclude_requirements = set(package_json['pypi']['exclude_requirements']).intersection(requirements)
		if len(exclude_requirements) > 0:
			with open(os.path.join(build_requirements_file), mode='w') as f:
				f.write('\n'.join(requirements.difference(exclude_requirements)))

	file_filters_re = package_json['pypi']['exclude_files_re'] if 'exclude_files_re' in package_json['pypi'] else []
	dir_filters_re = package_json['pypi']['exclude_dirs_re'] if 'exclude_dirs_re' in package_json['pypi'] else []

	if len(file_filters_re) > 0 or len(dir_filters_re) > 0:
		file_filters_re = [re.compile(x) for x in file_filters_re]
		dir_filters_re = [re.compile(x) for x in dir_filters_re]

		for root, dirs, files in os.walk(build_dir):

			if len(files) > 0 and len(file_filters_re) > 0:
				for file_name in files:
					for filter_re in file_filters_re:
						if filter_re.match(file_name) is not None:
							file_path = os.path.join(build_dir, root, file_name)
							print('Removing excluded file: %s' % file_path)
							os.unlink(file_path)

			if len(dirs) > 0 and len(dir_filters_re) > 0:
				for dir_name in dirs:
					for filter_re in dir_filters_re:
						if filter_re.match(dir_name) is not None:
							dir_path = os.path.join(build_dir, root, dir_name)
							print('Removing excluded directory: %s' % dir_path)
							shutil.rmtree(dir_path)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Utility that helps to build python packages')

	action_group = parser.add_mutually_exclusive_group(required=True)

	# clean args
	action_group.add_argument(
		'--clean', help='remove build directories and quit', action='store_true'
	)

	# clone args
	action_group.add_argument(
		'--clone', help='clone sources to a separated subdirectory', action='store_true'
	)
	parser.add_argument(
		'--clone-source', type=str, metavar='directory_path',
		help='directory with sources to clone', default=__root_dir__
	)
	parser.add_argument(
		'--clone-target', type=str, metavar='directory_path', help='directory to clone to'
	)
	parser.add_argument(
		'--clone-clear-target', help='whether to recreate target directory before cloning', action='store_true'
	)

	# common build args
	parser.add_argument(
		'--apply-package-patch', type=str, metavar='json_file',
		help='package json-file to be applied to current project json-file'
	)

	# pypi build args
	action_group.add_argument(
		'--pypi-build', help='build and upload sources to the pypi', action='store_true'
	)
	parser.add_argument(
		'--pypi-interpreter', type=str, metavar='python_interpreter',
		help='interpreter to use to build package (default - python3)', default='python3'
	)
	parser.add_argument(
		'--pypi-commands', type=str, metavar='commands', nargs='*',
		help='setup.py commands to execute (like sdist)'
	)
	parser.add_argument(
		'--pypi-repo', type=str, metavar='repo_name',
		help='pypi repository for publishing (may have value: %s)' % ', '.join(__pypi_suggested_repo__)
	)

	# debian build args
	action_group.add_argument(
		'--debian-build', help='build dpkg files from specifications', action='store_true'
	)

	# centos build args
	action_group.add_argument(
		'--centos-build', help='build rpm files from specifications', action='store_true'
	)

	args = parser.parse_args()

	if args.clean is True:
		clear_build_dirs(*__build_dirs__)
		sys.exit(0)
	elif args.clone is True:
		if args.clone_target is None:
			raise ValueError('--clone-target argument is required')

		if args.clone_clear_target is True and os.path.exists(args.clone_target) is True:
			print('Removing directory "%s"' % args.clone_target)
			shutil.rmtree(args.clone_target)

		if os.path.exists(args.clone_target) is False:
			print('Creating directory "%s"' % args.clone_target)
			os.mkdir(args.clone_target)

		print('Cloning from "%s" to "%s"' % (args.clone_source, args.clone_target))
		clone_dir(args.clone_source, args.clone_target)
		sys.exit(0)

	elif args.pypi_build is True:
		if args.pypi_commands is None and args.pypi_repo is None:
			raise ValueError('at least one argument of --pypi-commands, --pypi-repo must be specified')

		clear_build_dirs(__pypi_build_dir_name__)
		os.mkdir(__pypi_build_dir__)
		prepare_build_dir(__pypi_build_dir__, package_patch=args.apply_package_patch)
		os.chdir(__pypi_build_dir__)

		if args.pypi_commands is not None:
			commands = ' '.join(args.pypi_commands)
			assert(os.system('%s setup.py %s' % (args.pypi_interpreter, commands)) == 0)
		elif args.pypi_repo is not None:
			assert(os.system('%s setup.py %s' % (args.pypi_interpreter, __pypi_built_command__)) == 0)

		if args.pypi_repo is not None:
			print('Uploading to "%s"' % args.pypi_repo)
			assert (os.system('twine upload -s dist/*.tar.gz -r %s' % args.pypi_repo) == 0)
		sys.exit(0)

	elif args.debian_build is True:
		clear_build_dirs(__debian_build_dir_name__)
		os.mkdir(__debian_pkg_dir__)
		prepare_build_dir(__debian_pkg_dir__, package_patch=args.apply_package_patch)
		clone_dir(__debian_pkg_dir__, os.path.join(__debian_build_dir__, 'debian'))
		os.chdir(__debian_build_dir__)
		assert (os.system('dpkg-buildpackage') == 0)
		sys.exit(0)

	elif args.centos_build is True:
		clear_build_dirs(__centos_build_dir_name__)
		os.mkdir(__centos_build_dir_name__)

		for subdir in __centos_build_required_directories__:
			os.makedirs(os.path.join(__centos_build_dir__, subdir), exist_ok=True)

		os.chdir(__centos_build_dir__)

		for spec_file in os.listdir(__centos_pkg_dir__):
			centos_package_name = __centos_spec_file_re__.search(spec_file).group(1)
			centos_package_name += __centos_package_version_suffix__

			packaging_dir = os.path.join(__centos_build_dir__, 'PACKAGING')
			sources_dir = os.path.join(packaging_dir, centos_package_name)

			clear_build_dirs(sources_dir)
			os.mkdir(sources_dir)
			prepare_build_dir(sources_dir, package_patch=args.apply_package_patch)

			sources_archive = os.path.join(__centos_build_dir__, 'SOURCES', __centos_package_file__)
			assert(os.system('tar czvf %s -C %s .' % (sources_archive, packaging_dir)) == 0)

			shutil.copy(
				os.path.join(__centos_pkg_dir__, spec_file),
				os.path.join(__centos_build_dir__, 'SPECS', spec_file)
			)

			print('Building package by spec file: %s' % spec_file)
			assert(os.system('rpmbuild -ba SPECS/%s' % spec_file) == 0)

	else:
		raise ValueError('Unknown action was specified')
