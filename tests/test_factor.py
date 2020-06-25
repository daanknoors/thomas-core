# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import unittest
import doctest
import logging

import numpy as np
import pandas as pd

import thomas
from thomas.core.factor import Factor, mul
from thomas.core import examples
from thomas.core import error

log = logging.getLogger(__name__)

# def load_tests(loader, tests, ignore):
#     # tests.addTests(doctest.DocTestSuite(...))
#     return tests

class TestFactor(unittest.TestCase):

    def test_creation(self):
        """Test creating Factors."""
        with self.assertRaises(Exception) as context:
            Factor(0)

        fA = Factor(
            [0.6, 0.4],
            {'A': ['a1', 'a0']}
        )

        self.assertEqual(repr(fA), 'factor(A)\nA \na1    0.6\na0    0.4\ndtype: float64')

    def test_add(self):
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        fAB = fA * fB_A
        f2 = fA.add(fAB)

        self.assertTrue(isinstance(f2, Factor))

        # Adding int
        self.assertEqual((fA + 1)['a1'], 1.6)
        self.assertEqual((fA + 1)['a0'], 1.4)

        # Adding float
        self.assertEqual((fA + 1.0)['a1'], 1.6)
        self.assertEqual((fA + 1.0)['a0'], 1.4)

        # Adding Factor
        self.assertEqual((fA + fB_A)['a1', 'b1'], 0.8)
        self.assertEqual((fA + fB_A)['a1', 'b0'], 1.4)
        self.assertEqual((fA + fB_A)['a0', 'b1'], 1.15)
        self.assertEqual((fA + fB_A)['a0', 'b0'], 0.65)

        with self.assertRaises(Exception):
            fA.add('noooooo')

    @unittest.skip('deprecate?')
    def test_extract_values(self):
        """Test factor.extract_values()."""
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        self.assertIsInstance(fA.extract_values(A='a0'), float)
        self.assertIsInstance(fB_A.extract_values(A='a0', B='b1'), float)
        self.assertIsInstance(fB_A.extract_values(A='a0'), Factor)

    def test_mul(self):
        """Test factor.mul()."""
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        # int * int
        self.assertEqual(mul(3, 3), 9)

        # int
        fA2 = mul(fA, 2)
        self.assertTrue(isinstance(fA2, Factor))
        self.assertEqual(fA2.scope, ['A'])
        self.assertEqual(fA2.sum(), 2)

        # float
        fA2 = mul(fA, 2.0)
        self.assertTrue(isinstance(fA2, Factor))
        self.assertEqual(fA2.scope, ['A'])
        self.assertEqual(fA2.sum(), 2)

        # Two Factors
        fAB = mul(fA, fB_A)
        self.assertTrue(isinstance(fAB, Factor))
        self.assertEqual(fAB.scope, ['A', 'B'])

        # Factors * Series
        # fAB = mul(fA, fB_A.as_series())
        # self.assertTrue(isinstance(fAB, Factor))
        # self.assertEqual(fAB.scope, ['A', 'B'])

        # Series * Factor
        # fAB = mul(fA.as_series(), fB_A)
        # self.assertTrue(isinstance(fAB, Factor))
        # self.assertEqual(fAB.scope, ['A', 'B'])

        # Factors with single entries
        # fA_sq = fA.keep_values(A='a1') * fA.keep_values(A='a1')
        # self.assertEqual(fA_sq['a1'], 0.36)

    def test_factor_mul(self):
        """Test factor.Factor.mul()."""
        fH, fS_H, fE_H = examples.get_example17_2_factors()

        # Scope of multiplied result should be {H, S}
        self.assertEqual((fH * fS_H).vars, {'H', 'S'})

        # Scope of multiplied result should be {H, S, E}
        self.assertEqual((fE_H * fS_H).vars, {'H', 'S', 'E'})

    def test_getitem(self):
        """Test casting to Factor when accessing Factor by index."""
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()
        fAB = fA * fB_A
        self.assertTrue(isinstance(fAB['a0'], np.ndarray))

    def test_state_order(self):
        """Test that a Factor keeps its states in order and/or its index correct.

            Regression test for GitHub issue #1.
        """
        # P(A)
        fA = Factor(
            [0.6, 0.4],
            {'A': ['a1', 'a0']}
        )

        self.assertEquals(fA['a1'], 0.6)
        self.assertEquals(fA['a0'], 0.4)

        # P(B|A)
        fB_A = Factor(
            [0.2, 0.8, 0.75, 0.25],
            {'A': ['a1', 'a0'],'B': ['b1', 'b0']}
        )

        self.assertEquals(fB_A['a1', 'b1'], 0.20)
        self.assertEquals(fB_A['a1', 'b0'], 0.80)
        self.assertEquals(fB_A['a0', 'b1'], 0.75)
        self.assertEquals(fB_A['a0', 'b0'], 0.25)

    def test_multiplication(self):
        """Test factor multiplication."""
        # Get the Factors for the Sprinkler network
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        # Multiplying the factor with a *prior* with a *conditional* distribution, yields
        # a *joint* distribution.
        fAB = fA * fB_A

        # Make sure we did this right :-)
        self.assertAlmostEquals(fAB['a1', 'b1'], 0.12, places=2)
        self.assertAlmostEquals(fAB['a1', 'b0'], 0.48, places=2)
        self.assertAlmostEquals(fAB['a0', 'b1'], 0.30, places=2)
        self.assertAlmostEquals(fAB['a0', 'b0'], 0.10, places=2)

        self.assertAlmostEquals(fAB.sum(), 1, places=8)

    @unittest.skip('deprecate?')
    def test_overlaps_with(self):
        """Test factor.overlaps_with()."""
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()
        overlap = fD_BC.overlaps_with(['B', 'C'])
        self.assertTrue(overlap)

    def test_summing_out(self):
        """Test summing out variables."""
        # Get the Factors for the Sprinkler network
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        # Multiplying the factor with a *prior* with a *conditional* distribution, yields
        # a *joint* distribution.
        fAB = fA * fB_A

        # By summing out A, we'll get the prior over B
        fB = fAB.sum_out('A')

        # Make sure we did this right :-)
        self.assertAlmostEquals(fB['b1'], 0.42, places=2)
        self.assertAlmostEquals(fB['b0'], 0.58, places=2)

        self.assertAlmostEquals(fB.sum(), 1, places=8)

    def test_summing_out_all(self):
        """Test summing out variables."""
        # Get the Factors for the Sprinkler network
        fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()

        # Multiplying the factor with a *prior* with a *conditional* distribution, yields
        # a *joint* distribution.
        fAB = fA * fB_A

        total = fAB.sum_out(['A', 'B'])

        # Make sure we did this right :-)
        self.assertAlmostEquals(total.values, 1.00, places=2)
        self.assertTrue(fA.sum_out([]).equals(fA))

    def test_project(self):
        """Test the `project` function."""
        fA, fB_A, fC_B = examples.get_example7_factors()
        fAfB = fA * fB_A
        fBfC = fAfB.sum_out('A') * fC_B

        fC = fBfC.project({'C'})
        self.assertAlmostEquals(fC['c0'], 0.624, places=8)
        self.assertAlmostEquals(fC['c1'], 0.376, places=8)
        self.assertAlmostEquals(fC.sum(), 1, places=8)

        self.assertTrue(fA.project('A').equals(fA))

    def test_from_data(self):
        """Test creating an (empirical) distribution from data."""
        filename = thomas.core.get_pkg_data('dataset_17_2.csv')
        df = pd.read_csv(filename, sep=';')

        scope = ['H', 'S', 'E']
        factor = Factor.from_data(df, cols=scope)

        self.assertEqual(set(factor.scope), set(scope))
        self.assertEqual(factor.sum(), 16)

    def test_serialization_simple(self):
        """Test the JSON serialization."""
        [fA, fB_A, fC_A, fD_BC, fE_C] = examples.get_sprinkler_factors()

        dict_repr = fA.as_dict()

        # Make sure the expected keys exist
        for key in ['type', 'scope', 'states', 'data']:
            self.assertTrue(key in dict_repr)

        self.assertTrue(dict_repr['type'] == 'Factor')

        fA2 = Factor.from_dict(dict_repr)
        self.assertEquals(fA.variables, fA2.variables)
        self.assertEquals(fA.states, fA2.states)

    def test_serialization_complex(self):
        """Test the JSON serialization."""
        [fA, fB_A, fC_A, fD_BC, fE_C] = examples.get_sprinkler_factors()

        dict_repr = fB_A.as_dict()

        # Make sure the expected keys exist
        for key in ['type', 'scope', 'states', 'data']:
            self.assertTrue(key in dict_repr)

        self.assertTrue(dict_repr['type'] == 'Factor')

        fB_A2 = Factor.from_dict(dict_repr)
        self.assertEquals(fB_A.scope, fB_A2.scope)
        self.assertEquals(fB_A.states, fB_A2.states)

    def test_values(self):
        """Test cast to np.array."""
        fA = Factor(
            [0.6, 0.4],
            {'A': ['a1', 'a0']}
        )

        self.assertTrue(isinstance(fA.values, np.ndarray))

    def test_error(self):
        factors = examples.get_sprinkler_factors()
        fB_A = factors[1]

        with self.assertRaises(error.NotInScopeError) as context:
            fB_A.sum_out('C')

        # with self.assertRaises(error.InvalidStateError) as context:
        #     fB_A.keep_values(A='a2')

    # @unittest.skip('deprecate?')
    # def test_unstack(self):
    #     """Test factor.unstack()."""
    #     fA, fB_A, fC_A, fD_BC, fE_C = examples.get_sprinkler_factors()
    #
    #     unstacked = fB_A.unstack()
    #
    #     self.assertIsInstance(unstacked, pd.DataFrame)
    #     self.assertEqual(unstacked.shape, (2, 2))
