import unittest

from odl import denylist


class TestDenyList(unittest.TestCase):
    def test_invalid_ip_format(self):
        with self.assertRaises(Exception) as context:
            denylist.is_denied("test")

        self.assertTrue('Invalid key type' in str(context.exception))

    def test_not_denied(self):
        assert denylist.is_denied("8.8.8.8") is False

    def test_is_denied(self):
        assert denylist.is_denied("3.120.0.0")
        assert denylist.is_denied("3.120.0.1")


if __name__ == '__main__':
    unittest.main()

