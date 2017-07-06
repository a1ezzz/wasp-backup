
# TODO: replace keywords with valid value
# TODO: replace url with valid value
# TODO: populate classifiers with values from http://pypi.python.org/pypi?%3Aaction=list_classifiers
# TODO Populate requirements.txt (details: https://pip.pypa.io/en/stable/user_guide/#requirements-files)

import os
from setuptools import setup, find_packages

from wasp_backup.version import __version__, __author__, __email__, __license__


def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()


def require(fname):
	return open(fname).read().splitlines()


setup(
	name = "wasp-backup",
	version = __version__,
	author = __author__,
	author_email = __email__,
	description = "Simple file backup application",
	license = __license__,
	keywords = "",
	url = "",
	packages=find_packages(),
	include_package_data=True,
	long_description=read('README'),
	classifiers=[],
	install_requires=require('requirements.txt')
)
