# Homework: Molecules as graphs and matrices

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. **Caffeine** is `CN1C=NC2=C1C(=O)N(C(=O)N2C)C`. How many heavy atoms, bonds and rings does it
   have? Use RDKit for the first two and the NetworkX graph for the rings.
2. Build caffeine's **adjacency matrix** with NetworkX. What do its rows add up to in total, and
   why is that twice the number of bonds?
3. Which two heavy atoms in caffeine are **furthest apart**, and by how many bonds? (Use the
   distance matrix.)
4. Build caffeine's **atom feature matrix** with the `atom_features` function from the lesson.
   How many nitrogen atoms carry no hydrogen?
5. Compute one step of **message passing**, `A @ X`, for caffeine. Which atom receives the most
   oxygens from its neighbours?
6. Trimethylamine hydrochloride can be written `CN(C)C.Cl`. How many **pieces** does the graph
   Laplacian find, and what would you want a pipeline to do with such a record?
