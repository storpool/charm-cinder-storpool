#!/usr/bin/python

import mock


class FunnyException(Exception):
    pass


config = mock.Mock()
error = mock.Mock()
error.StorPoolNoConfigException = FunnyException
error.StorPoolPackageInstallException = FunnyException
error.StorPoolNoCGroupsException = FunnyException
error.StorPoolException = FunnyException
osi = mock.Mock()
repo = mock.Mock()
service_hook = mock.Mock()
states = mock.Mock()
status = mock.Mock()
utils = mock.Mock()
