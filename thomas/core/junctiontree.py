# -*- coding: utf-8 -*-
"""JunctionTree"""
import networkx as nx
from networkx.algorithms.shortest_paths.generic import shortest_path

from functools import reduce

from .util import sep
from .factor import mul, Factor
# ------------------------------------------------------------------------------
# JunctionTree
# ------------------------------------------------------------------------------
class JunctionTree(object):
    """JunctionTree for a BayesianNetwork.


    The tree consists of TreeNodes and TreeEdges.
    """

    def __init__(self, bn):
        """Initialize a new JunctionTree.

        Args:
            clusters (list): list of sets of RVs.
        """
        self._bn = bn

        self.nodes = {}      # TreeNode, indexed by cluster.label
        self.edges = []
        self.indicators = {} # evidence indicators; indexed by RV
        self._RVs = {}       # TreeNode, indexed by RV and

        # Create the structure.
        self.clusters = self._get_elimination_clusters()
        self._create_structure()

        # Assign factors & evidence indicators.
        self._assign_factors(bn)

    def _get_elimination_clusters(self):
        """Compute the clusters for the elimination tree."""

        bn = self._bn

        # Get the full set of clusters.
        edges = bn.moralize_graph()
        order = bn.get_node_elimination_order()
        clusters = self._get_elimination_clusters_rec(edges, order)

        # Merge clusters that are contained in other clusters by iterating over
        # the full set and replacing the smaller with the larger clusters.
        merged = list(clusters)
        clusters = list(clusters)

        # We should merge later clusters into earlier clusters.
        # The reversion is undone just before the function returns.
        clusters.reverse()

        should_continue = len(clusters) > 1
        while should_continue:
            should_continue = False

            for idx_i in range(len(clusters)):
                modified = False
                C_i = clusters[idx_i]

                for idx_j in range(idx_i+1, len(clusters)):
                    C_j = clusters[idx_j]

                    if C_i.issubset(C_j):
                        clusters[idx_i] = C_j
                        clusters.pop(idx_j)

                        modified = True
                        should_continue = len(clusters) > 1

                        # Break from the inner for-loop
                        break

                if modified:
                    # Break from the outer for-loop
                    break

        # Undo the earlier reversion.
        clusters.reverse()
        return clusters

    def _get_elimination_clusters_rec(self, edges, order):
        """Recursively compute the clusters for the elimination tree.

        Args:
            edges (list): List of edges that make up the (remaining) Graph.
            order (list): Elimination order.

        Returns:
            list of clusters (i.e. sets of RVs)
        """
        if edges is None:
            edges = bn.moralize_graph()

        if order is None:
            order = bn.get_node_elimination_order()

        # Create a copy to make sure we're not modifying the method argument.
        order = list(order)

        if not len(order):
            return []

        # Reconstruct the graph
        G = nx.Graph()
        G.add_nodes_from(order)
        G.add_edges_from(edges)

        node = order.pop(0)

        # Make sure the neighbors from `node` are connected by adding fill-in
        # edges.
        neighbors = list(G.neighbors(node))

        if len(neighbors) > 1:
            for outer_idx in range(len(neighbors)):
                n1 = neighbors[outer_idx]

                for inner_idx in range(outer_idx+1, len(neighbors)):
                    n2 = neighbors[inner_idx]
                    G.add_edge(n1, n2)

        G.remove_node(node)
        cluster = set([node, ] + neighbors)

        return [cluster, ] + self._get_elimination_clusters_rec(G.edges, order)

    def _create_structure(self):
        """Create the tree's structure (i.e. add edges) using the clusters."""

        # Each cluster is added to a TreeNode by reference, meaning that any
        # changes to `node.cluster` are also reflected in `self.clusters`.
        for c in self.clusters:
            self.add_node(c)

        # The nodes contain a variable `cluster` that corresponds to one of the
        # tree's clusters. The order is equivalent to `self.clusters`.
        nodes = list(self.nodes.values())

        # Iterate over the tree's nodes to find a neighbor for each node.
        # We need to cast the iterator to a list to use reversed()
        for idx, node_i in reversed(list(enumerate(nodes))):
            C_i = node_i.cluster

            # `remaining_nodes` will hold clusters C_i+1 , C_i+2, .... C_n
            remaining_nodes = nodes[idx+1:]

            if remaining_nodes:
                remaining_clusters = [n.cluster for n in remaining_nodes]

                # We'll compute union over the remaining clusters and determine
                # the intersection with the current cluster.
                intersection = C_i.intersection(set.union(*remaining_clusters))
                found = False

                # According to the running intersection property, there should
                # be a node/cluster that contains the above intersection.
                for node_j in remaining_nodes:
                    C_j = node_j.cluster

                    if intersection.issubset(C_j):
                        self.add_edge(node_i, node_j)
                        found = True
                        break

                if not found:
                    print('*** WARNING ***')
                    print('Could not add node_i: ', node_i)
                    print('C_i:', C_i)
                    print('remaining_clusters:')
                    for r in remaining_clusters:
                        print('  ', r)
                    print()

                    # Stop it right there!
                    msg = 'Could not find cluster/node containing intersection.'
                    raise Exception(msg)

    def _assign_factors(self, bn):
        """Assign the BNs factors (nodes) to one of the clusters."""

        bn = self._bn

        # Iterate over all nodes in the BN to assign each BN node/CPT to the
        # first TreeNode that contains the BN node's RV. Also, assign an evidence
        # indicator for that variable to that JT node.
        for RV, bn_node in bn.nodes.items():
            # Iterate over the JT nodes/clusters
            for jt_node in self.nodes.values():
                # node.vars returns all variables in the node's factor
                if bn_node.vars.issubset(jt_node.cluster):
                    jt_node.add_factor(bn_node.cpt)
                    self.set_node_for_RV(RV, jt_node)

                    states = {RV: bn_node.states}
                    indicator = Factor(1, variable_states=states)
                    self.add_indicator(indicator, jt_node)
                    break

        # Iterate over the JT nodes/clusters to make sure each cluster has
        # the correct factors assigned.
        for jt_node in self.nodes.values():
            try:
                for missing in (jt_node.cluster - jt_node.vars):
                    bn_node = bn.nodes[missing]
                    states = {bn_node.RV: bn_node.states}
                    trivial = Factor(1, variable_states=states)
                    jt_node.add_factor(trivial)
            except:
                print('*** WARNING ***')
                print('jt_node.cluster:', jt_node.cluster)
                print('jt_node.vars:', jt_node.vars)

    def ensure_cluster(self, cluster):
        """Ensure cluster is contained in one of the nodes."""
        if isinstance(cluster, list):
            Q = set(cluster)
        else:
            Q = cluster

        if self.get_node_for_set(Q):
            return

        # Find the (first) node that has the maximum overlap with Q
        overlap = [len(Q.intersection(c)) for c in self.clusters]
        idx = overlap.index(max(overlap))
        cluster = self.clusters[idx]
        node = self.get_node_for_set(cluster)

        # Determine which variables are missing in the cluster
        missing = Q - node.cluster

        # Convert the JT to a NetworkX graph, so we can use it's implementation
        # of Dijkstra's shortest path later.
        G = self.as_networkx()

        for var in missing:
            # Find a path to the nearest node that contains `var`.
            # There may be multiple nodes that contain `var`, so first list all
            # targets.
            targets = [n for n in self.nodes.values() if var in n.cluster]
            paths = []

            for target in targets:
                paths.append(shortest_path(G, node, target))

            distances = [len(p) for p in paths]
            idx = distances.index(min(distances))
            path = paths[idx]

            states = self._bn.nodes[var].states

            for tree_node in path:
                # path includes the target node, which already has `var`
                # in scope
                if var not in tree_node.cluster:
                    f = Factor(1, variable_states={var: states})
                    tree_node.add_factor(f)

    def get_node_for_RV(self, RV):
        """A[x] <==> A.__getitem__(x)"""
        return self._RVs[RV]

    def set_node_for_RV(self, RV, node):
        """A[x] = y <==> A.__setitem__(x, y)"""
        self._RVs[RV] = node

    def get_node_for_set(self, RVs):
        """Return the node that contains RVs or None.

        :param (set) RVs: set of RV names (strings)
        :return: TreeNode
        """
        for node in self.nodes.values():
            if RVs.issubset(node.cluster):
                return node

        return None

    def get_marginal(self, RV):
        return self.get_node_for_RV(RV).project(RV)

    def get_marginals(self, RVs=None):
        """Return the probabilities for a set off/all RVs given set evidence."""
        if RVs is None:
            RVs = self._RVs

        return {RV: self.get_node_for_RV(RV).project(RV) for RV in RVs}

    def add_node(self, cluster, factors=None, evidence=False):
        """Add a node to the tree."""

        # FIXME: I don't think `evidence` is ever set to True in the
        #        current implementation.
        if evidence:
            node = EvidenceNode(cluster, factors)
        else:
            node = TreeNode(cluster, factors)

        self.nodes[node.label] = node
        return node

    def add_edge(self, node1, node2):
        """Add an edge between two nodes."""
        if isinstance(node1, str):
            node1 = self.nodes[node1]

        if isinstance(node2, str):
            node2 = self.nodes[node2]

        self.edges.append(TreeEdge(node1, node2))
        # Adding an edge requires us to recompute the separators.

    def add_indicator(self, factor, node):
        """Add an indicator for a random variable to a node."""
        if isinstance(node, str):
            node = self.nodes[node]

        RV = list(factor.variable_states.keys()).pop()
        self.indicators[RV] = factor
        node.indicators.append(factor)

    def reset_evidence(self, RVs=None):
        """Reset evidence for one or more RVs."""
        if RVs is None:
            RVs = self.indicators

        elif isinstance(RVs, str):
            RVs = [RVs]

        for RV in RVs:
            indicator = self.indicators[RV]
            indicator._data[:] = 1.0

        self.invalidate_caches()

    def set_evidence_likelihood(self, RV, **kwargs):
        """Set likelihood evidence on a variable."""
        indicator = self.indicators[RV]

        # FIXME: it's not pretty to access Factor._data like this!
        data = indicator._data

        for state, value in kwargs.items():
            data[state] = value

        self.invalidate_caches()

    def set_evidence_hard(self, **kwargs):
        """Set hard evidence on a variable.

        This corresponds to setting the likelihood of the provided state to 1
        and the likelihood of all other states to 0.

        Kwargs:
            evidence (dict): dict with states, indexed by RV: {RV: state}
                             e.g. use as set_evidence_hard(G='g1')
        """
        for RV, state in kwargs.items():
            indicator = self.indicators[RV]

            if state not in indicator.index.get_level_values(RV):
                state = state.replace(f'{RV}.', '')
                raise e.InvalidStateError(RV, state, self)

            # FIXME: it's not pretty to access Factor._data like this!
            data = indicator._data
            idx = data.index.get_level_values(RV) != state
            data[idx] = 0.0

            idx = data.index.get_level_values(RV) == state
            data[idx] = 1.0

        self.invalidate_caches()

    def invalidate_caches(self):
        """Invalidate the nodes' caches."""
        for n in self.nodes.values():
            n.invalidate_cache()

    def run(self):
        for n in self.nodes.values():
            n.pull()

    def compute_posterior(self, query_dist, query_values, evidence_dist,
        evidence_values, **kwargs):
        """Compute the probability of the query variables given the evidence.

        The query P(I,G=g1|D,L=l0) would imply:
            query_dist = ['I']
            query_values = {'G': 'g1'}
            evidence_dist = ('D',)
            evidence_values = {'L': 'l0'}

        :param tuple query_dist: Random variable to query
        :param dict query_values: Random variable values to query
        :param tuple evidence_dist: Conditioned on evidence
        :param dict evidence_values: Conditioned on values
        :return: pandas.Series (possibly with MultiIndex)
        """
        Q = set(query_dist)
        for n in self.nodes.values():
            if Q in n.cluster:
                return n

    def as_networkx(self):
        """Return the JunctionTree as a networkx.Graph() instance."""
        G = nx.Graph()

        for e in self.edges:
            G.add_edge(e._left, e._right, label=','.join(e.separator))

        return G

    def draw(self):
        """Draw the JunctionTree using networkx & matplotlib."""
        nx_tree = self.as_networkx()
        pos = nx.spring_layout(nx_tree)

        nx.draw(
            nx_tree,
            pos,
            edge_color='black',
            width=1,
            linewidths=1,
            node_size=1500,
            node_color='pink',
            alpha=1.0,
            labels={node:node.label for node in nx_tree.nodes}
        )

        nx.draw_networkx_edge_labels(
            nx_tree,
            pos,
            edge_labels={key:value['label'] for key,value in nx_tree.edges.items()},
            font_color='red'
        )

