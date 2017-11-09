#!/usr/bin/python3

"""
A set of unit tests for the cinder-storpool charm.
"""

import os
import sys
import unittest

import json
import mock

from charmhelpers.core import hookenv

root_path = os.path.realpath('.')
if root_path not in sys.path:
    sys.path.insert(0, root_path)

lib_path = os.path.realpath('unit_tests/lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from spcharms import config as spconfig


class MockReactive(object):
    def r_clear_states(self):
        self.states = set()

    def __init__(self):
        self.r_clear_states()

    def set_state(self, name):
        self.states.add(name)

    def remove_state(self, name):
        if name in self.states:
            self.states.remove(name)

    def is_state(self, name):
        return name in self.states

    def r_get_states(self):
        return set(self.states)

    def r_set_states(self, states):
        self.states = set(states)


initializing_config = None


class MockConfig(object):
    def r_clear_config(self):
        global initializing_config
        saved = initializing_config
        initializing_config = self
        self.override = {}
        self.changed_attrs = {}
        self.config = {}
        initializing_config = saved

    def __init__(self):
        self.r_clear_config()

    def r_set(self, key, value, changed):
        self.override[key] = value
        self.changed_attrs[key] = changed

    def get(self, key, default):
        return self.override.get(key, self.config.get(key, default))

    def changed(self, key):
        return self.changed_attrs.get(key, False)

    def __getitem__(self, name):
        # Make sure a KeyError is actually thrown if needed.
        if name in self.override:
            return self.override[name]
        else:
            return self.config[name]

    def __getattr__(self, name):
        return self.config.__getattribute__(name)

    def __setattr__(self, name, value):
        if initializing_config == self:
            return super(MockConfig, self).__setattr__(name, value)

        raise AttributeError('Cannot override the MockConfig '
                             '"{name}" attribute'.format(name=name))


r_state = MockReactive()
r_config = MockConfig()
r_env_config = MockConfig()

# Do not give hookenv.config() a chance to run at all
hookenv.config = lambda: r_env_config
spconfig.m = lambda: r_config


def mock_reactive_states(f):
    def inner1(inst, *args, **kwargs):
        @mock.patch('charms.reactive.set_state', new=r_state.set_state)
        @mock.patch('charms.reactive.remove_state', new=r_state.remove_state)
        @mock.patch('charms.reactive.helpers.is_state', new=r_state.is_state)
        def inner2(*args, **kwargs):
            return f(inst, *args, **kwargs)

        return inner2()

    return inner1


from reactive import cinder_storpool_charm as testee


TEMPLATE_NAME = 'hybrid'
SERVICE_NAME = 'cinder-storpool'
RELATION_NAME = 'storage-backend'
RELATION_ID = 'storage-backend.42'
CONFIG_DATA = {
    'cinder': {
        '/etc/cinder/cinder.conf': {
            'sections': {
                SERVICE_NAME: [
                    ('volume_backend_name',
                     SERVICE_NAME),
                    ('volume_driver',
                     'cinder.volume.drivers.storpool.StorPoolDriver'),
                    ('storpool_template',
                     TEMPLATE_NAME),
                ],
            },
        },
    },
}
CONFIG_JSON = json.dumps(CONFIG_DATA)


class TestCinderStorPoolCharm(unittest.TestCase):
    def setUp(self):
        super(TestCinderStorPoolCharm, self).setUp()
        r_state.r_clear_states()
        r_config.r_clear_config()
        r_env_config.r_clear_config()

    def do_test_no_config(self):
        """
        Make sure the charm does nothing without configuration.
        """

        r_config.r_clear_config()
        r_env_config.r_clear_config()
        r_state.r_clear_states()
        testee.configure()
        self.assertEquals(set(), r_state.r_get_states())

        # An empty string should feel the same
        r_state.r_clear_states()
        r_env_config.r_set('storpool_template', '', True)
        testee.configure()
        self.assertEquals(set(), r_state.r_get_states())

    def do_test_config(self):
        """
        Make sure the charm does something when configured.
        """
        r_config.r_clear_config()
        r_env_config.r_clear_config()
        r_env_config.r_set('storpool_template', TEMPLATE_NAME, True)
        r_state.r_clear_states()
        testee.configure()
        self.assertEquals(set(['cinder-storpool.configured']),
                          r_state.r_get_states())

    def do_test_final_configure(self, h_sname, h_relids, h_relset, h_status):
        """
        Make sure the charm sends the correct info to Cinder.
        """
        r_config.r_clear_config()
        r_env_config.r_clear_config()
        r_env_config.r_set('storpool_template', TEMPLATE_NAME, False)
        r_state.r_set_states(set(['cinder-storpool.configured']))

        h_sname.return_value = SERVICE_NAME
        h_relids.return_value = [RELATION_ID]

        testee.storage_backend_configure(None)
        self.assertEquals(set([
                              'cinder-storpool.configured',
                              'cinder-storpool.ready',
                              ]), r_state.r_get_states())

        self.assertEquals(2, h_sname.call_count)
        h_relids.assert_called_once_with(RELATION_NAME)
        h_relset.assert_called_once_with(RELATION_ID,
                                         backend_name=SERVICE_NAME,
                                         subordinate_configuration=CONFIG_JSON,
                                         stateless=True)

    @mock_reactive_states
    def test_no_config(self):
        """
        A trivial no-configuration test.
        """
        self.do_test_no_config()

    @mock_reactive_states
    def test_config(self):
        """
        A trivial no-configuration test.
        """
        self.do_test_config()

    @mock_reactive_states
    @mock.patch('charmhelpers.core.hookenv.status_set')
    @mock.patch('charmhelpers.core.hookenv.relation_set')
    @mock.patch('charmhelpers.core.hookenv.relation_ids')
    @mock.patch('charmhelpers.core.hookenv.service_name')
    def test_final_configure(self, h_sname, h_relids, h_relset, h_status):
        """
        Test the actual passing of the configuration to Cinder.
        """
        self.do_test_final_configure(h_sname, h_relids, h_relset, h_status)

    @mock_reactive_states
    @mock.patch('charmhelpers.core.hookenv.status_set')
    @mock.patch('charmhelpers.core.hookenv.relation_set')
    @mock.patch('charmhelpers.core.hookenv.relation_ids')
    @mock.patch('charmhelpers.core.hookenv.service_name')
    def test_full_lifecycle(self, h_sname, h_relids, h_relset, h_status):
        """
        Test the full lifecycle of the Cinder charm.
        """
        self.do_test_no_config()
        self.do_test_config()
        self.do_test_final_configure(h_sname, h_relids, h_relset, h_status)
