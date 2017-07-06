#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Original fetched from https://gitlab.com/a1ezzz/ansible-common/raw/master/roles/common/files/pybackup.py

import sys
import os
import json
import argparse
import tarfile
import hashlib
import subprocess
import uuid
import logging
import logging.handlers
import tempfile
import re


class B4cku9Logger(logging.Logger):

	log = None
	verbose = False

	def __init__(self):
		logging.Logger.__init__(self, 'PyBackup')
		
		self.__syslog = logging.handlers.SysLogHandler(address = '/dev/log')
		self.__syslog.setLevel(logging.DEBUG)
		self.addHandler(self.__syslog)

		self.__stdout = logging.StreamHandler(sys.stdout)
		self.__stdout.setLevel(logging.DEBUG)
		self.addHandler(self.__stdout)

	@staticmethod
	def setup(verbose=False):
		if B4cku9Logger.log is None:
			B4cku9Logger.log = B4cku9Logger()

	def info(self, msg, *args, **kwargs):
		if 'verbose' not in kwargs or kwargs['verbose'] == B4cku9Logger.verbose:
			logger_kwargs = kwargs
			if 'verbose' in logger_kwargs:
				logger_kwargs.pop('verbose')
			logging.Logger.info(self, msg, *args, **logger_kwargs)

	def error(self, msg, *args, **kwargs):
		if 'verbose' not in kwargs or kwargs['verbose'] == B4cku9Logger.verbose:
			logger_kwargs = kwargs
			if 'verbose' in logger_kwargs:
				logger_kwargs.pop('verbose')
			logging.Logger.error(self, msg, *args, **logger_kwargs)

	def warn(self, msg, *args, **kwargs):
		if 'verbose' not in kwargs or kwargs['verbose'] == B4cku9Logger.verbose:
			logger_kwargs = kwargs
			if 'verbose' in logger_kwargs:
				logger_kwargs.pop('verbose')
			logging.Logger.warn(self, msg, *args, **logger_kwargs)


class B4cku9TarArchiver:

	meta_suffix = '.meta'

	def __init__(self, output, *backup, mode=None):
		self.tar_filename = output
		self.backup = list(backup)
		self.mode = 'w|%s' % (mode if mode is not None else '')
		self.filter = self.verbose_filter if B4cku9Logger.verbose is True else None

	@classmethod
	def verbose_filter(cls, tarinfo):
		B4cku9Logger.log.info('Compressing: %s', tarinfo.name, verbose=True)
		return tarinfo

	def archive(self):
		self._archive()		

	def _archive(self, abs_path=True):
		tar = tarfile.open(name=self.tar_filename, mode=self.mode)
		for entry in self.backup:
			if abs_path is True:
				entry = os.path.abspath(entry)
			tar.add(entry, recursive=True, filter=self.filter)
		tar.close()

	def meta(self):
		return {'md5sum': self.md5sum(self.tar_filename)}
	
	def write_meta(self):
		meta_file_name = self.tar_filename + self.meta_suffix
		B4cku9Logger.log.info('Creating meta file: %s' % meta_file_name)
		meta_file = open(meta_file_name, 'w')
		meta_data = self.meta()
		meta_file.write(json.dumps(meta_data))
		meta_file.close()

		if B4cku9Logger.verbose is True:
			meta_data_keys = list(meta_data.keys())
			meta_data_keys.sort()
			for key in meta_data_keys:
				B4cku9Logger.log.info(
					'Archive meta information. %s: %s', str(key), str(meta_data[key]), verbose=True
				)

	@classmethod
	def md5sum(cls, filename, blocksize=65536):
		hash = hashlib.md5()
		with open(filename, "rb") as f:
			for block in iter(lambda: f.read(blocksize), b""):
				hash.update(block)
		return hash.hexdigest()
		


