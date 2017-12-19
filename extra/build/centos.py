#!/usr/bin/python3

import os
import sys
import shutil


script_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))

centos_pkg_dir_name = 'centos_pkg'
centos_pkg_dir = os.path.join(script_dir, centos_pkg_dir_name)

centos_build_dir_name = 'centos_build'
centos_build_dir = os.path.join(script_dir, centos_build_dir_name)

clone_program_name = 'clone.py'
clone_program = os.path.join(script_dir, clone_program_name)

rpmbuild_required_directories = ('BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS', 'PACKAGING')

python_interpr = 'python3'

package_dir = 'wasp-backup-0.0.2'
package_file = 'v0.0.2.tar.gz'


if __name__ == '__main__':

	for subdir in rpmbuild_required_directories:
		os.makedirs(os.path.join(centos_build_dir, subdir), exist_ok=True)

	specfiles = list(os.listdir(centos_pkg_dir))
	assert(len(specfiles) == 1)
	specfile = specfiles[0]
	
	shutil.copy(
		os.path.join(centos_pkg_dir, specfile),
		os.path.join(centos_build_dir, 'SPECS', specfile)
	)

	packaging_dir = os.path.join(centos_build_dir, 'PACKAGING')
	package_dir = os.path.join(packaging_dir, package_dir)
	os.system('%s --clear --target %s' % (clone_program, package_dir))
	
	sources_archive = os.path.join(centos_build_dir, 'SOURCES', package_file)
	os.system('tar czvf %s -C %s .' % (sources_archive, packaging_dir))
	
	os.chdir(centos_build_dir)
	print('Building package')
	os.system('rpmbuild -ba SPECS/%s' % specfile)
