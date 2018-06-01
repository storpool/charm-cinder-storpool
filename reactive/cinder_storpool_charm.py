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
import os
import platform

from charms import reactive

from charmhelpers.core import hookenv

from spcharms import config as spconfig
from spcharms import error as sperror
from spcharms import service_hook
from spcharms import utils as sputils

from spcharms.run import storpool_openstack_integration as run_osi


RELATIONS = ['cinder-p', 'storpool-presence']


sp_node = platform.node()


def rdebug(s, cond=None):
    """
    Pass the diagnostic message string `s` to the central diagnostic logger.
    """
    sputils.rdebug(s, prefix='cinder-charm', cond=cond)


@reactive.hook('install')
def install():
    """
    Try to (re-)install everything.
    """
    reactive.set_state('cinder-storpool.run')


@reactive.hook('config-changed')
def config_changed():
    """
    Try to (re-)install everything.
    """
    reactive.set_state('cinder-storpool.run')


@reactive.when('cinder-storpool.configure')
@reactive.when_not('cinder-storpool.configured')
@reactive.when_not('cinder-storpool-charm.stopped')
def configure():
    """
    Make note of the fact that the "storpool_template" setting has been
    set (or changed) in the charm configuration.
    """
    rdebug('config-changed')
    reactive.remove_state('cinder-storpool.configure')
    config = hookenv.config()

    template = config.get('storpool_template', None)
    rdebug('and we do{xnot} have a StorPool template setting'
           .format(xnot=' not' if template is None else ''))
    if template is None or template == '':
        rdebug('no storpool_template in the configuration yet')
        return

    rdebug('we have the {template} template now'.format(template=template))
    reactive.set_state('cinder-storpool.configured')


@reactive.when_not('storage-backend.configure')
@reactive.when_not('cinder-storpool-charm.stopped')
def no_cinder_presence():
    """
    Set the unit status to "maintenance" until the `storage-backend` hook has
    been connected to the `cinder` charm.
    """
    rdebug('no Cinder hook yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance', 'waiting for the Cinder relation')


@reactive.when('storage-backend.configure')
@reactive.when_not('storpool-presence.configured')
@reactive.when_not('cinder-storpool-charm.stopped')
def no_storpool_presence():
    """
    Set the unit status to "maintenance" until the `storpool-presence` hook
    has been connected to the `storpool-block` charm.
    """
    rdebug('no StorPool presence data yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance',
                       'waiting for the StorPool block presence data')


@reactive.when('storpool-presence.configured')
@reactive.when_not('cinder-storpool.configured')
@reactive.when_not('cinder-storpool-charm.stopped')
def no_config(*args, **kwargs):
    """
    Set the unit status to "maintenance" until the `storpool-block` charm has
    sent the notification that the services are set up on this node.
    """
    rdebug('no StorPool configuration yet')
    reactive.remove_state('cinder-storpool.ready')
    hookenv.status_set('maintenance', 'waiting for the StorPool configuration')


@reactive.when('storage-backend.configure')
@reactive.when('storpool-presence.notify')
def block_changed(_):
    try_announce()


@reactive.when('storage-backend.configure')
@reactive.when('cinder-p.notify')
def cinder_changed(_):
    try_announce()


def try_announce():
    try:
        announce_presence()
        # Only reset the flag afterwards so that if anything
        # goes wrong we can retry this later
        # It should be safe to reset both states at once; we always
        # fetch data on both hooks, so we can't miss anything.
        reactive.remove_state('cinder-p.notify')
        reactive.remove_state('cinder-p.notify-joined')
        reactive.remove_state('storpool-presence.notify')
        reactive.remove_state('storpool-presence.notify-joined')
    except Exception as e:
        hookenv.log('Could not parse the presence data: {e}'.format(e=e))
        exit(42)


def build_presence(current):
    current['hostname'] = platform.node()


def deconfigure():
    if reactive.is_state('storpool-presence.configured'):
        rdebug('  - clearing any cached config state')
        spconfig.unset_meta_config()
        spconfig.unset_meta_generation()
        spconfig.unset_our_id()
        reactive.remove_state('storpool-presence.configured')


