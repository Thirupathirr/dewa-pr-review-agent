from calculator import add, subtract, sqrt


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_sqrt():
    assert sqrt(9) == 3
