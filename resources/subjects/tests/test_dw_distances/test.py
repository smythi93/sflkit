import unittest
from main import f


class TestMain(unittest.TestCase):
    def test(self):
        a = f()
        a.g()
        b = f()
        assert b.g()
        assert b.h()
        assert a.h()
