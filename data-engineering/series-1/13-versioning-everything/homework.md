# Homework: Versioning everything

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. In a new repository under `work/`, commit a file `filters.py`, tag it `v0.1.0`, then make two
   more commits and tag the second `v0.2.0`. What does `git describe --tags` print after each
   step, and what does it print if you then edit `filters.py` without committing? Use `git show`
   to print `filters.py` as it was at `v0.1.0`.
2. Write a migration `0005_add_activity_type.sql` that adds an `activity_type` column to
   `measurements`, and apply it with the lesson's `migrate()`. What does `schema_migrations` hold
   afterwards? Now write a migration with a mistake in its SQL: what happens to the database and
   to `schema_migrations` when it fails, and why?
3. Make a library with `chemlib.library(3_000, seed=41)` and write it as CSV twice: once with
   `lineterminator="\n"` and once with `lineterminator="\r\n"`. Are the two SHA-256 hashes equal?
   Read both back with pandas: are the tables equal? What does this mean for a manifest?
4. Add a rule to the lesson's `RULES` (for example `"max_heavy_atoms": 50`) without changing the
   version. What does `check_rules()` say? Release it properly as version `2.2.0` and show that
   both versions now pass.
5. Use the lesson's `write_with_provenance()` to write a second result, the number of compounds
   per vendor in each stock band (choose your own bands and pass them as parameters, so they are
   in the record). Then change one parameter and rebuild: which fields of the record change, and which
   stay the same?
6. **To think about:** a colleague's paper reports a model trained on "ChEMBL 34 kinase data,
   standardised". List everything you would need to rebuild their training set exactly, which of
   those a provenance record like the lesson's would capture, and which it would not. What would
   you add to the record so that someone could rebuild your numbers in five years' time?
