
%define _topdir %(echo $PWD)

Name:		wasp-backup-minimal
Version:	0.0.2
Release:	0
License:	GPL
Source:		https://github.com/a1ezzz/wasp-backup/archive/v0.0.2.tar.gz
URL:		https://github.com/a1ezzz/wasp-backup
Summary:	python library
Packager:	Ildar Gafurov <dev@binblob.com>

BuildArch:	noarch
BuildRequires:	python34-devel
BuildRequires:	python34-setuptools
Requires:	python34-wasp-general
Provides:	python34-wasp-backup-minimal
Conflicts:	python34-wasp-backup

%description
some python library

%prep
%autosetup

%build
%py3_build

%install
%py3_install
cp wasp-backup.py %{buildroot}%{_bindir}
rm -f %{buildroot}%{python3_sitelib}/wasp_backup/apps.py
rm -f %{buildroot}%{python3_sitelib}/wasp_backup/__pycache__/apps.cpython-34.pyc
rm -f %{buildroot}%{python3_sitelib}/wasp_backup/__pycache__/apps.cpython-34.pyo

%files
%{python3_sitelib}/*
%{_bindir}/wasp-backup.py
