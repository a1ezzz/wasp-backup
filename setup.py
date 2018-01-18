
import os
import json
from setuptools import setup, find_packages

__root_dir__ = os.path.abspath(os.path.dirname(__file__))
__package_json_file_name__ = 'package.json'


def find_package_file():
	result = None
	for root, dirs, files in os.walk(__root_dir__):
		if __package_json_file_name__ in files:
			if result is not None:
				raise RuntimeError('Multiple package files was found')
			result = root
	return result


def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()


def requirements(pypi_data):
	result = read('requirements.txt').splitlines()
	if 'exclude_requirements' in pypi_data:
		return list(set(result).difference(set(pypi_data['exclude_requirements'])))
	return result


if __name__ == "__main__":

	with open(os.path.join(find_package_file(), __package_json_file_name__)) as f:
		package_data = json.load(f)

	pypi_data = package_data['pypi']

	setup(
		name=package_data['package'],
		version=package_data['numeric_version'],
		author=package_data['author'],
		author_email=package_data['author_email'],
		maintainer=package_data['maintainer'],
		maintainer_email=package_data['maintainer_email'],
		description=package_data['brief_description'],
		license=package_data['license'],
		keywords=pypi_data['keywords'],
		url=package_data['homepage'],
		packages=find_packages(),
		include_package_data= \
			pypi_data['include_package_data'] if 'include_package_data' in pypi_data else True,
		long_description=read(package_data['readme_file']),
		classifiers=pypi_data['classifiers'],
		install_requires=requirements(pypi_data),
		zip_safe=pypi_data['zip_safe'] if 'zip_safe' in pypi_data else False,
		scripts=package_data['scripts'] if 'scripts' in package_data else [],
		extras_require=pypi_data['extra_require'] if 'extra_require' in pypi_data else {}
	)
