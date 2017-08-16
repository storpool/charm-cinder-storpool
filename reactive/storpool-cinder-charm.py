from __future__ import print_function

import json
import platform
import time

from charms import reactive
from charms.reactive import helpers

from charmhelpers.core import hookenv

sp_node = platform.node()

def rdebug(s):
	with open('/tmp/storpool-charms.log', 'a') as f:
		print('{tm} [cinder-charm] {s}'.format(tm=time.ctime(), s=s), file=f)

@reactive.when('storage-backend.configure')
@reactive.when_not('storpool-presence.configure')
def no_presence():
	rdebug('no StorPool presence data yet')
	hookenv.status_set('maintenance', 'waiting for the StorPool block presence data')

@reactive.when_not('storage-backend.configure')
@reactive.when('storpool-presence.configure')
def no_presence():
	rdebug('no Cinder hook yet')
	hookenv.status_set('maintenance', 'waiting for the Cinder relation')

@reactive.when_not('storage-backend.configure')
@reactive.when_not('storpool-presence.configure')
def no_presence():
	rdebug('no Cinder hook or StorPool presence data yet')
	hookenv.status_set('maintenance', 'waiting for the Cinder relation and the StorPool presence data')

@reactive.when('storage-backend.configure')
@reactive.when('storpool-presence.configure')
def storage_backend_configure(hk):
	rdebug('configuring cinder and stuff')
	service = hookenv.service_name()
	data = {
		'cinder': {
			'/etc/cinder/cinder.conf': {
				'sections': {
					service: [
						('volume_backend_name', service),
						('volume_driver', 'cinder.volume.drivers.storpool.StorPoolDriver'),
						('storpool_template', 'hybrid-r3'),
					],
				},
			},
		},
	}
	rdebug('configure setting some data: {data}'.format(data=data))
	rdebug('now looking for our Cinder relation...')
	rel_ids = hookenv.relation_ids('storage-backend')
	rdebug('got rel_ids {rel_ids}'.format(rel_ids=rel_ids))
	for rel_id in rel_ids:
		rdebug('- trying for {rel_id}'.format(rel_id=rel_id))
		hookenv.relation_set(rel_id,
			backend_name=hookenv.service_name(),
			subordinate_configuration=json.dumps(data),
			stateless=True)
		rdebug('  - looks like we did it for {rel_id}'.format(rel_id=rel_id))
	rdebug('seemed to work, did it not')
	hookenv.status_set('active', 'the StorPool Cinder backend should be up and running')

@reactive.hook('storage-backend-relation-joined')
def got_cinder_conn():
	rdebug('got a cinder connection')
	reactive.set_state('storage-backend.configure')

@reactive.hook('storage-backend-relation-changed')
def got_cinder_conn():
	rdebug('updated a cinder connection')
	reactive.set_state('storage-backend.configure')
