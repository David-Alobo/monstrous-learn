# Homework: Validating molecules

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
functions (`parse`, `validate`, `verdict` and the checks) and its settings exist. If you are in a
cohort, you will be told where to send your answers; everyone can check theirs against the answers
published after the cohort's deadline.

1. *Builds on section 2, "Capturing RDKit's messages".* Run the lesson's `parse` function on these
   five records: `C1CC(C`, `c1ccncc1`, `N(C)(C)(C)C`, `c1ccnc1`, `CC(=O)O[Na]`. For example,
   `mol, issues = parse("C1CC(C")` and then `print(issues)`. Which can be read, and for each that
   cannot, what reason code and message does it get? One of them is read without complaint
   although a chemist would object: which, and why does sanitisation (RDKit's check of valences
   and aromaticity) accept it?
2. *Builds on sections 1 and 4.* Make a new damaged library with
   `chemlib.add_defects(chemlib.library(5_000, seed=11), rate=0.08, seed=12)`. Run the gate on it:
   for each SMILES, `validate` gives its issues and `verdict` turns them into "accept" or
   "quarantine", as in section 4. How many records are accepted and how many quarantined? How many
   quarantined records could Module 7 repair, because every one of their issues has the action
   "fix"?
3. *Builds on section 3.* The selenium records made by `add_defects` are written with `[Se]`, an
   atom in square brackets. In SMILES, an atom in brackets gets exactly the hydrogens written
   inside the brackets, here none, so the selenium is left with an unpaired electron: a
   **radical**. Write a `check_radicals` check in the style of section 3: it takes a molecule and
   returns a list of issues, here one with the code `RADICAL` when any atom has
   `atom.GetNumRadicalElectrons()` above zero. Add it to `CHECKS` (`CHECKS.append(check_radicals)`)
   and run the gate on your library from question 2. Which kinds of fault does it fire on? Is it a
   second reason for records that were already quarantined, or does it catch anything new?
4. *Builds on section 3, "Stereochemistry".* The lesson's stereochemistry check returns its issue
   with the action "warn", so those records are accepted. Change that action to "reject" and run
   the gate again. How many records of your library from question 2 would now be quarantined? The
   molecules of `chemlib` are built on a few core structures, listed as SMILES in
   `chemlib.SCAFFOLDS`. Find the two scaffolds that contribute the most of the new quarantines, and
   point to the atom that makes each one a stereocentre.
5. *Builds on sections 5 and 6.* Build the confusion table (true fault in the rows, the gate's
   outcome in the columns) for your library from question 2, including the duplicate check across
   records from section 5. Are there clean records flagged as duplicates? For one of them, show the
   two SMILES and explain why they are the same molecule.
6. **To think about.** *Builds on the whole lesson, especially section 7.* A vendor sends you an
   update file every week, and your validator will change over the year (a new element allowed, a
   stricter size limit). Design what you store for each record so that, a year from now, you can
   say why any record was accepted or quarantined, and re-run only the records whose verdict a new
   version of the validator could change. Who in a team should own the allow-list of elements and
   the salt and solvent lists, and how would a change to them be reviewed?
