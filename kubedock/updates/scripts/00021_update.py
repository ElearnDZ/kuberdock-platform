from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='18f6b46d5b6c')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db()
