# Homework: Standardisation as a tested transformation

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
functions (`standardise`, `config_hash`, `is_idempotent`, `is_invariant`, `inchikey`,
`duplicate_groups`) and its options (`DEFAULT`, `WITH_TAUTOMERS`) exist. If you are in a cohort,
you will be told where to send your answers; everyone can check theirs against the answers
published after the cohort's deadline.

1. *Builds on sections 2 and 3.* Run the lesson's `standardise` on these records: sodium salicylate
   `O=C([O-])c1ccccc1O.[Na+]`, metformin hydrochloride `CN(C)C(=N)NC(=N)N.Cl`, acetylcholine
   chloride `CC(=O)OCC[N+](C)(C)C.[Cl-]` and `CS(C)=O` (DMSO on its own). For example,
   `result = standardise("CS(C)=O")`, then `print(result.smiles, result.changed_by)`. For each,
   give the output SMILES and the steps that changed it. One output still carries a charge: why can
   the uncharger not remove it, and should the validation gate of Module 6 (its charge check, in
   section 3) accept that record?
2. *Builds on section 2, "Canonical tautomer".* Acetylacetone can be written as its keto form
   `CC(=O)CC(C)=O` or its enol form `CC(O)=CC(C)=O`; these are two tautomers, forms that differ only
   by where a hydrogen sits. Do the two give the same output with the default options
   (`standardise(smiles)`)? With `WITH_TAUTOMERS` (`standardise(smiles, WITH_TAUTOMERS)`)? Do they
   have the same InChIKey (use the lesson's `inchikey` function)? Use your answers to explain which
   tautomers the standard InChI already treats as one, and which it does not.
3. *Builds on section 4.* Test idempotency (standardising the output again changes nothing) and
   invariance (different SMILES of one molecule give one output) with `WITH_TAUTOMERS` on the
   SMILES of `chemlib.library(300, seed=41)`: call `is_idempotent(s, WITH_TAUTOMERS)` and
   `is_invariant(s, WITH_TAUTOMERS)` for each SMILES `s` in its `"smiles"` column. Do all 300
   molecules pass both tests? If any fail, show one and explain what you see.
4. *Builds on sections 3 and 5.* Make a new options set with the neutralisation step switched off,
   `Options(uncharge=False)`. What is its configuration hash (`config_hash`)? Standardise the
   lesson's merged table of vendor A and vendor B (`merged`, from section 5) with it: how many
   outputs differ from the default, and how many duplicate groups (InChIKeys of the output held by
   more than one record) do you find now? Explain the difference.
5. *Builds on section 5.* Repeat section 5 with a different library: `chemlib.library(3_000,
   seed=51)`, `add_defects(..., rate=0.06, seed=52)`, and a vendor B of 150 salts
   (`basic.sample(150, random_state=8)`). How many duplicate groups are there before and after
   standardisation, and how many groups join records whose InChIKeys differed before?
6. **To think about.** *Builds on sections 3 and 5.* Your team wants to change the standardiser (a
   new RDKit release, or switching the tautomer step on), and the database already holds two
   million standardised records. Using the provenance columns of this module (`input_smiles`,
   `changed_by`, `rules_version`, `config_hash`), describe how you would find out which records the
   change affects before you make it, how you would store records made under the old and new rules
   while the change rolls out, and what a reviewer should see before approving it.
