# -*- coding: utf-8 -*-
import unittest
import doctest
import logging

from thomas.core.base import ProbabilisticModel
from thomas.core import examples

log = logging.getLogger(__name__)

class TestProbabilisticModel(unittest.TestCase):

    def test_compute_posterior(self):

        model = ProbabilisticModel()

        with self.assertRaises(NotImplementedError) as context:
            model.compute_posterior([], {}, [], {})