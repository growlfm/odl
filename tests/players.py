import os
import json
import unittest

from odl import players

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_useragents():
    with open(os.path.join(DIR_PATH, '../odl/data/user-agents.json'),
              'rb') as jsonfile:
        return json.load(jsonfile)


class TestPlayers(unittest.TestCase):
    def test_basic_players(self):

        for row in get_useragents():
            assert "user_agents" in row
            assert len(row['user_agents']) > 0


if __name__ == '__main__':
    unittest.main()
