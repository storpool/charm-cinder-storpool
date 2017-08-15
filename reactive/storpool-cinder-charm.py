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

@reactive.when('storage-backend.available')
def do_configure(hk):
	rdebug('storage-backend.available, configuring the thing')
	hk.configure()
	rdebug('done configuring the storage-backend, it seems')

"""
Figure this out... the storpool-config way doesn't work.

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
			return
		rdebug('  - we have *some* configuration, checking for our node {node}'.format(node=sp_node))
		nodeconf = conf.get(sp_node, None)
		if nodeconf is None:
			rdebug('no config from our node yet...')
			reactive.remove_state('storpool-cinder.configure')
			reactive.remove_state('storpool-cinder.configured')
			return
		rdebug('  - yeah, we are on!')
		if helpers.data_changed('storpool-cinder.conf', nodeconf) or not helpers.is_state('storpool-cinder.configured'):
			rdebug('  - and something changed, what do you know?')
			reactive.set_state('storpool-cinder.configure')
			reactive.remove_state('storpool-cinder.configured')
		else:
			rdebug('  - but nothing changed for our node {node}'.format(node=sp_node))
	except Exception as e:
		rdebug('could not examine the hook conversation: {e}'.format(e=e))

@reactive.when_not('storpool-config.available')
@reactive.when_not('storpool-cinder.configured')
def no_whee_yet():
	rdebug('hm, we do not have a storpool-config hook yet?')
	hookenv.status_set('maintenance', 'waiting for the storpool-config hook')

@reactive.when('storpool-cinder.configure')
@reactive.when_not('storpool-cinder.configure')
@reactive.when('storpool-config.available')
def configure(hconfig):
	rdebug('trying to configure the StorPool backend of the Cinder installation')
	reactive.remove_state('storpool-cinder.configure')

	conf = hconfig.get_storpool_config()
	if conf is None:
		rdebug('erm, how did we get here with no configuration at all?')
	nodeconf = conf.get(sp_node, None)
	if nodeconf is None:
		rdebug('erm, how did we get here with no node configuration?')
	rdebug('now let us pretend we actually did something with the data')

	reactive.set_state('storpool-cinder.configured')
	hookenv.status_set('active', 'up and running and configured')
"""
