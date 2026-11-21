# Homework: Parallel and distributed processing

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so `workers`,
`chunked` and the other names it made exist. If you are in a cohort, you will be told where to send
your answers; everyone can check theirs against the answers published after the cohort's deadline.

1. *(Sections 1 and 2.)* Make `chemlib.library(8_000, seed=31)` and run `workers.describe` over its
   SMILES serially (one call on the whole list) and with joblib (`n_jobs=2`, chunks of 1,000 made
   with the lesson's `chunked`). Are the results identical? What is the mean molecular weight (the
   `mw` of each row), to two decimal places?
2. *(Sections 1 and 2.)* Add a function to `workers.py` that also returns each molecule's
   InChIKey, and run it with joblib on the same 8,000 molecules. An InChIKey is a fixed-length code
   made from a molecule's structure (Module 3), so two records of the same molecule get the same
   key; RDKit makes it with `Chem.MolToInchiKey(mol)`. How many different InChIKeys are there? (The
   teaching library has a few molecules that are the same by symmetry.) In Colab, open `workers.py`
   from the Files panel on the left, edit and save it, then restart the session (**Runtime →
   Restart session**) and run the cells again, so Python loads your new version.
3. *(Sections 2 and 5.)* Time your function from question 2 with `n_jobs` of 1, 2 and 4 (if your
   computer has 4 cores; Colab's free computers usually have 2, so use 1 and 2 there). Amdahl's law
   in section 5 gives the speed-up from the parallel fraction `p`; turned round, it gives `p` from a
   measured speed-up `s` with `n` workers: `p = (1 - 1/s) / (1 - 1/n)`. Estimate `p` from your
   largest `n`. What speed-up would that `p` predict for 16 workers?
4. *(Section 3.)* Pickle chunks of 1,000 molecules three ways with `pickle.dumps`: as SMILES, as
   RDKit molecules, and as the molecules' binary form (`mol.ToBinary()`, RDKit's own compact way of
   writing a molecule as bytes). How many bytes does each take per molecule?
5. *(Section 6.)* With Dask, write `chemlib.stream(16_000, batch=2_000, start=600_000)` as a
   folder of Parquet files (one file per batch, as in the lesson, but in a new folder such as
   `work/homework`), run `workers.describe_frame` over it with `map_partitions`, and find the vendor
   with the highest mean polar surface area (`tpsa`). How many partitions did Dask use?
6. *To think about:* your group wants fingerprints for 50 million molecules every night, on a
   shared server with 32 cores and 64 GB of memory, where other people also run jobs. How would
   you choose the number of workers and the chunk size, what would each worker read and write, and
   how would you check that the parallel run gives the same answer as the serial one? There is no
   single right answer: a few paragraphs, using the ideas of this lesson and Module 8.
