# -*- coding: utf-8 -*-

import pytest
import os
from tempfile import mkdtemp

from wasp_backup.version import revision


@pytest.fixture()
def cwd(request):
	curdir = os.getcwd()

	def fin():
		os.chdir(curdir)
	request.addfinalizer(fin)


@pytest.mark.usefixtures('cwd')
def test_revision(tmpdir):
	revision()
	os.chdir(tmpdir.strpath)
	assert(revision() == '--')
