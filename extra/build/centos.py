#!/usr/bin/python3

import os
import re
import shutil
from os.path import abspath


script_dir = os.path.dirname(__file__)
root_dir = abspath(os.path.join(script_dir, '..', '..'))

centos_pkg_dir_name = 'centos_pkg'
centos_pkg_dir = abspath(os.path.join(script_dir, centos_pkg_dir_name))

centos_build_dir_name = 'centos_build'
centos_build_dir = abspath(os.path.join(script_dir, centos_build_dir_name))

clone_program_name = 'clone.py'
clone_program = abspath(os.path.join(script_dir, clone_program_name))

rpmbuild_required_directories = ('BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS', 'PACKAGING')

package_dir_re = re.compile('(.+)\.spec', re.IGNORECASE)
package_version_suffix = '-0.0.2'
package_file = 'v0.0.2.tar.gz'


if __name__ == '__main__':

	for subdir in rpmbuild_required_directories:
		os.makedirs(os.path.join(centos_build_dir, subdir), exist_ok=True)

	os.chdir(centos_build_dir)

	for specfile in os.listdir(centos_pkg_dir):

		package_dir = package_dir_re.search(specfile).group(1) + package_version_suffix

		packaging_dir = os.path.join(centos_build_dir, 'PACKAGING')
		package_dir = os.path.join(packaging_dir, package_dir)
		assert(os.system('%s --clear --target %s' % (clone_program, package_dir)) == 0)

		sources_archive = os.path.join(centos_build_dir, 'SOURCES', package_file)
		assert(os.system('tar czvf %s -C %s .' % (sources_archive, packaging_dir)) == 0)

		shutil.copy(
			os.path.join(centos_pkg_dir, specfile),
			os.path.join(centos_build_dir, 'SPECS', specfile)
		)

		print('Building package by spec file: %s' % specfile)
		assert(os.system('rpmbuild -ba SPECS/%s' % specfile) == 0)
