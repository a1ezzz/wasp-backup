#!/usr/bin/python3

import os
import sys
import shutil
import argparse


script_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
exclude_dirs = ('extra/build',)


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
			if source_file_project_path not in exclude_dirs:
				os.mkdir(target_file)
				clone_dir(source_file, target_file, parent_dir=source_file_project_path)
			


if __name__ == '__main__':

	parser = argparse.ArgumentParser(
		description='This program clones original source code in order not to become polluted'
	)

	parser.add_argument(
		'-s', '--source', action='store', required=False, type=str, metavar='source-directory',
		dest='source', help='source directory to clone', default=root_dir
	)

	parser.add_argument(
		'-t', '--target', action='store', required=True, type=str, metavar='target-directory',
		dest='target', help='directory to clone to'
	)

	parser.add_argument(
		'-c', '--clear', action='store_true', required=False, dest='clear',
		help='whether to recreate target directory before cloning'
	)

	clone_args = parser.parse_args(sys.argv[1:])
	

	source = clone_args.source
	target = clone_args.target

	if clone_args.clear is True and os.path.exists(target) is True:
		print('Removing directory "%s"' % target)
		shutil.rmtree(target)

	if os.path.exists(target) is False:
		print('Creating directory "%s"' % target)
		os.mkdir(target)

	print('Cloning from "%s" to "%s"' % (source, target))
	clone_dir(source, target)

