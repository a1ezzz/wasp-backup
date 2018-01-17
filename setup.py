
import os
from setuptools import setup, find_packages

from wasp_backup.version import __package_data__
__pypi_data__ = __package_data__['pypi']


def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()


def requirements():
	result = read('requirements.txt').splitlines()
	if 'exclude_requirements' in __pypi_data__:
		for name in __pypi_data__['exclude_requirements']:
			result.remove(name)
	return result


if __name__ == "__main__":
	setup(
		name=__package_data__['package'],
		version=__package_data__['numeric_version'],
		author=__package_data__['author'],
		author_email=__package_data__['author_email'],
		maintainer=__package_data__['maintainer'],
		maintainer_email=__package_data__['maintainer_email'],
		description=__package_data__['brief_description'],
		license=__package_data__['license'],
		keywords=__pypi_data__['keywords'],
		url=__package_data__['homepage'],
		packages=find_packages(),
		include_package_data=\
			__pypi_data__['include_package_data'] if 'include_package_data' in __pypi_data__ else True,
		long_description=read(__package_data__['readme_file']),
		classifiers=__pypi_data__['classifiers'],
		install_requires=requirements(),
		zip_safe=__pypi_data__['zip_safe'] if 'zip_safe' in __pypi_data__ else False,
		scripts=__package_data__['scripts'] if 'scripts' in __package_data__ else [],
		extras_require=__pypi_data__['extra_require'] if 'extra_require' in __pypi_data__ else {}
	)
