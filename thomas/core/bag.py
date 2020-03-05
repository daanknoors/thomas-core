# -*- coding: utf-8 -*-
"""Bag: collection of Factors."""
import os
from datetime import datetime as dt

from collections import OrderedDict

import numpy as np
import pandas as pd
from pandas.core.dtypes.dtypes import CategoricalDtype
from functools import reduce

import json

from .base import ProbabilisticModel, remove_none_values_from_dict
from .factor import Factor, mul
from .cpt import CPT

from . import error

import logging
log = logging.getLogger('thomas')

# ------------------------------------------------------------------------------
# Bag
# ------------------------------------------------------------------------------
class Bag(ProbabilisticModel):
    """Bag of factors."""

    def __init__(self, name='', factors=None):
        """Instantiate a new Bag."""
        msg = f'factors should be a list, not a {type(factors)}'
        assert isinstance(factors, list), msg

        self.name = name
        self._factors = factors

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return f"<Bag: '{self.name}'>"

    def __len__(self):
        """len(f) == f.__len__()"""
        return len(self._factors)

    def _scope(self, factors):
        """Return the scope of a set of factors.

        This comprises the set of (unique) variables covered by the factors.
        """
        scope = []

        for f in factors:
            scope += f.scope

        return set(scope)

    # --- properties ---
    @property
    def scope(self):
        """Return the network scope."""
        return self._scope(self._factors)

    # --- inference ---
    def find_elimination_ordering(self, Q, factors):
        """Return a variable ordering for a set of factors.

        The result will only contain variables *not* in Q.
        """
        scope = self._scope(factors)
        return [v for v in scope if v not in Q]

    def eliminate(self, Q, e=None):
        """Perform variable elimination."""
        if e is None: e = {}

        # Initialize the list of factors
        factors = list(self._factors)

        # Apply the evidence
        try:
            factors = [f.keep_values(**e) for f in factors]
        except error.InvalidStateError as e:
            # Actually, don't deal with this here ...
            raise

        # ordering will contain a list of variables *not* in Q, i.e. the
        # remaining variables from the full distribution.
        ordering = self.find_elimination_ordering(Q, factors)

        # Iterate over the variables in the ordering.
        for X in ordering:
            # Find factors that have the current variable 'X' in scope
            related_factors = [f for f in factors if X in f.scope]

            # Multiply all related factors with each other and sum out 'X'
            try:
                new_factor = reduce(mul, related_factors)

            except Exception as e:
                log.error('Could not reduce list of factors!?')
                log.exception(e)
                raise e

            new_factor = new_factor.sum_out(X)

            # Replace the factors we have eliminated with the new factor.
            factors = [f for f in factors if f not in related_factors]
            factors.append(new_factor)

        result = reduce(mul, factors)

        try:
            result = result.reorder_scope(Q)

        except Exception as e:
            log.error('exception while reordering scope')
            log.exception(e)
            log.error('Q:', Q)
            log.error('result.scope:', result.scope)
            log.error('result:', result)
            raise

        result.sort_index()

        return result

    def compute_posterior(self, qd, qv, ed, ev):
        """Compute the probability of the query variables given the evidence.

        The query P(I,G=g1|D,L=l0) would imply:
            qd = ['I']
            qv = {'G': 'g1'}
            ed = ('D',)
            ev = {'L': 'l0'}

        Args:
            qd (list): query distributions: RVs to query
            qv (dict): query values: RV-values to extract
            ed (list): evidence distributions: coniditioning RVs to include
            ev (dict): evidence values: values to set as evidence.

        Returns:
            CPT
        """
        ev = remove_none_values_from_dict(ev)

        # Get a list of *all* variables to query
        query_vars = list(qv.keys()) + qd
        evidence_vars = list(ev.keys()) + ed

        # First, compute the joint over the query variables and the evidence.
        result = self.eliminate(query_vars + ed, ev)
        result = result.normalize()

        # At this point, result's scope is over all query and evidence variables
        # If we're computing an entire conditional distribution ...
        if evidence_vars:
            try:
                result = result / result.sum_out(query_vars)
            except Exception as e:
                log.error('-' * 80)
                log.error(f'trying to sum out {query_vars}')
                log.error(result)
                log.error('-' * 80)
                log.exception(e)
                raise

        # If query values were specified we can extract them from the factor.
        if qv:
            values = list(qv.values())

            if result.width == 1:
                result = result[values[0]]

            elif result.width > 1:
                indices = []

                for level, value in qv.items():
                    idx = result._data.index.get_level_values(level) == value
                    indices.append(list(idx))

                zipped = list(zip(*indices))
                idx = [all(x) for x in zipped]
                result = Factor(result._data[idx])

        if isinstance(result, Factor):
            result.sort_index()
            return CPT(result, conditioned_variables=query_vars)

        return result

    # --- (de)serialization and conversion ---
    def as_dict(self):
        """Return a dict representation of this Bag."""
        return {
            'type': 'Bag',
            'name': self.name,
            'factors': [f.as_dict() for f in self._factors]
        }

