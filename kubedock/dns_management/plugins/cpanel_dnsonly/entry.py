from flask import current_app

from .dnsonly_client import API


def delete_type_A_record(domain, **kwargs):
    """
    Delete A record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as email and
        token and certtoken for access to Cloudflare API
    :return: None
    """
    _, _, main_domain = domain.partition('.')
    api = API(**kwargs)

    for zone in api.zones():
        if zone.name == main_domain:
            for dns_record in zone.records():
                # dns record without end point
                if dns_record.type == 'A' and domain == dns_record.name[:-1]:
                    dns_record.delete()


def delete_type_CNAME_record(domain, **kwargs):
    """
    Delete CNAME record to domain

    :param domain: domain which will have been deleted
    :param dict kwargs: additional params such as email and
        token and certtoken for access to Cloudflare API
    :return: None
    """
    _, _, main_domain = domain.partition('.')
    api = API(**kwargs)

    for zone in api.zones():
        if zone.name == main_domain:
            for record in zone.records():
                # dns record without end point
                if record.type == 'CNAME' and domain == record.name[:-1]:
                    record.delete()


def create_or_update_type_A_record(domain, new_ips, **kwargs):
    """
    Create or update A record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as token for access WHM API
    :return:
    """
    _, _, main_domain = domain.partition('.')
    api = API(**kwargs)

    for zone in api.zones():
        if zone.name == main_domain:
            for dns_record in zone.records():
                # dns record without end point
                if dns_record.type == 'A' and domain == dns_record.name[:-1]:
                    if dns_record.address not in new_ips:
                        # dnsonly can assign only one ip address
                        # here you can use roundrobin for many ip addresses
                        new_ip = new_ips[0]

                        dns_record.address = new_ip
                        dns_record.edit()

                        current_app.logger.debug(
                            'Replace record in zone "{zone}" with '
                            'domain "{domain}" '
                            'and ip "{ips}"'.format(
                                zone=zone.name, domain=domain, ips=new_ip
                            ))

                    else:
                        current_app.logger.debug(
                            'Domain "{domain}" with '
                            'ip "{ips}" in zone "{zone}" '
                            'already exists'.format(
                                zone=zone.name, domain=domain, ips=new_ips
                            ))

                    break  # exit for loop after dns record was processed

            else:
                # dnsonly can assign only one ip address
                # here you can use roundrobin for many ip addresses
                new_ip = new_ips[0]

                zone.add_a_record(domain, new_ip)
                current_app.logger.debug(
                    'Create new record in zone "{zone}" with '
                    '"{domain}" '
                    'and ip "{ips}"'.format(
                        zone=zone.name, domain=domain, ips=new_ips
                    ))
            break  # exit for loop after dns zone was processed
    else:
        # this branch executes if for loop is not terminated by break
        # e.g. there is no dns zone that we expect
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))


def create_or_update_type_CNAME_record(domain, target, **kwargs):
    """
    Create or update CNAME record for IP addresses of load
    balancer

    :param str domain: New subdomain name in existing zone
    :param list new_ips: IP addresses of load balancer
    :param dict kwargs: additional params such as token for access WHM API
    :return:
    """
    _, _, main_domain = domain.partition('.')
    api = API(**kwargs)

    try:
        target_zone = next(z for z in api.zones() if z.name == main_domain)
    except StopIteration:
        raise ValueError("Zone for domain {} not found. "
                         "Need to configure the zone".format(domain))

    for dns_record in target_zone.records():
        if dns_record.type == 'CNAME' and domain == dns_record.name[:-1]:
            if dns_record.cname == target:
                current_app.logger.debug(
                    'CNAME record {} for domain "{}" '
                    'in the "{}" zone already exists'.format(
                        target, domain, target_zone.name))
                return

            dns_record.cname = target
            dns_record.edit()

            current_app.logger.debug(
                'Replaced CNAME record in zone "{zone}" with '
                'domain "{domain}" and target "{target}"'.format(
                    zone=target_zone.name, domain=domain, target=target))

            return

    # If a matching record was not found - create a new one
    target_zone.add_cname_record(domain, target)
    current_app.logger.debug(
        'Created a new CNAME record in zone "{zone}" with '
        '"{domain}" and target "{target}"'.format(
            zone=target_zone.name, domain=domain, target=target
        ))


def check_if_zone_exists(domain, **kwargs):
    api = API(**kwargs)
    for zone in api.zones():
        if zone.name == domain:
            return True
    return False
