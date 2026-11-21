"""Molecules as graphs, and graph databases: the code of the lesson, in order.

Work with molecules as graphs (rings, paths, substructure as graph matching, the largest shared substructure), then store chemistry that is all about links, synthesis routes and drug targets, in a Neo4j graph database and query it with Cypher.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/05-graphs-and-graph-databases/
Run it from anywhere, e.g. from the series folder: uv run python 05-graphs-and-graph-databases/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- Setup ----
import logging
import os
from pathlib import Path

import duckdb
import networkx as nx
import pandas as pd
from dotenv import find_dotenv, load_dotenv
from networkx.algorithms import isomorphism
from neo4j import GraphDatabase
from neo4j.exceptions import ConstraintError
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFMCS

from drawing import grid_svg, scheme_svg

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)
logging.getLogger("neo4j").setLevel(logging.WARNING)  # the driver's own notes on each query: hidden

# molecules of sections 1 and 2
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
METHYL_SALICYLATE = "COC(=O)c1ccccc1O"
SALICYLIC_ACID = "OC(=O)c1ccccc1O"
MCS_TIMEOUT_S = 10  # give up the common-substructure search after this many seconds

# Neo4j (sections 3 to 6): where it is and how to log in
# passwords and addresses: from the environment, or from the course's .env file (copied from
# .env.example at the repository's root); find_dotenv looks for it in this folder and the ones
# above, and settings already in the environment are kept
load_dotenv(find_dotenv(usecwd=True))
NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
LESSON_LABEL = "Module5"  # every node the lesson makes carries it, so the lesson can remove its own

# the lesson's chemistry network: textbook syntheses and well-established drug targets
# (compound name: SMILES)
COMPOUNDS = {
    "phenol": "Oc1ccccc1",
    "nitric acid": "O=[N+]([O-])O",
    "4-nitrophenol": "O=[N+]([O-])c1ccc(O)cc1",
    "hydrogen": "[HH]",
    "4-aminophenol": "Nc1ccc(O)cc1",
    "acetic anhydride": "CC(=O)OC(C)=O",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "carbon dioxide": "O=C=O",
    "salicylic acid": SALICYLIC_ACID,
    "aspirin": ASPIRIN,
    "methanol": "CO",
    "methyl salicylate": METHYL_SALICYLATE,
    "isobutylbenzene": "CC(C)Cc1ccccc1",
    "4-isobutylacetophenone": "CC(=O)c1ccc(CC(C)C)cc1",
    "1-(4-isobutylphenyl)ethanol": "CC(O)c1ccc(CC(C)C)cc1",
    "carbon monoxide": "[C-]#[O+]",
    "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "celecoxib": "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1",
}
# (reaction name, reactants, products)
REACTIONS = [
    ("nitration of phenol", ["phenol", "nitric acid"], ["4-nitrophenol"]),
    ("reduction of 4-nitrophenol", ["4-nitrophenol", "hydrogen"], ["4-aminophenol"]),
    ("acetylation of 4-aminophenol", ["4-aminophenol", "acetic anhydride"], ["paracetamol"]),
    ("Kolbe-Schmitt carboxylation", ["phenol", "carbon dioxide"], ["salicylic acid"]),
    ("acetylation of salicylic acid", ["salicylic acid", "acetic anhydride"], ["aspirin"]),
    ("esterification of salicylic acid", ["salicylic acid", "methanol"], ["methyl salicylate"]),
    ("Friedel-Crafts acylation", ["isobutylbenzene", "acetic anhydride"], ["4-isobutylacetophenone"]),
    ("hydrogenation of the ketone", ["4-isobutylacetophenone", "hydrogen"], ["1-(4-isobutylphenyl)ethanol"]),
    ("carbonylation", ["1-(4-isobutylphenyl)ethanol", "carbon monoxide"], ["ibuprofen"]),
]  # fmt: skip
# (target ChEMBL id, name, gene) and which compounds inhibit it (well established)
TARGETS = [("CHEMBL221", "Cyclooxygenase-1", "PTGS1"), ("CHEMBL230", "Cyclooxygenase-2", "PTGS2")]
INHIBITS = [("aspirin", "CHEMBL221"), ("aspirin", "CHEMBL230"), ("ibuprofen", "CHEMBL221"),
            ("ibuprofen", "CHEMBL230"), ("celecoxib", "CHEMBL230")]  # fmt: skip
START = "phenol"  # the starting material of section 4's questions
DRUG = "aspirin"  # the route drawn at the end of section 4
WORK = Path("work")  # where the lesson saves its drawings (git-ignored)

RDLogger.DisableLog("rdApp.*")  # RDKit warns about hydrogen gas ([HH]), which has no heavy atom
WORK.mkdir(exist_ok=True)

# ---- 1. Graph questions about one molecule ----
def to_graph(mol: Chem.Mol) -> nx.Graph:
    """A molecule as a NetworkX graph: atoms (element, hydrogens) as nodes, bonds (order) as edges."""
    g = nx.Graph()
    for atom in mol.GetAtoms():
        g.add_node(atom.GetIdx(), element=atom.GetSymbol(), hydrogens=atom.GetTotalNumHs())
    for bond in mol.GetBonds():
        g.add_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), order=bond.GetBondTypeAsDouble())
    return g


aspirin = Chem.MolFromSmiles(ASPIRIN)
aspirin_graph = to_graph(aspirin)
print(aspirin_graph.number_of_nodes(), "atoms,", aspirin_graph.number_of_edges(), "bonds")
print("NetworkX:", [sorted(ring) for ring in nx.cycle_basis(aspirin_graph)])
print("RDKit:   ", [sorted(ring) for ring in aspirin.GetRingInfo().AtomRings()])
path = nx.shortest_path(aspirin_graph, 0, 12)
print("atoms on the way:", path)
print("bonds apart:", len(path) - 1, "  RDKit agrees:", int(Chem.GetDistanceMatrix(aspirin)[0, 12]))

# ---- 2. Substructure search is graph matching ----
def acid_pattern(require_hydrogen: bool) -> nx.Graph:
    """The carboxyl group C(=O)O as a small graph; optionally the OH oxygen must carry one H."""
    pattern = nx.Graph()
    pattern.add_node("C", element="C")
    pattern.add_node("O=", element="O")
    pattern.add_node("OH", element="O", **({"hydrogens": 1} if require_hydrogen else {}))
    pattern.add_edge("C", "O=", order=2.0)
    pattern.add_edge("C", "OH", order=1.0)
    return pattern


def atoms_match(atom: dict, wanted: dict) -> bool:
    """A molecule's atom matches a pattern atom: same element, and same hydrogens if given."""
    return atom["element"] == wanted["element"] and atom["hydrogens"] == wanted.get("hydrogens", atom["hydrogens"])


