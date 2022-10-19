"""
Utility to grab the raw data for user_agents and datacenter IP list.
"""

import os
import requests

from pathlib import Path


DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def download(url, file_path):
    resp = requests.get(url)
    with open(os.path.join(DIR_PATH, file_path), 'w') as file:
        file.write(resp.text)


def update():
    print("Downloading opawg user_agents and ipcat datacenters")

    # Ensure output dir exists
    output_path = '/tmp/odl/'
    Path(output_path).mkdir(parents=True, exist_ok=True)

    download(
        'https://raw.githubusercontent.com/opawg/user-agents/master/src/user-agents.json',
        '/tmp/odl/user-agents.json')

    download(
        'https://raw.githubusercontent.com/growlfm/ipcat/main/datacenters.csv',
        '/tmp/odl/datacenters.csv')

    print("Updated opawg user_agents and ipcat datacenters")


if __name__ == '__main__':
    update()