# ------------------------------------------------------------------------------
# TreeEdge
# ------------------------------------------------------------------------------
class TreeEdge(object):
    """Edge in an elimination/junction tree."""

    def __init__(self, node1, node2):
        """Create a new (undirected) TreeEdge.

        Args:
            node1 (TreeNode): node 1
            node1 (TreeNode): node 2
        """
        # Left/right are arbitrary.
        self._left = node1
        self._right = node2
        self._separator = None

        node1.add_neighbor(self)
        node2.add_neighbor(self)

    def __repr__(self):
        """repr(x) <==> x.__repr__()"""
        return f'Edge: ({repr(self._left)} - {repr(self._right)})'

    def __getitem__(self, key):
        """a[key] <==> a.__getitem__(key) <==> a.get_neighbor(key)"""
        return self.get_neighbor(key)

    @property
    def separator(self):
        """Return/compute the separator on this edge."""
        if self._separator is None:
            self.recompute_separator()

        return self._separator

    def get_neighbor(self, node):
        """Return the neighbor for `node`."""
        if node == self._left:
            return self._right

        if node == self._right:
            return self._left

        raise Exception('Supplied node is not connected to this edge!?')

    def recompute_separator(self):
        """(re)compute the separator for this Edge."""
        left_downstream = self._left.get_all_downstream_nodes(self)
        right_downstream = self._right.get_all_downstream_nodes(self)

        left_cluster = set.union(*[n.cluster for n in left_downstream])
        right_cluster = set.union(*[n.cluster for n in right_downstream])

        self._separator = set.intersection(left_cluster, right_cluster)