def contains(mol: Chem.Mol, pattern: nx.Graph) -> bool:
    """Whether the molecule's graph contains the pattern's graph (atoms and bond orders matching)."""
    matcher = isomorphism.GraphMatcher(
        to_graph(mol), pattern, node_match=atoms_match,
        edge_match=lambda bond, wanted: bond["order"] == wanted["order"],
    )  # fmt: skip
    return matcher.subgraph_is_monomorphic()


for name, smiles in [("aspirin", ASPIRIN), ("methyl salicylate", METHYL_SALICYLATE)]:
    mol = Chem.MolFromSmiles(smiles)
    print(f"{name:18} C(=O)O: {contains(mol, acid_pattern(False))!s:5}  "
          f"C(=O)O-H: {contains(mol, acid_pattern(True))!s:5}  "
          f"RDKit SMARTS: {mol.HasSubstructMatch(Chem.MolFromSmarts('[CX3](=O)[OX2H1]'))}")

# ---- What several molecules share: the maximum common substructure ----
salicylates = [Chem.MolFromSmiles(s) for s in (ASPIRIN, METHYL_SALICYLATE, SALICYLIC_ACID)]
mcs = rdFMCS.FindMCS(salicylates, timeout=MCS_TIMEOUT_S)
print("shared core:", mcs.smartsString)
print(mcs.numAtoms, "atoms,", mcs.numBonds, "bonds; search finished in time:", not mcs.canceled)

# ---- 3. A graph database: Neo4j ----
# needs: neo4j
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()
driver.execute_query(f"MATCH (n:{LESSON_LABEL}) DETACH DELETE n")  # remove the last run's nodes
driver.execute_query("CREATE CONSTRAINT compound_key IF NOT EXISTS "
                     "FOR (c:Compound) REQUIRE c.inchikey IS UNIQUE")  # fmt: skip
