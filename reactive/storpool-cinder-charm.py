from __future__ import print_function

import platform
import time

from charms import reactive
from charms.reactive import helpers

from charmhelpers.core import hookenv

sp_node = platform.node()

def rdebug(s):
	with open('/tmp/storpool-charms.log', 'a') as f:
		print('{tm} [cinder-charm] {s}'.format(tm=time.ctime(), s=s), file=f)

@reactive.hook('config-changed')
def whee():
	rdebug('wheeeeeee config-changed')
	hookenv.status_set('maintenance', 'waiting for stuff to happen') # or just ''

@reactive.when('storpool-config.available')
def get_storpool_config(hconfig):
	rdebug('apparently the storpool-config hook is available now: {h}'.format(h=hconfig))
	try:
		rdebug('let us see what this is all about')
		conf = hconfig.get_storpool_config()
		if conf is None:
			rdebug('no config yet...')
			reactive.remove_state('storpool-cinder.configure')
			reactive.remove_state('storpool-cinder.configured')
		else:
			rdebug('  - yeah, baby, we are on!')
			if helpers.data_changed('storpool-cinder.conf', conf):
				rdebug('  - and something changed, what do you know?')
				reactive.set_state('storpool-cinder.configure')
				reactive.remove_state('storpool-cinder.configured')
	except Exception as e:
		rdebug('could not examine the hook conversation: {e}'.format(e=e))

@reactive.when_not('storpool-config.available')
@reactive.when_not('storpool-cinder.whee')
def no_whee_yet():
	rdebug('hm, we do not have a storpool-config hook yet?')
	reactive.remove_state('storpool-cinder.configure')
	reactive.remove_state('storpool-cinder.configured')
	hookenv.status_set('maintenance', 'waiting for the storpool-config hook')

@reactive.when_not('storpool-config.available')
@reactive.when('storpool-cinder.whee')
def no_more_config():
	rdebug('erm, we lost the config, did we not?')
	reactive.remove_state('storpool-cinder.whee')
	reactive.remove_state('storpool-cinder.configure')
	reactive.remove_state('storpool-cinder.configured')
	hookenv.status_set('maintenance', 'waiting for the storpool-config hook to be reestablished')

@reactive.when('storpool-cinder.configure')
@reactive.when('storpool-config.available')
def configure(hconfig):
	rdebug('trying to configure the StorPool backend of the Cinder installation')
	reactive.remove_state('storpool-cinder.configure')

	rdebug('now let us pretend we actually did something with the {hconfig} hook, okay?'.format(hconfig=hconfig))

	reactive.set_state('storpool-cinder.configured')
	hookenv.status_set('active', 'up and running and configured')
