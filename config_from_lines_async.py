#!/usr/bin/env python3

import time
import datetime
from pytz import timezone
from decouple import config
import re
import yaml
import asyncio
import netdev

"""
works as of 

"""

COMMANDS_FILE = "configs.yml"
INVENTORY_FILE = "devices.yml"

GLOBAL_DEVICE_PARAMS = {
    "device_type": "cisco_ios",
    "username": config("USER_NAME"),
    "password": config("PASSWORD"),
}

# from getpass import getpass
# USER_NAME = input("Enter your SSH username:")
# PASSWORD = getpass()

# GLOBAL_DEVICE_PARAMS = {
#     "device_type": "cisco_ios",
#     "username": USER_NAME,
#     "password": PASSWORD,
# }

def get_devices_list(file_name=INVENTORY_FILE):
    with open(file_name) as f:
        result = yaml.safe_load(f)
    return result["devices"]

def get_config_commands(file_name=COMMANDS_FILE):
    with open(file_name) as f:
        result = f.read().splitlines()
    return result

def extract_hostname(sh_ver):
    device_hostname = dict()
    for regexp in software_ver_check(sh_ver):
        device_hostname.update(regexp.search(sh_ver).groupdict())
    return device_hostname


def software_ver_check(sh_ver):

    # Types of devices
    version_list = [
        "IOS XE",
        "NX-OS",
        "C2960X-UNIVERSALK9-M",
        "vios_l2-ADVENTERPRISEK9-M",
        "VIOS-ADVENTERPRISEK9-M",
    ]
    # Check software versions
    for version in version_list:
        int_version = 0  # Reset integer value
        int_version = sh_ver.find(version)  # Check software version
        if int_version > 0:  # software version found, break out of loop.
            break

    if version == "NX-OS":
        parsed_hostname = [
            re.compile(r"(^\s+)+(Device name:)\s(?P<hostname>\S+)", re.M)
        ]

    else:  # other cisco ios versions
        parsed_hostname = [re.compile(r"(?P<hostname>^\S+)\s+uptime", re.M)]

    return parsed_hostname


def save_output(device_hostname, commands_output):
    """
    writes outputs to a file.

    Args:
        device_hostname (string): parsed hostname of device on which commands were executed
        command output(dict): concantenated string of the outputs executed on devices

    Returns:
        Filename is timestamped with date etc

    """

    est = timezone("EST")
    time_now = datetime.datetime.now(est)
    output_filename = "%s_%.2i%.2i%i_%.2i%.2i%.2i.log" % (
        device_hostname,
        time_now.year,
        time_now.month,
        time_now.day,
        time_now.hour,
        time_now.minute,
        time_now.second,
    )
    output_file = open(output_filename, "a")
    output_file.write(commands_output)
    output_file.close


async def configure_device(ip_address):

    """
    Login and run list of commands from file on all devices on the site

    Args:
        ip_address (list): host ip address from list component

    Returns:
        hostname (dict): key is device hostname, value is dictionary containing hostname for use in saving output to file
        command output(dict): concantenated string of the outputs executed on devices

    the method used to parse the device hostname could be simpler but it's flexible enough to add other parsed variables.

    for netmiko 
    send_config_from_file(self, config_file=None, **kwargs)
    send_config_set(self, config_commands=None, exit_config_mode=True, delay_factor=1, max_loops=150, strip_prompt=False, strip_command=False, config_mode_command=None, cmd_verify=True, enter_config_mode=True)

    setting config file=yml and using load.yml results in config not loaded properly, lines not split into new lines
    setting config file=yml/cfg and using read, results in not being able to login but config actually applies. splitlines() works

    Netdev does not support send_config_from_file
    
    """

    device_params = GLOBAL_DEVICE_PARAMS.copy()
    device_params["host"] = ip_address
    parsed_values = dict()
    
    try: 
        async with netdev.create(**device_params) as device_conn:
            show_version_output = await device_conn.send_command("show version")
            parsed_values.update(extract_hostname(show_version_output))
            print("Running commands on {hostname}".format(**parsed_values))
            
            commands_output = ["Deploying configs to {hostname}".format(**parsed_values)]
            config_commands = get_config_commands()
            
            # commands_output.append(await device_conn.send_config_from_file(config_file=COMMANDS_FILE) #not supported for netdev?
            commands_output.append(await device_conn.send_config_set(config_commands))
            commands_output.append("\n" + ("=" * 80) + "\n")
            all_commands_output = "\n".join(commands_output)

            result = {
                    "device_hostname": "{hostname}".format(**parsed_values),
                    "commands_output": all_commands_output,
                }
            return result

    # except netdev.exceptions.DisconnectError as e:
    except Exception as e:
        exception_msg = "Unable to login to device " + ip_address + "\n"
        exception_msg+= str(e)
        exception_msg+= "\n" + ("=" * 80) + "\n"
        result = {
                "device_hostname": ip_address,
                "commands_output": exception_msg,
            }
        print("Unable to login to device " + ip_address)
        print (e)
        return result


def main():

    start_time = time.time()

    ip_list = get_devices_list()

    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(configure_device(ip)) for ip in ip_list]
    loop.run_until_complete(asyncio.gather(*tasks))

    for task in tasks:
        save_output(task.result()["device_hostname"], task.result()["commands_output"])
        print(task.result()["commands_output"])
    
    print("Please check device logs for any errors")
    print(f"It took {time.time() - start_time} seconds to run")


if __name__ == "__main__":
    main()
