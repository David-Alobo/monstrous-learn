# Homework: Validating molecules

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. Run the lesson's `parse` function on these five records: `C1CC(C`, `c1ccncc1`, `N(C)(C)(C)C`,
   `c1ccnc1`, `CC(=O)O[Na]`. Which can be read, and for each that cannot, what reason code and
   message does it get? One of them is read without complaint although a chemist would object:
   which, and why does sanitisation accept it?
2. Make a new damaged library with `chemlib.library(5_000, seed=11)` and
   `chemlib.add_defects(..., rate=0.08, seed=12)`. Run the gate. How many records are accepted and
   how many quarantined, and how many quarantined records could Module 7 repair (all their issues
   are "fix")?
3. The selenium records in `add_defects` are written with `[Se]`, a bracket atom with no hydrogens.
   Write a `check_radicals` check (use `atom.GetNumRadicalElectrons()`) that returns an issue with
   the code `RADICAL`, add it to `CHECKS`, and run the gate on your library from question 2. Which
   kinds of fault does it fire on, and is it a second reason for records that were already
   quarantined, or does it catch anything new?
4. Change the stereochemistry policy from "warn" to "reject". How many records of your library
   from question 2 would now be quarantined? Find the two scaffolds of `chemlib.SCAFFOLDS` that
   contribute the most of them, and point to the atom that makes each one a stereocentre.
5. Build the confusion table for your library from question 2, with the duplicate check across
   records from section 5. Are there clean records flagged as duplicates? For one of them, show the
   two SMILES and explain why they are the same molecule.
6. **To think about.** A vendor sends you an update file every week, and your validator will
   change over the year (a new element allowed, a stricter size limit). Design what you store for
   each record so that, a year from now, you can say why any record was accepted or quarantined, and
   re-run only the records whose verdict a new version of the validator could change. Who in a team
   should own the allow-list and the salt and solvent lists, and how would a change to them be
   reviewed?
