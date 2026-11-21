# Homework: Chemical files and identity

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. *(Section 1.)* Make `chemlib.library(5_000, seed=11)` and write it as SDF, gzipped SDF, SMILES,
   CSV and Parquet, as in section 1, with the functions defined there. How many bytes per molecule
   does each take? Then write the Parquet file three more times, with `compression="snappy"`,
   `"gzip"` and `"none"` in `pq.write_table`. (These are different ways of compressing the file;
   `"none"` means not compressed.) Which is smallest, and how much does compression save over
   `"none"`?
2. *(Section 3.)* Make a damaged delivery with `chemlib.add_defects(chemlib.library(3_000,
   seed=12), rate=0.08, seed=13)`, write it with `write_unchecked_sdf`, and cut the last 500 bytes
   off the file, as section 3 does with 300. Read it with the generator `records`. How many
   molecules are read, how many records fail, and for which reasons? The `defect` column says how
   each row was damaged: which kinds of defect are read without any error, and why is that not the
   same as their being correct?
3. *(Section 4.)* A supplier's CSV has a column `salt_form` with the values `HCl`, `Na`, `NA`,
   `None` and `TFA`, and a column `lot` (the batch number) with the values `0012`, `1e3` and `0450`.
   Write it with the `csv` module and read it back with `pd.read_csv` and no options. Which values
   come back changed, and into what? (pandas shows a missing value as `NaN`, "not a number".) Which
   options to `read_csv` keep every value exactly as written? Store the result as Parquet with a
   schema and show that it reads back unchanged.
4. *(Section 5.)* Make `chemlib.library(30_000, seed=21)` and compute an InChIKey for every
   molecule. How many molecules appear more than once? Do canonical SMILES find exactly the same
   groups (compare the groups, that is which IDs are together, not only how many groups there are)?
   Draw or print three of the pairs and explain, from the scaffold (the core structure the building
   blocks are joined to), why each pair is the same molecule.
5. *(Section 6.)* Take 500 molecules of your choice from the library in question 4. For each, make a
   randomly ordered SMILES with `Chem.MolToSmiles(mol, canonical=False, doRandom=True)`, and
   canonicalise both the original and the random SMILES (turn them into canonical SMILES) with RDKit
   and with Open Babel, using `rdkit_canonical` and `openbabel_canonical`. Within each toolkit, do
   the two canonical forms always agree? If `"inchikey" in pybel.outformats` is true on your
   computer (it is in Google Colab), also compare Open Babel's own InChIKeys with RDKit's: how many
   agree?
6. **To think about (sections 3, 5 and 7).** A partner sends you a 2 GB gzipped SDF of their
   catalogue every week, with a SHA-256 checksum. Design the intake, the steps that take the file in:
   in what order do you check the checksum, stream the records (read them one at a time), record
   failures and convert the data fields; what do you store, in which format, and with which key (the
   column that identifies each molecule); and how do you tell which molecules in this week's file
   are new, which have changed price, and which are no longer offered? What would go wrong if the
   key were RDKit's canonical SMILES, and your partner moved to a new version of their toolkit?
