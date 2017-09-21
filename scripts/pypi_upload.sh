#!/bin/bash

PYPI_DIR=`dirname "$0"`
PACKAGE_DIR=`dirname "$PYPI_DIR"`
REPO="$1"

if [ -z "$REPO" ]
then
	REPO="pypi"
fi

cd "$PACKAGE_DIR"
rm -rf dist/
python3 setup.py sdist
twine upload -s dist/wasp-backup-* -r "$REPO"
