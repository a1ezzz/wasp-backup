#!/usr/bin/python3

import os
import sys


script_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))

pypy_build_dir_name = 'pypi_build'
pypy_build_dir = os.path.join(script_dir, pypy_build_dir_name)

clone_programm_name = 'clone.py'
clone_programm = os.path.join(script_dir, clone_programm_name)

python_interpr = 'python3'

suggested_repo = ('pypi', 'test')


if __name__ == '__main__':
	os.system('%s --clear --target %s' % (clone_programm, pypy_build_dir))
	os.chdir(pypy_build_dir)
	print('Building package')
	os.system('%s setup.py sdist' % python_interpr)

	if len(sys.argv) > 1:
		repo = sys.argv[1]
		if repo not in suggested_repo:
			print('Warning. May be wrong repository was specified. Default repositories are: %s' % ', '.join(suggested_repo))
		print('Uploading to "%s"' % repo)
		os.system('twine upload -s dist/*.tar.gz -r %s' % repo)