driver.execute_query("CREATE CONSTRAINT reaction_name IF NOT EXISTS "
                     "FOR (r:Reaction) REQUIRE r.name IS UNIQUE")  # fmt: skip
log.info("connected to Neo4j; constraints in place")
# needs: neo4j
compound_rows = [
    {"name": name, "smiles": Chem.MolToSmiles(Chem.MolFromSmiles(smiles)),
     "inchikey": Chem.MolToInchiKey(Chem.MolFromSmiles(smiles))}
    for name, smiles in COMPOUNDS.items()
]  # fmt: skip
driver.execute_query(f"""
    UNWIND $rows AS row
    MERGE (c:Compound {{inchikey: row.inchikey}})
    SET c:{LESSON_LABEL}, c.name = row.name, c.smiles = row.smiles""", rows=compound_rows)
reaction_rows = [{"name": n, "reactants": r, "products": p} for n, r, p in REACTIONS]
driver.execute_query(f"""
    UNWIND $rows AS row
    MERGE (r:Reaction {{name: row.name}}) SET r:{LESSON_LABEL}
    WITH r, row
    UNWIND row.reactants AS reactant
    MATCH (c:Compound {{name: reactant}})
    MERGE (c)-[:REACTANT_OF]->(r)""", rows=reaction_rows)
driver.execute_query("""
    UNWIND $rows AS row
    MATCH (r:Reaction {name: row.name})
    UNWIND row.products AS product
    MATCH (c:Compound {name: product})
    MERGE (r)-[:PRODUCES]->(c)""", rows=reaction_rows)
driver.execute_query(f"""
    UNWIND $targets AS t
    MERGE (target:Target {{chembl_id: t[0]}}) SET target:{LESSON_LABEL}, target.name = t[1], target.gene = t[2]
    WITH count(*) AS made
    UNWIND $links AS link
    MATCH (c:Compound {{name: link[0]}}), (target:Target {{chembl_id: link[1]}})
    MERGE (c)-[:INHIBITS]->(target)""", targets=TARGETS, links=INHIBITS)
records, _, _ = driver.execute_query(f"""
    MATCH (n:{LESSON_LABEL}) WITH labels(n) AS kinds
    RETURN [k IN kinds WHERE k <> '{LESSON_LABEL}'][0] AS kind, count(*) AS nodes ORDER BY kind""")
for record in records:
    print(f"{record['kind']:9} {record['nodes']} nodes")
records, _, _ = driver.execute_query(f"""
    MATCH (:{LESSON_LABEL})-[rel]->(:{LESSON_LABEL})
    RETURN type(rel) AS kind, count(*) AS links ORDER BY kind""")
for record in records:
    print(f"{record['kind']:12} {record['links']} relationships")
# needs: neo4j
try:
    driver.execute_query("CREATE (:Compound {inchikey: $key, name: 'aspirin, typed again'})",
                         key=Chem.MolToInchiKey(aspirin))  # fmt: skip
except ConstraintError as error:
    print("refused:", error.code)

# ---- 4. Following links: Cypher questions ----
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH (c:Compound)-[:INHIBITS]->(t:Target)
    RETURN t.name AS target, collect(c.name) AS inhibitors ORDER BY target""")
for record in records:
    print(f"{record['target']:17} {sorted(record['inhibitors'])}")
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH path = (start:Compound {name: $start})-[:REACTANT_OF|PRODUCES*]->(product:Compound)
    RETURN product.name AS product, min(length(path)) / 2 AS steps
    ORDER BY steps, product""", start=START)
for record in records:
    print(f"{record['steps']} step(s): {record['product']}")
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH route = (start:Compound {name: $start})-[:REACTANT_OF|PRODUCES*]->(drug:Compound)
                  -[:INHIBITS]->(target:Target)
    RETURN drug.name AS drug, target.name AS target,
           [n IN nodes(route) WHERE n:Reaction | n.name] AS reactions
    ORDER BY drug, target""", start=START)
for record in records:
    print(f"{record['drug']} inhibits {record['target']}, via: {', '.join(record['reactions'])}")
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH (c:Compound)-[:REACTANT_OF]->(r:Reaction)
    WITH c, count(r) AS uses WHERE uses > 1
    RETURN c.name AS compound, uses ORDER BY uses DESC, compound""")
for record in records:
    print(f"{record['compound']:17} used in {record['uses']} reactions")

