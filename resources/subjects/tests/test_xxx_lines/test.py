import unittest
import main


class TestMain(unittest.TestCase):
    def test_main_f(self):
        self.assertEqual(0, main.f())

    def test_main_fgh(self):
        self.assertEqual(0, main.f())
        self.assertEqual(1, main.g())
        self.assertEqual(2, main.h())

    def test_main_gh(self):
        self.assertEqual(1, main.g())
        self.assertEqual(2, main.h())
