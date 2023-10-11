#!/usr/bin/env python3

import time
import datetime
from getpass import getpass
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from netmiko.ssh_exception import AuthenticationException
from paramiko.ssh_exception import SSHException
from pytz import timezone
import re
import yaml
import jinja2

template_vars = {
    'comm_string': 'SNMP_STRING',
    'trap_source': 'GigabitEthernet0/0',
    'ast_subnet1': '10.243.10.0',
    'ast_mask1': '0.0.0.255',
    'ast_subnet2': '10.244.10.0',
    'ast_mask2': '0.0.0.255',
    'server_host': '10.244.10.30'
}
# Timezone conversion for timestamping file saved filenames
est = timezone('EST')
time_now = datetime.datetime.now(est)

username = input('Enter your SSH username:')
password = getpass()

# contains list of commands to be run on devices
template_file = 'configs_snmp.j2'
with open(template_file) as f:
    configs_template = f.read()

# contains list of devices to login to
with open('devices_file.yaml') as f:
    devices_list = yaml.full_load(f)

template = jinja2.Template(configs_template)
print(template.render(template_vars))

snmp_configs = template.render(template_vars)

# Login to list of devices from 'devices_file'
for devices in devices_list:
    print("Connecting to device " + devices)
    ip_address_of_device = devices
    ios_device = {
        'device_type': 'cisco_ios',
        'ip': ip_address_of_device,
        'username': username,
        'password': password
    }
    try:
        net_connect = ConnectHandler(**ios_device)
    except (AuthenticationException):
        print("Authenticaiton Failure: " + ip_address_of_device)
        continue
    except (NetMikoTimeoutException):
        print("Timeout to device: " + ip_address_of_device)
        continue
    except (EOFError):
        print("End of file while attempting device " + ip_address_of_device)
        continue
    except (SSHException):
        print("SSH issue. Are you sure SSH is enabled on " +
              ip_address_of_device + "?")
        continue
    except Exception as unknown_error:
        print("Some other error " + unknown_error)
        continue

    # Extract the device hostname from running configuration
    net_connect.send_command('term len 0')
    running_config = net_connect.send_command('show run', delay_factor=2)
    device_hostname = re.search(
        r"^hostname (.*)\s*$", running_config, flags=re.M).group(1)
    print("Connected to: " + device_hostname)
    print("Running all the relevant commands on " +
          device_hostname + ", please wait.")

    # Run list of commands from configs_file.txt
    device_hostname = device_hostname.strip() + '_config_log'
    configs_output = net_connect.send_config_set(
        snmp_configs, delay_factor=2)
    output_filename = "%s_%.2i%.2i%i_%.2i%.2i%.2i" % (
        device_hostname, time_now.year, time_now.month, time_now.day, time_now.hour, time_now.minute, time_now.second)
    output_file = open(output_filename, "a")
    output_file.write("\n\n")
    output_file.write(configs_output)
    output_file.write("\n\n")
    output_file.close


'''
confirmed working

'''
