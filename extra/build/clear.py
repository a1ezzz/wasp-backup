#!/usr/bin/python3

import os
import shutil


script_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))

build_dirs = ('pypi_build', 'debian_build', )


if __name__ == '__main__':

	cleared = False
	for dir_name in build_dirs:
		dir_path = os.path.abspath(os.path.join(script_dir, dir_name))
		if os.path.exists(dir_path):
			print('Removing directory: %s' % dir_path)
			shutil.rmtree(dir_path)
			cleared = True

	if cleared is False:
		print('Nothing to clear')

