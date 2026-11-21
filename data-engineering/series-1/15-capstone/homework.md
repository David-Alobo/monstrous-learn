# Homework: Capstone: a resumable, monitored pipeline over a large library

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

Run the whole lesson first, from the top, so `pipeline`, `Tick`, `START`, `WORK` and the other
names exist. Every run needs its own output folder, or it will resume the run already there: give
each question a new one, such as `WORK / "hw1"`. A run starts like this (the settings you do not
name keep their defaults, shown in Section 2):

```python
hw1 = pipeline.Settings(n_molecules=6_000, seed=27, defect_rate=0.05, batch_size=300,
                        out_dir=WORK / "hw1", retry_wait_s=RETRY_WAIT_S)
manifest_hw1 = pipeline.run(hw1, Tick(START))
```

1. **A run of your own (Sections 2 to 7).** Run `pipeline.run` on 6,000 molecules with `seed=27`,
   `defect_rate=0.05` and `batch_size=300`, as above. How many batches are there, what are the
   counts at every stage (`manifest_hw1["counts"]`), and do they reconcile? Which quarantine reason
   is most common? (Open the run's database with
   `duckdb.connect(str(WORK / "hw1" / "pipeline.duckdb"), read_only=True)` and count the rows of
   the `quarantine` table by `reason`.)
2. **When retries run out (Section 3).** Make batch 0 fail three times
   (`pipeline.Faults(flaky_reads={0: 3})`, passed to `pipeline.run` as its third argument) with
   `max_attempts=3` in the settings, so the pipeline gives up before the source answers. Wrap the
   run in `try:` / `except ConnectionError as err:` to see the error. What happens to the run, and
   what does the run history say about it afterwards (the `runs` and `batches` tables, as in
   Section 6)? Run it again without the fault: which batches does the second run do?
3. **Crash, resume, compare (Sections 6 and 9).** Crash a run in a batch of your choice
   (`pipeline.Faults(crash_in_batch=5)`, and catch `pipeline.SimulatedCrash` as the lesson does),
   then resume it by running the same settings again without the fault. Run the same settings
   uninterrupted into another folder and compare `data_sha256` from the two manifests. Then do the
   same with `workers=1` for one of the runs. Is the data still identical, and how long did each
   take (time them with `time.perf_counter()`, as the lesson does)?
4. **Rules and settings (Sections 4 and 5).** Change `max_logp` to 5.5 and run again into a new
   folder. How many more compounds pass the filters? Does `pipeline.rules_hash()` change? Should a
   property limit be part of the rules hash, or only of the settings recorded in the manifest? Give
   one argument each way.
5. **Querying the output (Sections 5 and 10).** Query your output from question 1 in DuckDB: the
   five compounds with the highest TPSA, the share of compounds with no hydrogen-bond donors
   (`hbd = 0`), and the Tanimoto similarity of the first compound to aspirin. Tanimoto similarity
   compares two fingerprints: the number of bits set in both, divided by the number of bits set in
   either; 1 means the same fingerprint. Unpack each stored fingerprint with `np.unpackbits`, as in
   Section 5. To get aspirin's fingerprint made the same way, run it through the pipeline's own
   code:
   `pipeline.process_batch(pd.DataFrame({"id": ["aspirin"], "smiles": ["CC(=O)Oc1ccccc1C(=O)O"], "defect": [""]}))[0]["morgan2"].iloc[0]`.
6. **To think about (Section 11 and the brief).** For a capstone built on one ChEMBL target, the
   records are activity measurements (one result, such as an IC50, for one compound in one assay),
   not just compounds, and ChEMBL publishes a new release (a new version of the whole database)
   every few months ([Module 11](../11-incremental-ingestion/)). What would you use as a record's
   identity, and how would the checkpoints and the table of InChIKeys already seen work when you
   load the next release on top of this one?
