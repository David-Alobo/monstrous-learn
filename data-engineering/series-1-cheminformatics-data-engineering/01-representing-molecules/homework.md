# Homework: Representing molecules

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. **Caffeine** is `CN1C=NC2=C1C(=O)N(C(=O)N2C)C`. How many heavy atoms, bonds and rings does it
   have? (Use the molecule, then the graph.)
2. Write three different SMILES for **paracetamol** (`CC(=O)Nc1ccc(O)cc1`) and show that RDKit gives
   the same canonical SMILES for all three. What is it?
3. What is paracetamol's **InChIKey**? Which block of the key would two stereoisomers of a molecule
   share?
4. Of the four molecules in section 7 (aspirin, salicylic acid, methyl salicylate, ibuprofen), how
   many contain a **phenol**? Write a SMARTS pattern for a hydroxyl group on an aromatic carbon and
   count the matches.
5. What is the **Tanimoto similarity** of paracetamol and aspirin, using Morgan fingerprints with
   radius 2 and 2048 bits, to two decimal places?
6. *To think about:* two suppliers send what they say is the same compound, one as an SDF file with
   3D coordinates and one as a SMILES string without stereochemistry. How would you decide whether
   they are the same, which representation would you compare, and what could go wrong?
