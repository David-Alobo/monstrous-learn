---
title: Representing molecules
summary: How a computer holds a molecule, what each representation keeps and loses, and which to store for which job.
---

A chemist looks at a drawing and sees aspirin. A computer sees nothing until the molecule is
written down as text, numbers or a graph, and every way of writing it down keeps some things and
loses others. Data engineering for chemistry starts here: before we can store, search, clean or
scale anything, we have to decide what a molecule *is* inside our systems.

By the end of this module you will be able to:

- read a molecule into RDKit and walk through its atoms and bonds;
- write a molecule as matrices: adjacency, bond orders, distances and atom features;
- explain why one molecule has many SMILES but one canonical SMILES;
- tell what a representation keeps and what it loses (stereochemistry, aromaticity, tautomers);
- use InChIKey as a molecule's identity, and SMARTS as a search pattern;
- turn molecules into fingerprints and descriptors for comparison and machine learning;
- choose what to store, for which job.

Everything here runs in a browser notebook or on any laptop: you need Python and RDKit only.

## 1. A molecule is a graph

To RDKit, a molecule is a graph: **atoms are nodes and bonds are edges**. Hydrogens are usually
left implicit, so only the heavy atoms appear. Here is aspirin, with every atom numbered in the
order RDKit reads it:

![Aspirin drawn by RDKit with every atom numbered](figures/aspirin-atoms.svg)

```python
from rdkit import Chem

aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
print(aspirin.GetNumAtoms(), "heavy atoms,", aspirin.GetNumBonds(), "bonds")
for atom in list(aspirin.GetAtoms())[:5]:
    neighbours = [n.GetIdx() for n in atom.GetNeighbors()]
    print(f"atom {atom.GetIdx()}: {atom.GetSymbol()}, bonded to {neighbours}")
```
```output
13 heavy atoms, 13 bonds
atom 0: C, bonded to [1]
atom 1: C, bonded to [0, 2, 3]
atom 2: O, bonded to [1]
atom 3: O, bonded to [1, 4]
atom 4: C, bonded to [3, 5, 9]
```

The same molecule as a plain graph, the way a graph library or a graph database sees it: nodes
carry the element, edges carry the bond order.

![Aspirin as a graph: atoms as circles, bonds as lines](figures/aspirin-graph.svg)

```python
import networkx as nx


def to_graph(mol):
    """A molecule as a NetworkX graph: atoms as nodes, bonds as edges."""
    g = nx.Graph()
    for atom in mol.GetAtoms():
        g.add_node(atom.GetIdx(), element=atom.GetSymbol())
    for bond in mol.GetBonds():
        g.add_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), order=str(bond.GetBondType()))
    return g


graph = to_graph(aspirin)
print(graph.number_of_nodes(), "nodes,", graph.number_of_edges(), "edges")
print("rings:", [sorted(ring) for ring in nx.cycle_basis(graph)])
print("bonds between the two carbonyl carbons:", nx.shortest_path_length(graph, 1, 10))
```
```output
13 nodes, 13 edges
rings: [[4, 5, 6, 7, 8, 9]]
bonds between the two carbonyl carbons: 4
```

Graph questions (rings, paths, which atoms are connected) are chemistry questions. Module 4 comes
back to this when we store molecules in a graph database.

## 2. Molecules as matrices

The same graph can be written as matrices, which is how many algorithms, and graph neural networks
in particular, see a molecule. The **adjacency matrix** has one row and one column per atom, with a
1 where two atoms are bonded. Here it is for acetic acid, with each atom labelled by element and
index:

```python
import pandas as pd

acetic_acid = Chem.MolFromSmiles("CC(=O)O")
labels = [f"{atom.GetSymbol()}{atom.GetIdx()}" for atom in acetic_acid.GetAtoms()]
adjacency = Chem.GetAdjacencyMatrix(acetic_acid)
print(pd.DataFrame(adjacency, index=labels, columns=labels))
print("symmetric:", bool((adjacency == adjacency.T).all()))
print("bonds per atom (row sums):", adjacency.sum(axis=1).tolist())
```
```output
    C0  C1  O2  O3
C0   0   1   0   0
C1   1   0   1   1
O2   0   1   0   0
O3   0   1   0   0
symmetric: True
bonds per atom (row sums): [1, 3, 1, 1]
```

Bonds have no direction, so the matrix is symmetric, and each row adds up to the number of bonds
that atom makes (its degree). Ask for bond orders and the 1s become 1, 1.5 (aromatic), 2 or 3:

