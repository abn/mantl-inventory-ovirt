# Mantl: Ansible dynamic inventory for oVirt

This script provides a dynamic inventory script for use with Mantl on oVirt.

#### Usage

Once the `ovirt.ini` file is configured as required, you can test the script as shown here.

```sh
./ovirt.py --pretty
```

This will print ansible dynamic inventory expected JSON with pretty print formatting.
```json
{
    "_meta": {
        "hostvars": {
            "192.168.10.20": {
                "consul_dc": "dc1",
                "dc": "dc1",
                "role": "control"
            },
            "192.168.10.55": {
                "consul_dc": "dc1",
                "dc": "dc1",
                "role": "worker"
            }
        }
    },
    "local_datacenter": {
        "hosts": [
            "192.168.10.20",
            "192.168.10.55"
        ],
        "vars": {
            "ansible_ssh_port": 22,
            "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
            "ansible_ssh_user": "root",
            "dc": "dc1"
        }
    },
    "role=control": {
        "hosts": [
            "192.168.10.20"
        ]
    },
    "role=worker": {
        "hosts": [
            "192.168.10.55"
        ]
    }
}

```
#### Prerequisites

##### Dependencies
The script requires the Python oVirt Engine SDK to be available.

```sh
pip install -r requirements.txt
```

##### VM Tags

As this script expects VMs to be already provisioned and tagged in the oVirt environment, provisioning of VMs is out of scope. The [oVirt documentation](http://www.ovirt.org/OVirt_Administration_Guide#Customizing_Hosts_with_Tags) is a great source for how to create and apply tags to VMs.

By default, this script looks for 'mi-control' and 'mi-worker' tags representing Mantl control and worker nodes respectively. This can be configured via the `ovirt.ini` file before executing the script.

#### Configuration

Copy over _ovirt.ini.sample_ to _ovirt.ini_ and modify according to your oVirt environment. A sample configuration for development instance could look like the following snippet.

```ini
[DEFAULT]
ovirt_api_insecure = True
ovirt_username = admin@internal
ovirt_url = https://192.168.10.9/api
ovirt_password = password

ovirt_ip_regex = ^(\d+).(\d+).(\d+).(\d+)$
ovirt_tag_control = mi-control
ovirt_tag_worker = mi-worker

ansible_ssh_port: 22
ansible_ssh_private_key_file: ~/.ssh/id_rsa
ansible_ssh_user: root

[dc1]
ovirt_dc = local_datacenter

[dc2]
ovirt_dc = local_datacenter
ovirt_url = https://192.168.10.10/api

```
##### Defaults

The default section defines all options that are common to every data center that is configured. This is similar to how python handles `ini` configuration files via `ConfigParser`.

##### oVirt API Configration

These options are used to interact with oVirt management API when extracting infromation from the environment. Username, password, and url are mandatory.

The options `ovirt_tag_control` and `ovirt_tag_worker` define what tags are used to identify each of the Mantl node roles.

##### Data Center Configuration

In this configuration, a single data center is configured. Note that the `ovirt_dc` option specifies the data center name in the oVirt environment and the section `[dc1]` specifies how this data center is referred to by Mantl. If both are the same, you can exclude `ovirt_dc` and the section name will be used for both.

##### Ansible Configuration

These options appear as host variables used by ansible. See the `ovirt.py` script for a full list of these options.
