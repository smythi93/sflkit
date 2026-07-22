import unittest
import main


class TestMain(unittest.TestCase):
    def setUp(self):
        main.f()

    def tearDown(self):
        main.g()

    def test_main_h(self):
        self.assertEqual(2, main.h())
