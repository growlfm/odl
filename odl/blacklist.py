import os
import csv
import ipaddress
import pytricia

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_ranges():
    input_path = os.path.join(DIR_PATH, './data/datacenters.csv')
    with open(input_path) as input_file:
        reader = csv.DictReader(input_file, fieldnames=['range_start', 'range_end', 'name', 'info_url'])
        for row in reader:
            yield (ipaddress.ip_address(row['range_start']),
                   ipaddress.ip_address(row['range_end']))


class Blacklist(object):
    """
    Uses ipcat's excellent data center list to remove downloads from known
    datacenters.

    https://github.com/client9/ipcat/blob/master/datacenters.csv
    """
    _db = None

    def is_blacklisted(self, ip):
        if self._db is None:
            self._db = pytricia.PyTricia()
            for start, end in get_ranges():
                for network in ipaddress.summarize_address_range(start, end):
                    self._db.insert(str(network), '1')

        return str(ip) in self._db


blacklist = Blacklist()


def is_blacklisted(ip):
    return blacklist.is_blacklisted(ip)