def announce_presence(force=False):
    data = service_hook.fetch_presence(RELATIONS)
    rdebug('processing presence data at generation {gen}'
           .format(gen=data['generation']),
           cond='announce')

    rdebug('state: {d}'.format(d=list(map(lambda k: '{k}={m}'
                                                    .format(k=k,
                                                            m=data['nodes'][k]
                                                            .get('id')),
                                          sorted(data['nodes'].keys())))),
           cond='announce')

    announce = force
    cinder_joined = reactive.is_state('cinder-p.notify-joined')
    block_joined = reactive.is_state('storpool-presence.notify-joined')
    if cinder_joined or block_joined:
        announce = True

    # Look for a block unit's config info.
    cfg = None
    cfg_gen = -1
    for node, ndata in data['nodes'].items():
        if not node.startswith('block:'):
            continue
        ncfg = ndata.get('config')
        if ncfg is None:
            continue
        if cfg is None:
            cfg = ncfg
            cfg_gen = ndata['generation']
        else:
            cfg = None
            break

    parent_id = 'block:' + sputils.get_parent_node()
    our_id = data['nodes'].get(parent_id, {}).get('id')
    if our_id is None:
        rdebug('no ourid in the StorPool presence data yet', cond='announce')
        deconfigure()
    else:
        rdebug('got ourid {oid}'.format(oid=our_id), cond='announce')
        if not os.path.exists('/etc/storpool.conf.d'):
            os.mkdir('/etc/storpool.conf.d', mode=0o755)
        with open('/etc/storpool.conf.d/cinder-sub-ourid.conf',
                  mode='wt') as spconf:
            print('[{name}]\nSP_OURID={oid}'
                  .format(name=platform.node(), oid=our_id),
                  file=spconf)
        if cfg is not None:
            # ...then, finally, process that config!
            spconfig.set_meta_config(cfg)
            reactive.set_state('storpool-presence.configured')
            last_gen = spconfig.get_meta_generation()
            if last_gen is None or int(cfg_gen) > int(last_gen):
                announce = True
                spconfig.set_meta_generation(cfg_gen)
                reactive.set_state('cinder-storpool.run')
        else:
            deconfigure()

    generation = data['generation']
    if int(generation) < 0:
        generation = 0
    if announce:
        mach_id = 'cinder:' + sputils.get_machine_id()
        data = {
            'generation': generation,

            'nodes': {
                mach_id: {
                    'generation': generation,
                    'hostname': sputils.get_machine_id()
                },
            },
        }
        rdebug('announcing {data}'.format(data=data),
               cond='announce')
        service_hook.send_presence(data, RELATIONS)


@reactive.when('storage-backend.configure')
@reactive.when('storpool-presence.configured')
@reactive.when('cinder-storpool.configured')
@reactive.when_not('cinder-storpool.ready')
@reactive.when_not('cinder-storpool-charm.stopped')
def storage_backend_configure(*args, **kwargs):
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
    rel_ids = hookenv.relation_ids('storage-backend')
    for rel_id in rel_ids:
        hookenv.relation_set(rel_id,
                             backend_name=hookenv.service_name(),
                             subordinate_configuration=json.dumps(data),
                             stateless=True)
        rdebug('- sent it along {rel}'.format(rel=rel_id))
    reactive.set_state('cinder-storpool.ready')
    hookenv.status_set('active',
                       'the StorPool Cinder backend should be up and running')


@reactive.hook('upgrade-charm')
@reactive.when_not('cinder-storpool-charm.stopped')
def upgrade():
    """
    Try to (re-)install everything.
    """
    reactive.set_state('cinder-storpool.run')


@reactive.hook('start')
@reactive.when_not('cinder-storpool-charm.stopped')
def start_service():
    """
    Try to (re-)install everything.
    """
    reactive.set_state('cinder-storpool.run')


@reactive.when('cinder-storpool.run')
@reactive.when('storpool-presence.configured')
def run():
    reactive.remove_state('cinder-storpool.run')
    reactive.remove_state('cinder-storpool.configured')
    reactive.remove_state('cinder-storpool.ready')
    failed = False
    try:
        rdebug('Run, StorPool OpenStack integration, run!')
        run_osi.run()
        rdebug('It seems that the storpool-osi setup has run its course')

        rdebug('Triggering the hooks configuration check')
        reactive.set_state('cinder-storpool.configure')
    except sperror.StorPoolNoConfigException as e_cfg:
        hookenv.log('StorPool: missing configuration: {m}'
                    .format(m=', '.join(e_cfg.missing)),
                    hookenv.INFO)
    except sperror.StorPoolPackageInstallException as e_pkg:
        hookenv.log('StorPool: could not install the {names} packages: {e}'
                    .format(names=' '.join(e_pkg.names), e=e_pkg.cause),
                    hookenv.ERROR)
        failed = True
    except sperror.StorPoolNoCGroupsException as e_cfg:
        hookenv.log('StorPool: {e}'.format(e=e_cfg), hookenv.ERROR)
        failed = True
    except sperror.StorPoolException as e:
        hookenv.log('StorPool installation problem: {e}'.format(e=e))
        failed = True

    if failed:
        exit(42)


@reactive.hook('stop')
def stop_and_propagate():
    """
    Propagate a `stop` action to the lower layers.

    Also set the "cinder-storpool-charm.stopped" state so that no further
    presence or status updates are sent to other units or charms.
    """
    rdebug('a stop event was received')

    rdebug('letting storpool-openstack-integration know')
    run_osi.stop()

    rdebug('done here, it seems')
    reactive.set_state('cinder-storpool-charm.stopped')