class B4cku9LVMTarArchiver(B4cku9TarArchiver):

	mount_files = '/proc/mounts'

	class MountPoint:

		def __init__(self, raw):
			parsed_raw = raw.split()
			self.device = parsed_raw[0]
			self.device_name = os.path.basename(self.device)
			self.path = parsed_raw[1]
			self.fs = parsed_raw[2]
			self.options = parsed_raw[3]
			self.dump = parsed_raw[4]
			self.pass_fsck = parsed_raw[5]
			
		@classmethod
		def current_mounts(cls, new_mount, *current_mounts):
			result = []
			for previous_mp in current_mounts:
				if previous_mp.path.startswith(new_mount.path) is True:
					continue
				result.append(previous_mp)
			result.append(new_mount)
			return result

	class LV:
		
		def __init__(self, mp, lv_name, lv_uuid):
			self.mount_point = mp
			self.lv_name = lv_name
			self.lv_uuid = lv_uuid
			self.snapshot_suffix = None
			self.snapshot_directory = None
			self.snapshot_mounted = False

			lvdisplay_cmd = 'lvdisplay -c %s' % self.lv(lv_name)
			status, specs = subprocess.getstatusoutput(lvdisplay_cmd)
			if status == 0:
				specs = specs.split(':')
				self.lv_path = specs[0]
				self.lv_short_name = os.path.basename(self.lv_path)
				self.vg_name = specs[1]
				self.lv_access = specs[2]
				self.lv_status = specs[3]
				self.lv_internal_number = specs[4]
				self.lv_opens = specs[5]
				self.lv_size = specs[6]
				self.lv_extents = specs[7]
				self.lv_allocated_extents = specs[8]
				self.lv_allocation_policy = specs[9]
				self.lv_read_ahead = specs[10]
				self.lv_dev_major = specs[11]
				self.lv_dev_minor = specs[12]

				self.vg = B4cku9LVMTarArchiver.VG(self.vg_name)
			else:
				B4cku9Logger.log.error('Command failed: %s', lvdisplay_cmd, verbose=True)
				raise RuntimeError('"lvdisplay" command execution failed (status - %i)' % status)

		@classmethod
		def lv(cls, lv_name):
			return '/dev/mapper/%s' % lv_name

		def create_snapshot(self, snapshot_size, snapshot_suffix):
			size = int(int(self.lv_extents) * int(self.vg.vg_extent_size) * (snapshot_size / 100))
			snapshot_name = self.lv_short_name + snapshot_suffix
			B4cku9Logger.log.info('Creating snapshot: %s (size: %iK)', snapshot_name, size)

			lvcreate_cmd = 'lvcreate -L %iK -s -n %s -p r %s' % (size, snapshot_name, self.lv_path)
			status, output = subprocess.getstatusoutput(lvcreate_cmd)

			if status != 0:
				B4cku9Logger.log.error('Command failed: %s', lvcreate_cmd, verbose=True)
				raise RuntimeError('"lvcreate" command execution failed (status - %i)' % status)

			self.snapshot_suffix = snapshot_suffix
			B4cku9Logger.log.info('Snapshot created successfully', verbose=True)

		def remove_snapshot(self):
			if self.snapshot_suffix is None:
				B4cku9Logger.log.info('No snapshot created - nothing to remove', verbose=True)
				return

			snapshot_name = self.lv_path + self.snapshot_suffix
			B4cku9Logger.log.info('Removing snapshot: %s', snapshot_name)
			
			lvremove_cmd = 'lvremove -f %s' % snapshot_name
			status, output = subprocess.getstatusoutput(lvremove_cmd)

			if status != 0:
				B4cku9Logger.log.warn('Command failed: %s', lvremove_cmd, verbose=True)
				B4cku9Logger.log.warn('Unable to remove created snapshot')
		
		def mount(self, mount_directory=None):
			if mount_directory is None:
				mount_directory = tempfile.mkdtemp(suffix=self.snapshot_suffix, prefix='pybackup-')
				B4cku9Logger.log.info('Temporary mount directory created: %s', mount_directory, verbose=True)
			self.snapshot_directory = mount_directory

			snapshot_name = self.lv_path + self.snapshot_suffix
			mount_cmd = 'mount -o ro %s %s' % (snapshot_name, self.snapshot_directory)
			status, output = subprocess.getstatusoutput(mount_cmd)

			if status != 0:
				B4cku9Logger.log.error('Command failed: %s', mount_cmd, verbose=True)
				raise RuntimeError('"mount" command execution failed (status - %i)' % status)

			self.snapshot_mounted = True

		def umount(self, mount_directory=None):
			if self.snapshot_mounted is False:
				B4cku9Logger.log.info("Snapshot wasn't mounted. Skipping unmount", verbose=True)
			else:
				umount_cmd = 'umount %s' % self.snapshot_directory
				status, output = subprocess.getstatusoutput(umount_cmd)

				if status != 0:
					B4cku9Logger.log.warn('Command failed: %s', umount_cmd, verbose=True)
					B4cku9Logger.log.warn('Unable to unmount snapshot')
				else:
					B4cku9Logger.log.info("Snapshot unmounted from: %s", self.snapshot_directory, verbose=True)

			if mount_directory is None:
				os.removedirs(self.snapshot_directory)
				B4cku9Logger.log.info('Temporary mount directory removed', verbose=True)

		def snapshot_corrupted(self):
			snapshot_name = self.lv_path + self.snapshot_suffix
			snapshot_check_cmd = 'lvs %s -o snap_percent --noheadings' % snapshot_name
			status, output = subprocess.getstatusoutput(snapshot_check_cmd)

			if status != 0:
				B4cku9Logger.log.warn('Command failed: %s', snapshot_check_cmd, verbose=True)
				B4cku9Logger.log.warn('Unable to check snapshot state')
			else:
				snapshot_allocation = float(output.strip().replace(',','.',1))
				B4cku9Logger.log.info('Snapshot allocation: %f%%', snapshot_allocation, verbose=True)
				return snapshot_allocation > 99

	class VG:
		
		def __init__(self, vg_name):
			vgdisplay_cmd = 'vgdisplay -c %s' % vg_name
			status, specs = subprocess.getstatusoutput(vgdisplay_cmd)
			if status == 0:
				specs = specs.split(':')
				self.vg_name = specs[0]
				self.vg_access = specs[1]
				self.vg_status = specs[2]
				self.vg_internal_number = specs[3]
				self.vg_max_lv = specs[4]
				self.vg_current_lv = specs[5]
				self.vg_opened_lv = specs[6]
				self.vg_max_lv_size = specs[7]
				self.vg_max_phy_vols = specs[8]
				self.vg_current_phy_vols = specs[9]
				self.vg_actual_phy_vols = specs[10]
				self.vg_size = specs[11]
				self.vg_extent_size = specs[12]
				self.vg_total_phy_extents = specs[13]
				self.vg_allocated_phy_extents = specs[14]
				self.vg_free_phy_extents = specs[15]
				self.vg_uuid = specs[16]
			else:
				B4cku9Logger.log.error('Command failed: %s', vgdisplay_cmd, verbose=True)
				raise RuntimeError('"vgdisplay" command execution failed (status - %i)' % status)

	def __init__(self, output, *backup, mode=None):
		B4cku9TarArchiver.__init__(self, output, *backup, mode=mode)
		mp = self.mount_point(*backup)
		self.lv = None
		if mp is not None:
			B4cku9Logger.log.info(
				'Backup block device found: %s', mp.device, verbose=True
			)
			
			try:
				self.lv = self.lv_device(mp) 
				B4cku9Logger.log.info(
					'Logical volume found: %s', self.lv.lv_path, verbose=True
				)
			except RuntimeError as e:
				B4cku9Logger.log.error('LVM inspection failed: ' + str(e))				
		if self.lv is None:
			B4cku9Logger.log.warn('Snapshot will be skipped.')
			B4cku9Logger.log.info("Logical volume wasn't found", verbose=True)

	@classmethod	
	def mounts(cls):
		result = []
		with open(B4cku9LVMTarArchiver.mount_files) as f:
			for single_mount in f:
				mp = B4cku9LVMTarArchiver.MountPoint(single_mount)
				result = B4cku9LVMTarArchiver.MountPoint.current_mounts(mp, *result)
		return result
	
	@classmethod
	def mount_point(cls, *backup):
		# checks if backup sources resides on a single lv and return it

		mounts = {}
		for m in cls.mounts():
			mounts[m.path] = m

		points = list(mounts.keys())
		points.sort(key=lambda x: len(x), reverse=True)

		check_point = None
		for single_backup in backup:
			single_backup = os.path.abspath(single_backup)
			current_point = None
			for i in range(len(points)):
				p = points[i]
				if single_backup.startswith(p) is True:
					if current_point is None:
						current_point = p
						for j in range(i):
							if points[j].startswith(single_backup):
								B4cku9Logger.log.warn('Backup source "%s" has inside mounts (%s and %s)', single_backup, p, points[j])
								return
			if current_point is None:
				B4cku9Logger.log.warn(
					'No suitable mount point found for: %s', single_backup
				)
				return
			elif check_point is None:
				check_point = current_point
			elif current_point != check_point:
				B4cku9Logger.log.warn('Different files resides on different mounts')
				return

		if check_point is not None:
			return mounts[check_point]
		else:
			B4cku9Logger.log.warn('No suitable mount point found')
	
	@classmethod
	def lv_device(cls, mp):

		uuid_file = '/sys/block/%s/dm/uuid' % mp.device_name
		name_file = '/sys/block/%s/dm/name' % mp.device_name
		lv_uuid = open(uuid_file).read().strip()
		if lv_uuid.startswith('LVM-') is True:
			lv_name = open(name_file).read().strip()
			dm_path = os.path.realpath(mp.device)
			lv_path = os.path.realpath(B4cku9LVMTarArchiver.LV.lv(lv_name))

			if dm_path == lv_path:
				return B4cku9LVMTarArchiver.LV(mp, lv_name, lv_uuid)
			else:
				B4cku9Logger.log.warn(
					'LVM device detection sanity check failed =( (original: %s, detected: %s)', dm_path, lv_path
				)
		else:
			B4cku9Logger.log.warn('non-LVM block device: %s', mp.device_name)

	def archive(self):
		if self.lv is None or self.lv.snapshot_mounted is False:
			B4cku9TarArchiver.archive(self)
			return

		current_cwd = os.getcwd()
		try:
			mount_path_len = len(self.lv.mount_point.path)
			for i in range(len(self.backup)):
				self.backup[i] = self.backup[i][mount_path_len:]

			os.chdir(self.lv.snapshot_directory)
			self._archive(abs_path=False)
		finally:
			os.chdir(current_cwd)

	def meta(self):
		meta = B4cku9TarArchiver.meta(self)
		if self.lv is None or self.lv.snapshot_mounted is False:
			return meta

		meta['snapshot'] = True
		meta['lv_uuid'] = self.lv.lv_uuid
		meta['original_mount'] = self.lv.mount_point.path
		return meta


