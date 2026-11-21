# Homework: Standardisation as a tested transformation

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. Run the lesson's `standardise` on these records: sodium salicylate `O=C([O-])c1ccccc1O.[Na+]`,
   metformin hydrochloride `CN(C)C(=N)NC(=N)N.Cl`, acetylcholine chloride
   `CC(=O)OCC[N+](C)(C)C.[Cl-]` and `CS(C)=O` (DMSO on its own). For each, give the output SMILES
   and the steps that changed it. One output still carries a charge: why can the uncharger not
   remove it, and should the validation gate (Module 6) accept that record?
2. Acetylacetone can be written as its keto form `CC(=O)CC(C)=O` or its enol form
   `CC(O)=CC(C)=O`. Do the two give the same output with the default options? With
   `WITH_TAUTOMERS`? Do they have the same InChIKey? Use your answers to explain which tautomers the
   standard InChI already treats as one, and which it does not.
3. Test idempotency and invariance with `WITH_TAUTOMERS` on `chemlib.library(300, seed=41)`. Do all
   300 molecules pass both tests? If any fail, show one and explain what you see.
4. Make a new options set with `uncharge=False`. What is its configuration hash? Standardise the
   lesson's merged table (vendor A and vendor B) with it: how many outputs differ from the default,
   and how many duplicate groups (by InChIKey of the output) do you find now? Explain the
   difference.
5. Repeat section 5 with `chemlib.library(3_000, seed=51)`, `add_defects(..., rate=0.06, seed=52)`
   and a vendor B of 150 salts (`random_state=8`). How many duplicate groups are there before and
   after standardisation, and how many groups join records whose InChIKeys differed before?
6. **To think about.** Your team wants to change the standardiser (a new RDKit release, or switching
   the tautomer step on), and the database already holds two million standardised records. Using
   the provenance columns of this module, describe how you would find out which records the change
   affects before you make it, how you would store records made under the old and new rules while
   the change rolls out, and what a reviewer should see before approving it.
