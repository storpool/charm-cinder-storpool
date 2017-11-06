"""
A Juju charm that uses the StorPool OpenStack integration installed by
the `storpool-block` charm and sends configuration information for
the `cinder-volume` service to the `cinder` charm.

Subordinate hooks to master charms:
- storage-backend: link to the `cinder` charm to send configuration data

Hooks to other charms:
- storpool-presence: receive a notification from the `storpool-block` charm
  when the StorPool client and the OpenStack integration have been installed
  on this node (or container).
"""
from __future__ import print_function

import json
import platform

from charms import reactive

from charmhelpers.core import hookenv

from spcharms import utils as sputils

sp_node = platform.node()


def rdebug(s):
    """
    Pass the diagnostic message string `s` to the central diagnostic logger.
    """
    sputils.rdebug(s, prefix='cinder-charm')


@reactive.hook('config-changed')
def configure():
    """
    Make note of the fact that the "storpool_template" setting has been
    set (or changed) in the charm configuration.
    """
    rdebug('config-changed')
    config = hookenv.config()

    # Make sure that we will try to send the new config to the cinder charm
    reactive.remove_state('cinder-storpool.ready')

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
    """
    Set the unit status to "maintenance" until the `storage-backend` hook has
    been connected to the `cinder` charm.
    """
    rdebug('no Cinder hook yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance', 'waiting for the Cinder relation')


@reactive.when('storage-backend.configure')
@reactive.when_not('storpool-presence.configure')
def no_storpool_presence():
    """
    Set the unit status to "maintenance" until the `storpool-presence` hook
    has been connected to the `storpool-block` charm.
    """
    rdebug('no StorPool presence data yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance',
                       'waiting for the StorPool block presence data')


@reactive.when('storpool-presence.configure')
@reactive.when_not('cinder-storpool.configured')
def no_config(hk):
    """
    Set the unit status to "maintenance" until the `storpool-block` charm has
    sent the notification that the services are set up on this node.
    """
    rdebug('no StorPool configuration yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance', 'waiting for the StorPool configuration')


@reactive.when('storage-backend.configure')
@reactive.when('storpool-presence.configure')
@reactive.when('cinder-storpool.configured')
@reactive.when_not('cinder-storpool.ready')
def storage_backend_configure(hk):
    """
    When everything has been set up and configured, let the `cinder` charm
    have the configuration for the "cinder-storpool" volume backend.
    """
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
    reactive.set_state('cinder-storpool.ready')
    hookenv.status_set('active',
                       'the StorPool Cinder backend should be up and running')