#!/usr/bin/python3

import os
import sys


script_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))

debian_pkg_dir_name = 'debian_pkg'
debian_pkg_dir = os.path.join(script_dir, debian_pkg_dir_name)

debian_build_dir_name = 'debian_build'
debian_build_dir = os.path.join(script_dir, debian_build_dir_name)

clone_program_name = 'clone.py'
clone_program = os.path.join(script_dir, clone_program_name)

python_interpr = 'python3'


if __name__ == '__main__':
	assert(os.system('%s --clear --target %s' % (clone_program, debian_build_dir)) == 0)
	debian_dir = os.path.join(debian_build_dir, 'debian')
	assert(os.system('%s --source %s --target %s' % (clone_program, debian_pkg_dir, debian_dir)) == 0)
	os.chdir(debian_build_dir)
	print('Building package')
	assert(os.system('dpkg-buildpackage') == 0)

