"""Tests for Finance_bot operations_finder module."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Finance_bot.operations_finder import operation_finder


class TestOperationFinder:
    """Test operation_finder function."""

    def test_basic_addition(self):
        result = operation_finder("2+3")
        assert result == 5

    def test_basic_subtraction(self):
        result = operation_finder("10-4")
        assert result == 6

    def test_basic_multiplication(self):
        result = operation_finder("6*7")
        assert result == 42

    def test_basic_division(self):
        result = operation_finder("20/4")
        assert result == 5

    def test_bodmas_multiplication_before_addition(self):
        result = operation_finder("2+3*4")
        assert result == 14  # 2 + (3*4) = 14

    def test_bodmas_division_before_subtraction(self):
        result = operation_finder("10-6/2")
        assert result == 7  # 10 - (6/2) = 7

    def test_multiple_operations(self):
        result = operation_finder("10+5*2-3")
        assert result == 17  # 10 + (5*2) - 3 = 17

    def test_chained_multiplication(self):
        result = operation_finder("2*3*4")
        assert result == 24

    def test_chained_division(self):
        result = operation_finder("100/2/5")
        assert result == 10  # (100/2)/5 = 10

    def test_mixed_operations(self):
        result = operation_finder("10+20*3-15/5")
        assert result == 67  # 10 + 60 - 3 = 67

    def test_negative_first_number(self):
        result = operation_finder("-5+3")
        assert result == -2

    def test_negative_after_operator(self):
        result = operation_finder("5*-3")
        assert result == -15

    def test_negative_after_subtraction(self):
        result = operation_finder("10--5")
        # This might be parsed as 10 - -5 = 15 or fail
        # Let's see what actually happens
        result = operation_finder("10- -5")
        assert result == 15

    def test_decimal_numbers(self):
        result = operation_finder("2.5+3.1")
        assert result == 5.6

    def test_decimal_multiplication(self):
        result = operation_finder("2.5*4")
        assert result == 10.0

    def test_division_results_in_float(self):
        result = operation_finder("7/2")
        assert result == 3.5

    def test_empty_string_returns_none(self):
        result = operation_finder("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = operation_finder("   ")
        assert result is None

    def test_invalid_expression_returns_none(self):
        result = operation_finder("abc")
        assert result is None

    def test_expression_with_spaces(self):
        result = operation_finder(" 2 + 3 ")
        assert result == 5

    def test_complex_expression(self):
        result = operation_finder("100/4*2+50-25")
        # 100/4 = 25, 25*2 = 50, 50+50 = 100, 100-25 = 75
        assert result == 75

    def test_single_number(self):
        result = operation_finder("42")
        assert result == 42

    def test_negative_single_number(self):
        result = operation_finder("-42")
        assert result == -42

    def test_zero_handling(self):
        result = operation_finder("5*0+10")
        assert result == 10

    def test_division_by_zero_raises(self):
        # Division by zero should raise ZeroDivisionError
        try:
            operation_finder("5/0")
            assert False, "Should have raised ZeroDivisionError"
        except ZeroDivisionError:
            pass

    def test_consecutive_operators_raises(self):
        # "5++3" raises ValueError due to malformed expression
        with pytest.raises(ValueError):
            operation_finder("5++3")


class TestOperationFinderEdgeCases:
    """Edge case tests for operation_finder."""

    def test_very_long_expression(self):
        expr = "+".join(["1"] * 100)
        result = operation_finder(expr)
        assert result == 100

    def test_large_numbers(self):
        result = operation_finder("1000000*1000000")
        assert result == 1000000000000

    def test_many_decimal_places(self):
        result = operation_finder("0.1+0.2")
        # Floating point precision
        assert abs(result - 0.3) < 0.0001

    def test_subtraction_resulting_in_negative(self):
        result = operation_finder("5-10")
        assert result == -5

    def test_multiple_negatives(self):
        result = operation_finder("-5*-3")
        assert result == 15

    def test_expression_ending_with_operator_raises(self):
        # "5+" raises IndexError due to missing operand
        with pytest.raises(IndexError):
            operation_finder("5+")

    def test_expression_starting_with_operator_raises(self):
        # "+5" raises ValueError as first token is operator
        with pytest.raises(ValueError):
            operation_finder("+5")