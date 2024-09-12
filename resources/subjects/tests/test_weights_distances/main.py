class A:
    FIRST = True

    def __init__(self):
        self.first = A.FIRST
        A.FIRST = False

    def g(self):
        return True

    def h(self):
        return not self.first


def f():
    return A()
