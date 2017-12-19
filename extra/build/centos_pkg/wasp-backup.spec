
%define _topdir %(echo $PWD)

Name:		wasp-backup
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
Requires:	python34-wasp-launcher
Provides:	python34-wasp-backup

%description
some python library

%prep
%autosetup

%build
%py3_build

%install
%py3_install

%files
%{python3_sitelib}/*
