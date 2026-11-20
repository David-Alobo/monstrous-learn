# Homework: Parallel and distributed processing

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. Make `chemlib.library(8_000, seed=31)` and run `workers.describe` over it serially and with
   joblib (`n_jobs=2`, chunks of 1,000). Are the results identical? What is the mean molecular
   weight, to two decimal places?
2. Add a function to `workers.py` that also returns each molecule's InChIKey, and run it with
   joblib on the same 8,000 molecules. How many different InChIKeys are there? (The teaching
   library has a few molecules that are the same by symmetry.)
3. Time your function from question 2 with `n_jobs` of 1, 2 and 4 (if your computer has 4 cores).
   Use the formula from section 5 to estimate the parallel fraction `p` from your 4-worker
   speed-up. What speed-up would that `p` predict for 16 workers?
4. Pickle chunks of 1,000 molecules three ways: as SMILES, as RDKit molecules, and as the
   molecules' binary form (`mol.ToBinary()`). How many bytes does each take per molecule?
5. With Dask, write `chemlib.stream(16_000, batch=2_000, start=600_000)` as a Parquet folder, run
   `workers.describe_frame` over it with `map_partitions`, and find the vendor with the highest
   mean polar surface area. How many partitions did Dask use?
6. *To think about:* your group wants fingerprints for 50 million molecules every night, on a
   shared server with 32 cores and 64 GB of memory, where other people also run jobs. How would
   you choose the number of workers and the chunk size, what would each worker read and write, and
   how would you check that the parallel run gives the same answer as the serial one?
