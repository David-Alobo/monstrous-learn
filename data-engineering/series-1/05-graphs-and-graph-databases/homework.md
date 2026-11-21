# Homework: Molecules as graphs, and graph databases

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first. Questions 3 to
6 need Neo4j running (see the database guide); the lesson closes its connection at the end, so open
a new one with `driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))`. If
you are in a cohort, you will be told where to send your answers; everyone can check theirs against
the answers published after the cohort's deadline.

1. **Rings and paths** (section 1). For naphthalene (`c1ccc2ccccc2c1`) and for caffeine
   (`Cn1cnc2c1c(=O)n(C)c(=O)n2C`), list the rings NetworkX and RDKit find. Which two atoms of
   caffeine are furthest apart, and how many bonds separate them? (Hint: `nx.diameter` gives the
   longest of all shortest paths; `Chem.GetDistanceMatrix` gives every distance.)
2. **Graph matching** (section 2). Write `amide_pattern(require_hydrogen)` for a primary amide,
   C(=O)N with the nitrogen carrying two hydrogens, by analogy with `acid_pattern`. Test it on
   paracetamol (`CC(=O)Nc1ccc(O)cc1`, a secondary amide) and on benzamide (`NC(=O)c1ccccc1`, a
   primary one), with and without the hydrogen condition. Check each answer against RDKit with the
   SMARTS `[NX3H2][CX3]=O`.
3. **Add to the network** (section 3). Add the reaction "hydrolysis of aspirin", in which aspirin
   and water (`O`) give salicylic acid and acetic acid (`CC(=O)O`), with `MERGE` so that running it
   twice changes nothing. How many reactions now use salicylic acid or make it? Show that running
   your load a second time leaves the counts of section 3 unchanged apart from your additions.
4. **Follow the links** (section 4). Starting from acetic anhydride instead of phenol, which
   compounds can be made, and in how many steps? Which of them inhibit a cyclooxygenase?
5. **Count the routes** (section 4). Write a Cypher query that returns, for each compound that is
   made by at least one reaction, how many different starting materials (compounds that no reaction
   makes) lead to it. Which compound has the most?
6. **Graph or table?** (section 6). Write the question of homework 4 as a recursive SQL query in
   DuckDB, and compare its length and readability with your Cypher. Then name one question about
   this data that is easier in SQL than in Cypher, and explain why.
