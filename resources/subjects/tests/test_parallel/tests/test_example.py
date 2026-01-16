import unittest
from example import compute_parallel


class MiddleTests(unittest.TestCase):
    def test_21345(self):
        self.assertEqual(compute_parallel([2, 1, 3, 4, 5]), [2, 1, 6, 24, 120])

    def test_32106(self):
        self.assertEqual(compute_parallel([3, 2, 1, 0, 6]), [6, 2, 1, 1, 720])

    def test_67(self):
        self.assertEqual(compute_parallel([6, 7]), [720, 5040])
