import json
from .models import db, SystemSettings


def add_system_settings():
    db.session.add_all([
        SystemSettings(
            name='billing_type', label='Select your billing system',
            value='No billing'),
        SystemSettings(
            name='billing_url', label='Link to WHMCS',
            placeholder='http://domain.name',
            description=('Used to access billing API and to create link to '
                         'predefined application request processing script')),
        SystemSettings(
            name='billing_username', label='WHMCS admin username',
            placeholder='admin'),
        SystemSettings(
            name='billing_password', label='WHMCS admin password',
            placeholder='password'),
        SystemSettings(
            name='sso_secret_key', label='Secret key for Single sign-on',
            placeholder='Enter a secret key',
            description=('Used for Single sign-on. Must be shared between '
                         'Kuberdock and billing system.')),
        SystemSettings(
            name='persitent_disk_max_size', value='10',
            label='Persistent disk maximum size',
            description='Maximum capacity of a user container persistent disk in GB',
            placeholder='Enter value to limit PD size'),
        SystemSettings(
            name='max_kubes_per_container', value='10',
            label='Maximum number of kubes per container',
            description='Changing this value won\'t affect existing containers',
            placeholder='Enter value to limit number of kubes per container'),
        SystemSettings(
            name='cpu_multiplier', value='8',
            label='CPU multiplier',
            description='Cluster CPU multiplier',
            placeholder='Enter value for CPU multiplier'),
        SystemSettings(
            name='memory_multiplier', value='4',
            label='Memory multiplier',
            description='Cluster Memory multiplier',
            placeholder='Enter value for Memory multiplier'),
    ])