class B4cku9Utility:
	
	def __init__(self):
		self.output_file = None

		self.parser = self.new_parser()
		self.args = self.parser.parse_args(sys.argv[1:])
		if self.args.verbose is True:
			B4cku9Logger.verbose=True
		
	@classmethod
	def new_parser(cls):
		parser = argparse.ArgumentParser(
			description='This utility helps to backup files. It is able to create snapshot if possible (if required).'
		)

		parser.add_argument(
			'-s', '--source', action='store', nargs='+',
			required=True, type=str, metavar='input-files',
			dest='sources', help='source files/directories to backup'
		)

		parser.add_argument(
			'-o', '--output', action='store', nargs=1,
			required=True, type=str, metavar='output-archive',
			dest='output_archive', help='target archive file'
		)
		parser.add_argument(
			'-l', '--lvm', action='store_true', dest='lvm', help='specifies, that snapshot is required prior to backup (lvm should be able to flush filesystem buffers during snapshot creation like it does with ext3/4 fs)'
		)
		parser.add_argument(
			'--snapshot-size', action='store', nargs=1, type=float, metavar='snapshot-size', default=5, dest='snapshot_size', help='specifies allocation snapshot size as percentages of target logical volume. (default is 5%%)'
		)
		parser.add_argument(
			'--snapshot-mount-dir', action='store', nargs=1, type=str, metavar='mount-dir', dest='snapshot_mount_dir', help='specifies directory, where snapshot will be mounted default is a temporary directory in "/tmp")'
		)
		parser.add_argument(
			'-m', '--meta', action='store_true', dest='meta', help='create meta file (same as "output-archive" but with "%s" suffix)' % B4cku9LVMTarArchiver.meta_suffix
		)

		parser.add_argument(
			'-v', '--verbose', action='store_true', dest='verbose', help='make utility more verbose'
		)

		compress_group = parser.add_mutually_exclusive_group()
		compress_group.add_argument(
			'-g', '--gzip', action='store_true', default=True, dest='gzip', help='compress tar file with gzip'
		)
		compress_group.add_argument(
			'-b', '--bzip', action='store_true', dest='bzip', help='compress tar file with bzip'
		)

		return parser

	def backup(self):
		output = self.args.output_archive[0]
		mode=('bz2' if self.args.bzip is True else 'gz')

		B4cku9Logger.log.info('Backing up to: %s', output)
		archiver = B4cku9LVMTarArchiver(output, *self.args.sources, mode=mode)
		if archiver.lv is None and self.args.lvm is True:
			B4cku9Logger.log.error('Unable to create backup due to snapshot creation fail')
			B4cku9Logger.log.error('Backup failed')
			sys.exit(-1)
		
		snapshot_suffix = '-snapshot-%s' % str(uuid.uuid4())
		try:
			if archiver.lv is not None:
				try:
					archiver.lv.create_snapshot(self.args.snapshot_size, snapshot_suffix)
					archiver.lv.mount(self.args.snapshot_mount_dir)
				except RuntimeError as e:
					B4cku9Logger.log.error('Unable to create snapshot: ' + str(e))
					if self.args.lvm is True:
						B4cku9Logger.log.error('Snapshot was selected. Backup failed')
						sys.exit(-1)

			archiver.archive()
			if self.args.meta is True:
				archiver.write_meta()

			if archiver.lv is not None and archiver.lv.snapshot_mounted is True:
				if archiver.lv.snapshot_corrupted() is True:
					os.unlink(output)
					if self.args.meta is True:
						os.unlink(output + archiver.lv.meta_suffix)
					B4cku9Logger.log.error('Snapshot was corrupted (100% full). Backup deleted')
					sys.exit(-1)

		finally:
			if archiver.lv is not None:
				archiver.lv.umount(self.args.snapshot_mount_dir)
				archiver.lv.remove_snapshot()
		
		B4cku9Logger.log.info('Backup completed successfully')


if __name__ == '__main__':
	B4cku9Logger.setup()
	utility = B4cku9Utility()
	utility.backup()

