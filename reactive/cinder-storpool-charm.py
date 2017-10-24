from __future__ import print_function

import json
import platform

from charms import reactive

from charmhelpers.core import hookenv

from spcharms import utils as sputils

sp_node = platform.node()


def rdebug(s):
    sputils.rdebug(s, prefix='cinder-charm')


@reactive.hook('config-changed')
def configure():
    rdebug('config-changed')
    config = hookenv.config()

    template = config.get('storpool_template', None)
    rdebug('and we do{xnot} have a StorPool template setting'
           .format(xnot=' not' if template is None else ''))
    if template is None:
        rdebug('no storpool_template in the configuration yet')
        reactive.remove_state('cinder-storpool.configured')
        return

    rdebug('we have the {template} template now'.format(template=template))
    reactive.set_state('cinder-storpool.configured')


@reactive.when_not('storage-backend.configure')
def no_cinder_presence():
    rdebug('no Cinder hook yet')
    hookenv.status_set('maintenance', 'waiting for the Cinder relation')


@reactive.when('storage-backend.configure')
@reactive.when_not('storpool-presence.configure')
def no_storpool_presence():
    rdebug('no StorPool presence data yet')
    hookenv.status_set('maintenance',
                       'waiting for the StorPool block presence data')


@reactive.when('storpool-presence.configure')
@reactive.when_not('cinder-storpool.configured')
def no_config(hk):
    rdebug('no StorPool configuration yet')
    hookenv.status_set('maintenance', 'waiting for the StorPool configuration')


@reactive.when('storage-backend.configure')
@reactive.when('storpool-presence.configure')
@reactive.when('cinder-storpool.configured')
def storage_backend_configure(hk):
    rdebug('configuring cinder and stuff')
    service = hookenv.service_name()
    data = {
        'cinder': {
            '/etc/cinder/cinder.conf': {
                'sections': {
                    service: [
                        ('volume_backend_name',
                         service),
                        ('volume_driver',
                         'cinder.volume.drivers.storpool.StorPoolDriver'),
                        ('storpool_template',
                         hookenv.config()['storpool_template']),
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
    hookenv.status_set('active',
                       'the StorPool Cinder backend should be up and running')


@reactive.hook('storage-backend-relation-joined')
def got_cinder_conn():
    rdebug('got a cinder connection')
    reactive.set_state('storage-backend.configure')


@reactive.hook('storage-backend-relation-changed')
def changed_cinder_conn():
    rdebug('updated a cinder connection')
    reactive.set_state('storage-backend.configure')