# ---- Seeing the molecules ----
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH path = (start:Compound {name: $start})-[:REACTANT_OF|PRODUCES*]->(product:Compound)
    RETURN product.name AS name, product.smiles AS smiles, min(length(path)) / 2 AS steps
    ORDER BY steps, name""", start=START)
grid = grid_svg([(r["smiles"], f"{r['name']} ({r['steps']} step{'s' if r['steps'] > 1 else ''})")
                 for r in records])  # fmt: skip
(WORK / "from-phenol.svg").write_text(grid, encoding="utf-8")
print(f"drew {len(records)} molecules in work/from-phenol.svg")
grid  # in a notebook, the last line of a cell is shown: here, the picture
# needs: neo4j
records, _, _ = driver.execute_query("""
    MATCH route = (start:Compound {name: $start})-[:REACTANT_OF|PRODUCES*]->(drug:Compound {name: $drug})
    RETURN [n IN nodes(route) | CASE WHEN n:Reaction
        THEN {reaction: n.name, reactants: [(c:Compound)-[:REACTANT_OF]->(n) | c.name]}
        ELSE {compound: n.name, smiles: n.smiles} END] AS steps
    ORDER BY length(route) LIMIT 1""", start=START, drug=DRUG)
steps = records[0]["steps"]
for k, step in enumerate(steps):
    if "reaction" in step:  # the other reactants: all of them except the compound we arrive with
        step["with"] = sorted(set(step["reactants"]) - {steps[k - 1]["compound"]})
        print(f"  --[{step['reaction']}, with {', '.join(step['with'])}]-->")
    else:
        print(step["compound"])
scheme = scheme_svg(steps)
(WORK / f"route-{DRUG}.svg").write_text(scheme, encoding="utf-8")
scheme

# ---- 5. A molecule inside a graph database ----
# needs: neo4j
atoms = [{"i": a.GetIdx(), "element": a.GetSymbol()} for a in aspirin.GetAtoms()]
bonds = [{"a": b.GetBeginAtomIdx(), "b": b.GetEndAtomIdx(), "order": b.GetBondTypeAsDouble()}
         for b in aspirin.GetBonds()]  # fmt: skip
driver.execute_query(f"""
    UNWIND $atoms AS atom CREATE (:Atom:{LESSON_LABEL} {{molecule: 'aspirin', i: atom.i, element: atom.element}})
    WITH count(*) AS made
    UNWIND $bonds AS bond
    MATCH (a:Atom {{molecule: 'aspirin', i: bond.a}}), (b:Atom {{molecule: 'aspirin', i: bond.b}})
    CREATE (a)-[:BOND {{order: bond.order}}]->(b)""", atoms=atoms, bonds=bonds)
records, _, _ = driver.execute_query("""
    MATCH (a:Atom {molecule: 'aspirin', i: 0}), (b:Atom {molecule: 'aspirin', i: 12}),
          path = shortestPath((a)-[:BOND*..30]-(b))
    RETURN length(path) AS bonds_apart, [n IN nodes(path) | n.element] AS elements""")
print("atom 0 to atom 12:", records[0]["bonds_apart"], "bonds, through", "".join(records[0]["elements"]))

# ---- 6. The same question in SQL, and where each wins ----
db = duckdb.connect()  # a database in memory: nothing is written to disk
db.execute("CREATE TABLE reactant (reaction VARCHAR, compound VARCHAR)")
db.execute("CREATE TABLE product (reaction VARCHAR, compound VARCHAR)")
db.executemany("INSERT INTO reactant VALUES (?, ?)", [(n, c) for n, rs, _ in REACTIONS for c in rs])
db.executemany("INSERT INTO product VALUES (?, ?)", [(n, c) for n, _, ps in REACTIONS for c in ps])
print(db.sql("""
    WITH RECURSIVE reachable (compound, steps) AS (
        SELECT ?::VARCHAR, 0
        UNION
        SELECT p.compound, r.steps + 1
        FROM reachable r
        JOIN reactant a ON a.compound = r.compound
        JOIN product p ON p.reaction = a.reaction
        WHERE r.steps < 10
    )
    SELECT compound AS product, min(steps) AS steps FROM reachable
    WHERE steps > 0 GROUP BY compound ORDER BY steps, product""", params=[START]).df().to_string(index=False))
db.close()
# needs: neo4j
driver.close()