# ------------------------------------------------------------------------------
# TreeNode
# ------------------------------------------------------------------------------
class TreeNode(object):
    """Node in an elimination/junction tree."""

    def __init__(self, cluster, factors=None):
        """Create a new node.

        Args:
            cluster (set): set of RV names (strings)
            factors (list): CPTs for the RVs in the cluster
        """
        self.cluster = cluster
        self.indicators = []

        if factors:      # list: Factor
            self._factors = factors
        else:
            self._factors = []

        self._edges = [] # list: TreeEdge
        self._factors_multiplied = None   # cache

        # The cache is indexed by upstream node.
        self.invalidate_cache() # sets self._cache = {}

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        # return self.label
        return f"TreeNode({self.cluster})"

    @property
    def label(self):
        """Return the Node's label."""
        return ','.join(self.cluster)

    @property
    def factors(self):
        return self._factors + self.indicators

    @property
    def vars(self):
        v = [f.vars for f in self.factors]
        if v:
            return set.union(*v)
        return set()

    @property
    def joint(self):
        return self.pull()

    @property
    def factors_multiplied(self):
        """Compute the joint of the Node's factors."""
        if self._factors_multiplied is None:
            factors = self._factors + self.indicators

            # Per documentation for reduce: "If initializer is not given and
            # sequence contains only one item, the first item is returned."
            try:
                self._factors_multiplied = reduce(mul, factors)
            except:
                print('*** ERROR ***')
                print('Error while trying to compute the joint distribution')
                print(f'Node: {self.cluster}')
                print(f'Factors:', factors)
                raise

        return self._factors_multiplied

    def add_neighbor(self, edge):
        if edge not in self._edges:
            self._edges.append(edge)

    def add_factor(self, factor):
        """Add a factor to this Node."""
        self._factors.append(factor)
        self._factors_multiplied = None

        # This can do harm
        for var in factor.vars:
            self.cluster.add(var)

        for edge in self._edges:
            edge.recompute_separator()

    def invalidate_cache(self):
        """Invalidate the cache.

        This comprises the message cache and the joint distribution for the
        cluster with indicators.
        """
        self._cache = {}
        self._factors_multiplied = None

    def get_downstream_edges(self, upstream=None):
        return [e for e in self._edges if e is not upstream]

    def get_all_downstream_nodes(self, upstream=None):
        edges = self.get_downstream_edges(upstream)

        if upstream is None:
            downstream = {}

            # edges is a list: TreeEdge
            for e in edges:
                downstream[e] = e.get_neighbor(self).get_all_downstream_nodes(e)

            return downstream

        downstream = []

        for edge in edges:
            node = edge.get_neighbor(self)
            downstream.extend(node.get_all_downstream_nodes(edge))

        return [self, ] + downstream

    def pull(self, upstream=None):
        """Trigger pulling of messages towards this node.

        This entails:
         - calling pull() on each of the downstream edges
         - multiplying the results into this factor
         - if an upstream edge is specified, the result is projected onto the
           upstream edge's separator.

        :return: factor.Factor
        """
        downstream_edges = self.get_downstream_edges(upstream)
        result = self.factors_multiplied

        if downstream_edges:
            downstream_results = []

            for e in downstream_edges:
                if e not in self._cache:
                    n = e.get_neighbor(self)
                    self._cache[e] = n.pull(e)

                downstream_results.append(self._cache[e])

            result = reduce(mul, downstream_results + [result])

        if upstream:
            return result.project(upstream.separator)

        return result

    def project(self, RV, normalize=True):
        """Trigger a pull and project the result onto RV.

        RV should be contained in the Node's cluster.
        Cave: note that TreeNode.project() has a different default behaviour
              compared to Factor.project(): it normalizes the result by default!

        Args:
            RV (str or set): ...
            normalize (bool): normalize the projection?

        Returns:
            ...
        """
        result = self.pull().project(RV)

        if normalize:
            return result.normalize()

        return result

# ------------------------------------------------------------------------------
# EvidenceNode
# ------------------------------------------------------------------------------
class EvidenceNode(TreeNode):
    """Node that can be used to set evidence or compute the prior."""

    def __init__(self, cluster, factors=None):
        """Initialize a new node."""
        msg = "EvidenceNode cluster can only contain a single variable."
        assert len(cluster) == 1, msg
        assert factors is None or len(factors) == 1, msg

        super().__init__(cluster, factors)

    @property
    def factor(self):
        return self._factors[0]

    def add_factor(self, factor):
        if len(factors) > 0:
            raise Exception('EvidenceNode can only contain a single variable.')

        super().add_factor(factors)

    def add_neighbor(self, edge):
        if edge not in self._edges:
            if len(self._edges) > 1:
                raise Exception('EvidenceNode can only contain a single variable.')

            super().add_neighbor(edge)
