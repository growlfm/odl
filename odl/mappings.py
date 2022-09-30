import os
import json

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_mappings():
    with open(os.path.join(DIR_PATH, './data/mappings.json'),
              'rb') as jsonfile:
        return json.load(jsonfile)


class Mappings(object):
    _json = None

    def get(self, section, key):
        if self._json is None:
            self._json = get_mappings()

        value = 'Unknown'

        if section in self._json.keys(): 
            map = self._json[section]
            if key in map.keys():
                value = map[key]

        return value


mappings = Mappings()


def map_device(val):
    return mappings.get('device', val)


def map_os(val):
    return mappings.get('os', val)
