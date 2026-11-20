"""Molecules as graphs and matrices: the code of the lesson, in order.

A molecule is a graph of atoms and bonds; as matrices it becomes something algorithms and models can compute on.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/01-graphs-and-matrices/
Run from the series folder: uv run python <this folder>/code.py
"""

# ---- 1. A molecule is a graph ----
from rdkit import Chem

aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
print(aspirin.GetNumAtoms(), "heavy atoms,", aspirin.GetNumBonds(), "bonds")
for atom in list(aspirin.GetAtoms())[:5]:
    neighbours = [n.GetIdx() for n in atom.GetNeighbors()]
    print(f"atom {atom.GetIdx()}: {atom.GetSymbol()}, bonded to {neighbours}")
import networkx as nx


def to_graph(mol):
    """A molecule as a NetworkX graph: atoms as nodes, bonds as edges, each with its properties."""
    g = nx.Graph()
    for atom in mol.GetAtoms():
        g.add_node(
            atom.GetIdx(),
            element=atom.GetSymbol(),
            hydrogens=atom.GetTotalNumHs(),
            charge=atom.GetFormalCharge(),
            aromatic=atom.GetIsAromatic(),
        )
    for bond in mol.GetBonds():
        g.add_edge(
            bond.GetBeginAtomIdx(),
            bond.GetEndAtomIdx(),
            bond_type=str(bond.GetBondType()),
            order=bond.GetBondTypeAsDouble(),
        )
    return g


graph = to_graph(aspirin)
print(graph.number_of_nodes(), "nodes,", graph.number_of_edges(), "edges")
print("rings:", [sorted(ring) for ring in nx.cycle_basis(graph)])
print("bonds between the two carbonyl carbons:", nx.shortest_path_length(graph, 1, 10))

# ---- 2. Molecules as matrices ----
import numpy as np
import pandas as pd

acetic_acid = Chem.MolFromSmiles("CC(=O)O")
g = to_graph(acetic_acid)
atoms = sorted(g)
labels = [f"{g.nodes[i]['element']}{i}" for i in atoms]
adjacency = nx.to_numpy_array(g, nodelist=atoms, weight=None, dtype=int)
print(pd.DataFrame(adjacency, index=labels, columns=labels))
print("symmetric:", bool((adjacency == adjacency.T).all()))
print("bonds per atom (row sums):", adjacency.sum(axis=1).tolist())
print("same as RDKit's:", bool((adjacency == Chem.GetAdjacencyMatrix(acetic_acid)).all()))

# ---- Encoding a molecule's properties ----
orders = nx.to_numpy_array(g, nodelist=atoms, weight="order")
print(pd.DataFrame(orders, index=labels, columns=labels))
ELEMENTS = ["C", "N", "O"]


def atom_features(data):
    element = [int(data["element"] == e) for e in ELEMENTS]
    other = int(data["element"] not in ELEMENTS)
    return [*element, other, data["hydrogens"], data["charge"], int(data["aromatic"])]


columns = [*ELEMENTS, "other", "hydrogens", "charge", "aromatic"]
X = np.array([atom_features(g.nodes[i]) for i in atoms])
print(pd.DataFrame(X, index=labels, columns=columns))
BOND_TYPES = ["SINGLE", "DOUBLE", "TRIPLE", "AROMATIC"]
tensor = np.zeros((len(BOND_TYPES), len(atoms), len(atoms)), dtype=int)
for i, j, data in g.edges(data=True):
    k = BOND_TYPES.index(data["bond_type"])
    tensor[k, i, j] = tensor[k, j, i] = 1
for name, layer in zip(BOND_TYPES[:2], tensor[:2], strict=True):
    print(f"{name} bonds:")
    print(pd.DataFrame(layer, index=labels, columns=labels))
print("shape of the bond tensor (types, atoms, atoms):", tensor.shape)
pairs = [(i, j) for i, j in g.edges()] + [(j, i) for i, j in g.edges()]
edge_index = np.array(pairs).T
edge_features = np.array(
    [[int(g.edges[i, j]["bond_type"] == t) for t in BOND_TYPES] for i, j in pairs]
)
print("edge index (from, to):")
print(edge_index)
print("edge features (one-hot bond type):")
print(pd.DataFrame(edge_features, columns=BOND_TYPES, index=[f"{i}-{j}" for i, j in pairs]))

# ---- Distances ----
aspirin_graph = to_graph(aspirin)
distances = nx.floyd_warshall_numpy(aspirin_graph, nodelist=sorted(aspirin_graph))
print("bonds between the two carbonyl carbons:", int(distances[1, 10]))
print("the two atoms furthest apart are", int(distances.max()), "bonds apart")
print("same as RDKit's:", bool((distances == Chem.GetDistanceMatrix(aspirin)).all()))

# ---- Graph operations with NumPy ----
A = nx.to_numpy_array(aspirin_graph, nodelist=sorted(aspirin_graph), weight=None, dtype=int)
print("degrees:", A.sum(axis=1).tolist())
print("neighbours of atom 4:", np.nonzero(A[4])[0].tolist())
A2 = A @ A
print("two-bond walks from atom 1 to atom 4:", int(A2[1, 4]))
print("diagonal of A @ A equals the degrees:", bool((np.diag(A2) == A.sum(axis=1)).all()))
aspirin_atoms = sorted(aspirin_graph)
aspirin_labels = [f"{aspirin_graph.nodes[i]['element']}{i}" for i in aspirin_atoms]
X_aspirin = np.array([atom_features(aspirin_graph.nodes[i]) for i in aspirin_atoms])
messages = A @ X_aspirin
print(pd.DataFrame(messages, index=aspirin_labels, columns=columns).head(5))
salt = Chem.MolFromSmiles("CC(=O)[O-].[Na+]")
A_salt = Chem.GetAdjacencyMatrix(salt)
laplacian = np.diag(A_salt.sum(axis=1)) - A_salt
eigenvalues = np.linalg.eigvalsh(laplacian)
print(
    "Laplacian eigenvalues:", (np.round(eigenvalues, 3) + 0.0).tolist()
)  # + 0.0 turns -0.0 into 0.0
print(
    "pieces:", int(np.isclose(eigenvalues, 0).sum()), " RDKit agrees:", len(Chem.GetMolFrags(salt))
)
