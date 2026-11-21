# Homework: Capstone: a resumable, monitored pipeline over a large library

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. Run `pipeline.run` on 6,000 molecules with `seed=27`, `defect_rate=0.05` and `batch_size=300`
   (into a new `out_dir`). How many batches are there, what are the counts at every stage, and do
   they reconcile? Which quarantine reason is most common?
2. Make batch 0 fail three times (`Faults(flaky_reads={0: 3})`) with `max_attempts=3`. What happens
   to the run, and what does the run history say about it afterwards? Run it again without the
   fault: which batches does the second run do?
3. Crash a run in a batch of your choice, resume it, and run the same settings uninterrupted into
   another folder. Compare `data_sha256` from the two manifests. Then do the same with `workers=1`
   for one of the runs. Is the data still identical, and how long did each take?
4. Change `max_logp` to 5.5. How many more compounds pass the filters? Does `rules_hash()` change?
   Should a property limit be part of the rules hash or only of the settings in the manifest? Give
   one argument each way.
5. Query your output from question 1 in DuckDB: the five compounds with the highest TPSA, the share
   of compounds with no hydrogen-bond donors, and the Tanimoto similarity of the first compound to
   aspirin, using its stored fingerprint (unpack it with `np.unpackbits`).
6. **To think about.** For a capstone built on one ChEMBL target, the records are activity
   measurements, not just compounds, and ChEMBL publishes a new release every few months. What would
   you use as a record's identity, and how would the checkpoints and the table of InChIKeys already
   seen work when you load the next release on top of this one?
