# Homework: Chemical files and identity

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. Make `chemlib.library(5_000, seed=11)` and write it as SDF, gzipped SDF, SMILES, CSV and
   Parquet, as in section 1. How many bytes per molecule does each take? Then write the Parquet
   file three more times, with `compression="snappy"`, `"gzip"` and `"none"`. Which is smallest,
   and how much does compression save over `"none"`?
2. Make a damaged delivery with `chemlib.add_defects(chemlib.library(3_000, seed=12), rate=0.08,
   seed=13)`, write it with `write_unchecked_sdf`, and cut the last 500 bytes off the file. Stream
   it with `records`. How many molecules are read, how many records fail, and for which reasons?
   Which kinds of defect are read without any error, and why is that not the same as their being
   correct?
3. A supplier's CSV has a column `salt_form` with the values `HCl`, `Na`, `NA`, `None` and `TFA`,
   and a column `lot` with the values `0012`, `1e3` and `0450`. Write it with the `csv` module and
   read it back with `pd.read_csv` and no options. Which values come back changed, and into what?
   Which options to `read_csv` keep every value exactly as written? Store the result as Parquet with
   a schema and show that it reads back unchanged.
4. Make `chemlib.library(30_000, seed=21)` and compute an InChIKey for every molecule. How many
   molecules appear more than once? Do canonical SMILES find exactly the same groups (compare the
   groups, not only their number)? Draw or print three of the pairs and explain, from the scaffold,
   why each pair is the same molecule.
5. Take 500 molecules of your choice from the library in question 4. For each, make a randomly
   ordered SMILES with `Chem.MolToSmiles(mol, canonical=False, doRandom=True)`, and canonicalise
   both the original and the random SMILES with RDKit and with Open Babel. Within each toolkit, do
   the two canonical forms always agree? If `"inchikey" in pybel.outformats` is true on your
   computer (it is in Google Colab), also compare Open Babel's own InChIKeys with RDKit's: how many
   agree?
6. **To think about.** A partner sends you a 2 GB gzipped SDF of their catalogue every week, with a
   SHA-256 checksum. Design the intake: in what order do you check the checksum, stream the
   records, record failures and convert the data fields; what do you store, in which format, and
   with which key; and how do you tell which molecules in this week's file are new, which have
   changed price, and which are no longer offered? What would go wrong if the key were RDKit's
   canonical SMILES, and your partner moved to a new version of their toolkit?
