#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Dynamic inventory for oVirt - finds all MANTL nodes based on oVirt tags.
This expects an ovirt.ini file to be present to configure oVirt API, tags etc.
"""
from argparse import ArgumentParser
from ConfigParser import SafeConfigParser as ConfigParser

from json import dumps

from os.path import dirname, join
from ovirtsdk.api import API
from re import compile as regex_compile


# oVirt configuration keys
OVIRT_API_INSECURE = 'ovirt_api_insecure'
OVIRT_CA = 'ovirt_ca'
OVIRT_IP_REGEX = 'ovirt_ip_regex'
OVIRT_NIC_NAME = 'ovirt_nic_name'
OVIRT_PASSWORD = 'ovirt_password'
OVIRT_TAG_CONTROL = 'ovirt_tag_control'
OVIRT_TAG_WORKER = 'ovirt_tag_worker'
OVIRT_URL = 'ovirt_url'
OVIRT_USERNAME = 'ovirt_username'
OVIRT_DC = 'ovirt_dc'


# ansible configuration keys
ANSIBLE_SSH_PK = 'ansible_ssh_private_key_file'
ANSIBLE_SSH_PORT = 'ansible_ssh_port'
ANSIBLE_SSH_USER = 'ansible_ssh_user'
ANSIBLE_SSH_PASS = 'ansible_ssh_pass'


# MI specific configuration keys
CONSUL_DC = 'consul_dc'


class OVirtInventory(object):
    # datacenter group variables extracted from configuration
    _DC_OPT_VARS = [
        (ANSIBLE_SSH_USER, str),
        (ANSIBLE_SSH_PK, str),
        (ANSIBLE_SSH_PORT, int),
        (ANSIBLE_SSH_PASS, str)
    ]

    # supported and their tag keys
    _ROLES = {
        'control': OVIRT_TAG_CONTROL,
        'worker': OVIRT_TAG_WORKER
    }

    def __init__(self, config_file):
        self._config = ConfigParser(
            defaults={
                OVIRT_IP_REGEX: '^(\d+).(\d+).(\d+).(\d+)$',
                OVIRT_NIC_NAME: None,
                OVIRT_TAG_CONTROL: 'mi-control',
                OVIRT_TAG_WORKER: 'mi-worker',
            }
        )
        self._config.read(config_file)

    @property
    def config(self):
        """

        :return: configuration used by this instance
        :rtype: ConfigParser.SafeConfigParser
        """
        return self._config

    @property
    def datacenters(self):
        return self.config.sections()

    def api(self, dc):
        """
        Create an oVirt API instance for a requested datacenter

        :param dc: datacenter
        :type dc: str
        :rtype: ovirtsdk.api.API
        """
        kwargs = {
            'password': self.config.get(dc, OVIRT_PASSWORD),
            'url': self.config.get(dc, OVIRT_URL),
            'username': self.config.get(dc, OVIRT_USERNAME),
        }

        if self.config.has_option(dc, OVIRT_CA):
            kwargs['ca_file'] = self.config.get(dc, OVIRT_CA)

        if self.config.has_option(dc, OVIRT_API_INSECURE):
            kwargs['insecure'] = bool(self.config.get(dc, OVIRT_API_INSECURE))

        return API(**kwargs)

    def ip(self, dc, vm):
        """
        Fetch the IP address of a VM in a datacenter based on configuration

        :param dc: datacenter the VM belongs to
        :type dc: str
        :param vm: the vm instance
        :type vm: ovirtsdk.infrastructure.brokers.VM
        :return: IP address string based on any NIC and REGEX conditions configured for the datacenter
        """
        nic_name = self.config.get(dc, OVIRT_NIC_NAME)
        ip_regex = self.config.get(dc, OVIRT_IP_REGEX)

        pattern = regex_compile('' if ip_regex is None else ip_regex)

        if nic_name is not None:
            nics = [vm.get_nics().get(name='nic_{0:s}'.format(nic_name))]
        else:
            nics = vm.get_nics().list()

        ips = []
        for nic in nics:
            for device in nic.get_reported_devices().get_reported_device():
                ips.extend(device.get_ips().get_ip())

        for ip in ips:
            if pattern.match(ip.get_address()) is None:
                continue
            return ip.get_address()

        return None

    def hosts(self, dc, tag=None):
        """
        Retrieve hosts in a datacenter filtered by tags if one is provided.

        :param dc: datacenter
        :type dc: str
        :param tag: oVirt tag name
        :type tag: str
        :return: a list of host IP addresses
        :rtype: list of str
        """
        hosts = []

        ovirt_dc = dc
        if self.config.has_option(dc, OVIRT_DC):
            ovirt_dc = self.config.get(dc, OVIRT_DC)

        # filter by datacenter
        conditions = ['datacenter={0:s}'.format(ovirt_dc)]

        if tag is not None:
            # filter by tag
            conditions.append('tag={0:s}'.format(tag))

        query = ' and '.join(conditions)
        for vm in self.api(dc).vms.list(query=query):
            if vm.status.state == 'up':
                # handle only if a VM is up
                ip = self.ip(dc, vm)
                if ip is not None:
                    # append only if an IP can be extracted based on configuration
                    hosts.append(ip)
        return hosts

    def inventory(self):
        """

        :return: dynamic inventory dictionary object for the configuration used in this instance
        :rtype: dict
        """
        data = {
            '_meta': {
                'hostvars': {}
            },
        }

        for dc in self.datacenters:
            # configure vars common to all hosts in a datacenter
            data[dc] = {
                'hosts': [],
                'vars': {
                    cfg[0]: cfg[1](self.config.get(dc, cfg[0]))
                    for cfg in self._DC_OPT_VARS
                    if self.config.has_option(dc, cfg[0])
                    }
            }
            data[dc]['vars']['dc'] = dc

            for role in self._ROLES.keys():
                # populate groups for each role
                group = 'role={0:s}'.format(role)
                tag = self.config.get(dc, self._ROLES.get(role))

                if group not in data:
                    data[group] = {'hosts': []}

                consul_dc = dc
                if self.config.has_option(dc, CONSUL_DC):
                    consul_dc = self.config.get(dc, CONSUL_DC)

                # hostvars for all hosts in this role are the same for this datacenter
                hostvars = {
                    'role': role,
                    'dc': dc,
                    'consul_dc': consul_dc,
                }

                hosts = self.hosts(dc, tag)

                # add hosts to both groups (role, datacenter)
                data[group]['hosts'].extend(hosts)
                data[dc]['hosts'].extend(hosts)

                for host in hosts:
                    # populate _meta
                    data['_meta']['hostvars'][host] = hostvars

        return data


def parse_cli_args():
    base_dir = dirname(__file__)
    config = join(base_dir, 'ovirt.ini')

    parser = ArgumentParser(description='Ansible dynamic inventory for MANTL on oVirt')
    parser.add_argument('--list', action='store_true', default=True, help='List instances (default: True)')
    parser.add_argument('--host', action='store', help='Get all information about an instance')
    parser.add_argument('--pretty', action='store_true', default=False, help='Pretty format (default: False)')
    parser.add_argument('--config', default=config, help='Configuration file (default: {0:s})'.format(config))
    return parser.parse_args()


def main():
    args = parse_cli_args()
    ovirt = OVirtInventory(args.config)
    inventory = ovirt.inventory()

    data = inventory

    if args.host is not None:
        data = data.get('_meta', {}).get('hostvars', {}).get(args.host, {})

    if args.pretty:
        print(dumps(data, sort_keys=True, indent=4))
    else:
        print(dumps(data))


if __name__ == '__main__':
    main()
