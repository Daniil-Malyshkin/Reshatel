# -*- coding: utf-8 -*-
"""Быстрые регрессионные тесты математического ядра (нужен sympy)."""
import unittest
import solver


class SolverRegressionTests(unittest.TestCase):
    def check_answer(self, task, expected):
        self.assertEqual(solver.solve_for_web(task)["answer"], expected, task)

    def test_linear(self):
        self.check_answer("2x + 3 = 11", "x = 4")

    def test_quadratic(self):
        self.check_answer("x^2 - 5x + 6 = 0", "x₁ = 2; x₂ = 3")

    def test_system(self):
        self.check_answer("x+y=6; x-y=2", "x = 4, y = 2")

    def test_inequality_unicode(self):
        self.check_answer("x ≤ 3", "(-∞; 3]")

    def test_fraction_latex(self):
        self.check_answer(r"\frac{1}{2}x=3", "x = 6")

    def test_root_unicode(self):
        self.check_answer("√(x)=3", "x = 9")

    def test_root_without_parentheses(self):
        self.check_answer("√9+1", "4")

    def test_logarithm(self):
        self.check_answer("log_2(x)=3", "x = 8")

    def test_trigonometry(self):
        self.assertIn("k ∈ ℤ", solver.solve_for_web("sin(x)=0")["answer"])

    def test_not_equal(self):
        self.check_answer("x≠2", "(-∞; 2) ∪ (2; ∞)")

    def test_parentheses_and_implicit_multiplication(self):
        self.check_answer("(x+1)(x-2)=0", "x₁ = -1; x₂ = 2")

    def test_fraction_with_x(self):
        self.check_answer(r"\frac{1}{2}x=3", "x = 6")

    def test_logarithm_with_x(self):
        self.check_answer("log(x)=2", "x = 100")

    def test_root_with_expression(self):
        self.check_answer("sqrt(x+1)=3", "x = 8")

    def test_trigonometry_with_interval(self):
        self.check_answer(
            "2sin^2(x)-3sin(x)+1=0\n0 <= x < 2*pi",
            "π/6; π/2; 5·π/6",
        )

    def test_linear_inequality(self):
        self.check_answer("x+2>5", "(3; ∞)")

    def test_no_real_roots(self):
        self.check_answer("x^2+1=0", "действительных решений нет")


if __name__ == "__main__":
    unittest.main(verbosity=2)
