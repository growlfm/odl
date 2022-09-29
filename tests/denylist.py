import unittest

from odl import denylist


class TestDenyList(unittest.TestCase):
    def test_basic_denylist(self):

        # it doesn't match?
        assert not denylist.is_denied("test")

        assert denylist.is_denied("3.120.0.0")
        assert denylist.is_denied("3.120.0.1")


if __name__ == '__main__':
    unittest.main()
