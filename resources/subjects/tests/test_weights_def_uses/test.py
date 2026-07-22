import unittest
import main


class TestMain(unittest.TestCase):
    def test_main_f(self):
        f = main.f()
        self.assertEqual(0, f)

    def test_main_fgh(self):
        f = main.f()
        self.assertEqual(0, f)
        g = main.g()
        self.assertEqual(1, g)
        h = main.h()
        h.bit_length()
        self.assertEqual(2, f + h)

    def test_main_gh(self):
        h = main.h()
        g = main.g()
        self.assertEqual(1, g)
        self.assertEqual(2, h)
