# Homework: Molecules as text, patterns and numbers

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. Write three different SMILES for **paracetamol** (`CC(=O)Nc1ccc(O)cc1`) and show that RDKit gives
   the same canonical SMILES for all three. What is it?
2. What is paracetamol's **InChIKey**? Which block of the key would two stereoisomers of a molecule
   share?
3. Of the four molecules in section 6 (aspirin, salicylic acid, methyl salicylate, ibuprofen), how
   many contain a **phenol**? Write a SMARTS pattern for a hydroxyl group on an aromatic carbon and
   count the matches.
4. What is the **Tanimoto similarity** of paracetamol and aspirin, using Morgan fingerprints with
   radius 2 and 2048 bits, to two decimal places?
5. *To think about:* two suppliers send what they say is the same compound, one as an SDF file with
   3D coordinates and one as a SMILES string without stereochemistry. How would you decide whether
   they are the same, which representation would you compare, and what could go wrong?
