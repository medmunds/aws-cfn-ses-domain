from unittest import TestCase

from aws_cfn_ses_domain.utils import to_bool


class TestToBool(TestCase):
    TRUE_VALUES = (
        'true', 'True', 'TRUE', 'tRuE',
        1, '1',
        True,
    )

    FALSE_VALUES = (
        'false', 'False', 'FALSE', 'fAlSe',
        0, '0',
        None, 'None',
        'null',  # JSON's None as a string
        '',  # empty string
        False,
    )

    INVALID_VALUES = (
        'yes', 'no', 't', 'f', ' ',
        100, -1, 0.5,
    )

    def test_true(self):
        for value in self.TRUE_VALUES:
            with self.subTest(value=value):
                self.assertIs(to_bool(value), True)

    def test_false(self):
        for value in self.FALSE_VALUES:
            with self.subTest(value=value):
                self.assertIs(to_bool(value), False)

    def test_invalid(self):
        for value in self.INVALID_VALUES:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    to_bool(value)