```python
orders = Chem.GetAdjacencyMatrix(acetic_acid, useBO=True)
print(pd.DataFrame(orders, index=labels, columns=labels))
```
```output
     C0   C1   O2   O3
C0  0.0  1.0  0.0  0.0
C1  1.0  0.0  2.0  1.0
O2  0.0  2.0  0.0  0.0
O3  0.0  1.0  0.0  0.0
```

For aspirin the matrix is 13 by 13 and mostly zeros: each atom is bonded to only a few others.

![Aspirin's adjacency matrix as a grid: a coloured square wherever two atoms are bonded, darker for double and aromatic bonds](figures/aspirin-adjacency.svg)

The **distance matrix** counts the bonds on the shortest path between every pair of atoms, the same
answer the graph gave above:

```python
distances = Chem.GetDistanceMatrix(aspirin)
print("bonds between the two carbonyl carbons:", int(distances[1, 10]))
print("the two atoms furthest apart are", int(distances.max()), "bonds apart")
```
```output
bonds between the two carbonyl carbons: 4
the two atoms furthest apart are 6 bonds apart
```

A model also needs to know what each atom *is*. An **atom feature matrix** has one row per atom and
one column per property; together with the adjacency matrix it is the usual input to a graph neural
network (the MLOps track returns to this):

```python
features = pd.DataFrame(
    [
        {
            "atom": f"{atom.GetSymbol()}{atom.GetIdx()}",
            "atomic_number": atom.GetAtomicNum(),
            "degree": atom.GetDegree(),
            "hydrogens": atom.GetTotalNumHs(),
            "aromatic": int(atom.GetIsAromatic()),
        }
        for atom in aspirin.GetAtoms()
    ]
)
print(features.head(6).to_string(index=False))
print(
    "aspirin as matrices:",
    Chem.GetAdjacencyMatrix(aspirin).shape,
    "adjacency,",
    features.drop(columns="atom").shape,
    "atom features",
)
```
```output
atom  atomic_number  degree  hydrogens  aromatic
  C0              6       1          3         0
  C1              6       3          0         0
  O2              8       1          0         0
  O3              8       2          0         0
  C4              6       3          0         1
  C5              6       2          1         1
aspirin as matrices: (13, 13) adjacency, (13, 4) atom features
```

Matrices are convenient for computation but wasteful for storage: an adjacency matrix grows with
the square of the number of atoms, while a list of bonds grows only with the bonds. Store the
molecule (or its bond list) and build matrices when an algorithm needs them.

## 3. SMILES: one molecule, many strings

SMILES writes the graph as a line of text by walking through it. There are many valid walks, so
one molecule has many SMILES. RDKit's **canonical SMILES** always picks the same one, which makes
it usable for comparing molecules:

```python
for smiles in ["OCC", "CCO", "C(O)C", "[CH3][CH2][OH]"]:
    canonical = Chem.MolToSmiles(Chem.MolFromSmiles(smiles))
    print(f"{smiles:16} -> {canonical}")
```
```output
OCC              -> CCO
CCO              -> CCO
C(O)C            -> CCO
[CH3][CH2][OH]   -> CCO
```

Canonical means canonical *for one toolkit and version*: another program, or another RDKit
release, may choose a different canonical form. That is why a database needs an identity that does
not depend on the toolkit (section 5).

**Aromaticity** is a choice too. Benzene can be written with alternating double bonds (Kekulé) or
with aromatic lower-case atoms; RDKit perceives the aromatic form when it reads the molecule:

```python
benzene = Chem.MolFromSmiles("C1=CC=CC=C1")
print("as read:   ", Chem.MolToSmiles(benzene))
Chem.Kekulize(benzene, clearAromaticFlags=True)
print("kekulised: ", Chem.MolToSmiles(benzene))
```
```output
as read:    c1ccccc1
kekulised:  C1=CC=CC=C1
```

Different toolkits perceive aromaticity by different rules, so the same file can give different
aromatic forms in different programs: one more reason to standardise before storing (Module 6).

## 4. What a representation can lose: stereochemistry

Ibuprofen has one stereocentre. The two mirror images (enantiomers) are different molecules with
different biology, and isomeric SMILES keeps them apart with `@` and `@@`:

![The two enantiomers of ibuprofen, labelled R and S](figures/ibuprofen-enantiomers.svg)

```python
s_ibuprofen = Chem.MolFromSmiles("CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O")
r_ibuprofen = Chem.MolFromSmiles("CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O")
print("S:", Chem.FindMolChiralCenters(s_ibuprofen), Chem.MolToSmiles(s_ibuprofen))
print("R:", Chem.FindMolChiralCenters(r_ibuprofen), Chem.MolToSmiles(r_ibuprofen))
```
```output
S: [(10, 'S')] CC(C)Cc1ccc([C@H](C)C(=O)O)cc1
R: [(10, 'R')] CC(C)Cc1ccc([C@@H](C)C(=O)O)cc1
```

Ask for SMILES without stereochemistry, and the two collapse into one:

```python
def flat(mol):
    return Chem.MolToSmiles(mol, isomericSmiles=False)


print("isomeric SMILES equal:", Chem.MolToSmiles(s_ibuprofen) == Chem.MolToSmiles(r_ibuprofen))
print("flat SMILES equal:    ", flat(s_ibuprofen) == flat(r_ibuprofen))
print("flat:", flat(s_ibuprofen))
```
```output
isomeric SMILES equal: False
flat SMILES equal:     True
flat: CC(C)Cc1ccc(C(C)C(=O)O)cc1
```

Store the flat form and your database silently merges two different drugs. Sometimes that is what
you want (grouping a racemate with its enantiomers), but it must be a decision, never an accident.

## 5. InChI and InChIKey: an identity for every molecule

The **InChI** (IUPAC International Chemical Identifier) is a standard, open, layered description
of a molecule, produced the same way by every program that uses the official software. The
**InChIKey** is a fixed-length, 27-character hash of it: short enough to index, search and join on.

```python
print(Chem.MolToInchi(aspirin))
print(Chem.MolToInchiKey(aspirin))
```
```output
InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)
BSYNRYMUTXBXSQ-UHFFFAOYSA-N
```

The key has three blocks. The first 14 letters encode the connectivity (the skeleton). The next
block has 8 letters for stereochemistry and the other layers, then `S` (a standard InChI) and `A`
(version 1). The last letter records protonation (`N` for neutral). So the two ibuprofen
enantiomers share the first block and differ in the second:

```python
for name, mol in [("S", s_ibuprofen), ("R", r_ibuprofen)]:
    key = Chem.MolToInchiKey(mol)
    print(name, key, "  skeleton:", key[:14])
```
```output
S HEFNNWSXXWATRW-JTQLQIEISA-N   skeleton: HEFNNWSXXWATRW
R HEFNNWSXXWATRW-SNVBAGLBSA-N   skeleton: HEFNNWSXXWATRW
```

Grouping on the first 14 letters finds every stereoisomer of a structure; joining on the whole key
keeps them apart. Standard InChI also treats some mobile hydrogens as one, so certain tautomers
share a key, which is usually what a database wants:

```python
pyridone = Chem.MolFromSmiles("O=c1cccc[nH]1")
hydroxypyridine = Chem.MolFromSmiles("Oc1ccccn1")
print("SMILES equal:  ", Chem.MolToSmiles(pyridone) == Chem.MolToSmiles(hydroxypyridine))
print("InChIKey equal:", Chem.MolToInchiKey(pyridone) == Chem.MolToInchiKey(hydroxypyridine))
```
```output
SMILES equal:   False
InChIKey equal: True
```

InChIKeys are hashes, so two different molecules could in principle share one; in practice
collisions are extremely rare, but a careful pipeline keeps the full InChI or SMILES beside the key.

## 6. Molfiles and SDF: the connection table

Before SMILES there were **connection tables**: a list of atoms (with coordinates) and a list of
bonds between them. The MDL molfile is the classic format, and an SDF file is many molfiles one after
another, each with optional data fields. Most compound libraries and vendor catalogues arrive as SDF.

```python
ethanol = Chem.MolFromSmiles("CCO")
print(Chem.MolToMolBlock(ethanol))
```
```output

     RDKit          2D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2990    0.7500    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.5981   -0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  END

```

Read it as a table: the counts line (3 atoms, 2 bonds), three atom lines (x, y, z, element) and two
bond lines (atom, atom, bond order). Unlike SMILES, a molfile carries coordinates, which also means
it is much larger: Module 2 measures what each format costs.

## 7. Three dimensions: conformers

Real molecules are three-dimensional and flexible. RDKit can generate 3D shapes (conformers), but
one molecule has many, and which you get depends on the method and the random seed:

```python
from rdkit.Chem import AllChem

with_h = Chem.AddHs(aspirin)
ids = AllChem.EmbedMultipleConfs(with_h, numConfs=5, randomSeed=42)
print(len(ids), "conformers of", with_h.GetNumAtoms(), "atoms (hydrogens included)")
print(
    "same atoms, different coordinates:",
    with_h.GetConformer(0).GetAtomPosition(0).x != with_h.GetConformer(1).GetAtomPosition(0).x,
)
```
```output
5 conformers of 21 atoms (hydrogens included)
same atoms, different coordinates: True
```

So 3D coordinates are not an identity: store them, when a job needs them (docking, shape
searches), as data *about* a molecule, never as the molecule's key.

## 8. SMARTS: patterns, not molecules

**SMARTS** describes a pattern to search for, not a molecule. A common mistake is to search with a
molecule written as SMILES. `C(=O)O` read as a molecule matches any carbon double-bonded to one
oxygen and single-bonded to another: carboxylic acids, but also esters. The SMARTS
`[CX3](=O)[OX2H1]` asks for that oxygen to carry a hydrogen, so it finds acids only:

![Four molecules with the carboxylic acid group highlighted where the SMARTS pattern matches](figures/smarts-acid.svg)

```python
library = {
    "aspirin": aspirin,
    "salicylic acid": Chem.MolFromSmiles("O=C(O)c1ccccc1O"),
    "methyl salicylate": Chem.MolFromSmiles("COC(=O)c1ccccc1O"),
    "ibuprofen": s_ibuprofen,
}
as_molecule = Chem.MolFromSmiles("C(=O)O")
acid = Chem.MolFromSmarts("[CX3](=O)[OX2H1]")
for name, mol in library.items():
    print(
        f"{name:18} C(=O)O as a molecule: {mol.HasSubstructMatch(as_molecule)!s:5}  "
        f"acid SMARTS: {mol.HasSubstructMatch(acid)}"
    )
```
```output
aspirin            C(=O)O as a molecule: True   acid SMARTS: True
salicylic acid     C(=O)O as a molecule: True   acid SMARTS: True
methyl salicylate  C(=O)O as a molecule: True   acid SMARTS: False
ibuprofen          C(=O)O as a molecule: True   acid SMARTS: True
```

Methyl salicylate is an ester, not an acid: only the SMARTS gets it right. Module 3 runs the same
searches inside the database.

## 9. Fingerprints: molecules as bits

To compare thousands of molecules quickly, we turn each into a **fingerprint**, a fixed-length
string of bits. A Morgan (circular, ECFP-like) fingerprint looks at every atom's surroundings out to
a radius, and sets a bit for each environment it finds. Similar molecules share many bits:

![Morgan fingerprint bits of aspirin and salicylic acid, with the bits they share marked](figures/fingerprint-bits.svg)

```python
from rdkit import DataStructs
from rdkit.Chem import rdFingerprintGenerator

morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
fingerprints = {name: morgan.GetFingerprint(mol) for name, mol in library.items()}
print("bits set in aspirin:", fingerprints["aspirin"].GetNumOnBits(), "of 2048")
for name in ["salicylic acid", "methyl salicylate", "ibuprofen"]:
    similarity = DataStructs.TanimotoSimilarity(fingerprints["aspirin"], fingerprints[name])
    print(f"Tanimoto similarity, aspirin and {name}: {similarity:.2f}")
```
```output
bits set in aspirin: 24 of 2048
Tanimoto similarity, aspirin and salicylic acid: 0.45
Tanimoto similarity, aspirin and methyl salicylate: 0.35
Tanimoto similarity, aspirin and ibuprofen: 0.20
```

The **Tanimoto similarity** is the number of bits both have divided by the number either has. A
fingerprint cannot be turned back into a molecule, and two different molecules can share one: it is
for comparing and searching, not for identity.

## 10. Descriptors: molecules as numbers

**Descriptors** are numbers calculated from a molecule: molecular weight, logP (a predicted
partition coefficient), polar surface area, hydrogen-bond donors. They are what most machine-learning
models and most filters work with:

```python
from rdkit.Chem import Descriptors

print(f"{'molecule':18}{'MW':>8}{'logP':>7}{'TPSA':>7}{'HBD':>5}")
for name, mol in library.items():
    print(
        f"{name:18}{Descriptors.MolWt(mol):8.1f}{Descriptors.MolLogP(mol):7.2f}"
        f"{Descriptors.TPSA(mol):7.1f}{Descriptors.NumHDonors(mol):5d}"
    )
```
```output
molecule                MW   logP   TPSA  HBD
aspirin              180.2   1.31   63.6    1
salicylic acid       138.1   1.09   57.5    2
methyl salicylate    152.1   1.18   46.5    1
ibuprofen            206.3   3.07   37.3    1
```

Descriptors are calculated, so they depend on the toolkit and its version: store the version beside
them (Module 12 returns to this).

## 11. What to store, for which job

| Representation | Keeps | Loses | Use it for |
|---|---|---|---|
| Canonical isomeric SMILES | Connectivity, stereochemistry, charges | Coordinates; toolkit-specific | Readable storage, exchange, rebuilding the molecule |
| InChI / InChIKey | A standard identity, the same in every program | Readability (the key); some tautomer detail | Keys, joins, finding duplicates |
| Molfile / SDF | Coordinates, data fields | Compactness | Receiving and sending libraries; 3D work |
| Molecular graph | Atoms, bonds, structure | Nothing of the 2D structure; no coordinates | Graph algorithms, graph databases |
| Adjacency, distance and feature matrices | The graph and chosen atom properties, as numbers | Compactness (they grow with atoms squared) | Algorithms, graph neural networks; build them when needed |
| 3D conformers | Shape | Uniqueness | Docking, shape searches (as data, never as a key) |
| SMARTS | A pattern | It is not a molecule | Searching and filtering |
| Fingerprints | Local environments, as bits | Can't be reversed; not unique | Similarity search, clustering, machine learning |
| Descriptors | Chosen properties, as numbers | Structure | Filters, analysis, machine learning |

A sensible first table for a compound library, which the next modules build on:

```python
import pandas as pd

rows = []
for name, mol in library.items():
    rows.append(
        {
            "name": name,
            "inchikey": Chem.MolToInchiKey(mol),
            "smiles": Chem.MolToSmiles(mol),
            "mw": round(Descriptors.MolWt(mol), 2),
        }
    )
compounds = pd.DataFrame(rows)
print(compounds.to_string(index=False))
```
```output
             name                    inchikey                         smiles     mw
          aspirin BSYNRYMUTXBXSQ-UHFFFAOYSA-N          CC(=O)Oc1ccccc1C(=O)O 180.16
   salicylic acid YGSDEFSMJLZEOE-UHFFFAOYSA-N                O=C(O)c1ccccc1O 138.12
methyl salicylate OSWPMRLSEDHDFF-UHFFFAOYSA-N               COC(=O)c1ccccc1O 152.15
        ibuprofen HEFNNWSXXWATRW-JTQLQIEISA-N CC(C)Cc1ccc([C@H](C)C(=O)O)cc1 206.28
```

The InChIKey is the identity, the canonical isomeric SMILES rebuilds the molecule, and everything
else (fingerprints, descriptors, conformers) can be recalculated from it, as long as we record how.

## Try it yourself

The homework for this module is in `homework.md`: a few questions answered by running code like the
code above. Answers are published after the cohort's deadline.

## Further reading

- Weininger, D. (1988). SMILES, a chemical language and information system. 1. Introduction to
  methodology and encoding rules. *Journal of Chemical Information and Computer Sciences*, 28(1),
  31–36. <https://doi.org/10.1021/ci00057a005>
- Heller, S., McNaught, A., Pletnev, I., Stein, S. & Tchekhovskoi, D. (2015). InChI, the IUPAC
  International Chemical Identifier. *Journal of Cheminformatics*, 7, 23.
  <https://doi.org/10.1186/s13321-015-0068-4>
- Dalby, A. et al. (1992). Description of several chemical structure file formats used by computer
  programs developed at Molecular Design Limited. *Journal of Chemical Information and Computer
  Sciences*, 32(3), 244–255. <https://doi.org/10.1021/ci00007a012>
- Rogers, D. & Hahn, M. (2010). Extended-connectivity fingerprints. *Journal of Chemical
  Information and Modeling*, 50(5), 742–754. <https://doi.org/10.1021/ci100050t>
- Daylight Chemical Information Systems. *Daylight Theory Manual*, chapters on SMILES and SMARTS.
  <https://www.daylight.com/dayhtml/doc/theory/>
- The RDKit documentation. *Getting Started with the RDKit in Python*.
  <https://www.rdkit.org/docs/GettingStartedInPython.html>
