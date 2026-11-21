# Homework: Versioning everything

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
helpers (`git`, `migrate`, `rules_hash`, `write_with_provenance` and the others) exist. If you are
in a cohort, you will be told where to send your answers; everyone can check theirs against the
answers published after the cohort's deadline.

1. *(Builds on section 1.)* Make a new repository in a new folder under `work/` (for example
   `work/homework-repo`, made with `.mkdir()` and `git(folder, "init", "--quiet",
   "--initial-branch=main")`, as the lesson does). Commit a file `filters.py` (any short Python
   code will do) and tag it `v0.1.0`; then make two more commits that change it, and tag the second
   `v0.2.0`. What does `git describe --tags` print after each step, and what does it print if you
   then edit `filters.py` without committing (add `--dirty`, as the lesson does)? Use `git show` to
   print `filters.py` as it was at `v0.1.0`.
2. *(Builds on section 3.)* Write a migration `0005_add_activity_type.sql` that adds an
   `activity_type` column (text) to `measurements`, put it in the `MIGRATIONS` folder, and apply it
   with the lesson's `migrate()`. What does the `schema_migrations` table hold afterwards (read it
   with `db.execute("SELECT * FROM schema_migrations").fetchall()`)? Now write a migration
   `0006_...` with a mistake in its SQL (a misspelt word, for example): what happens to the
   database and to `schema_migrations` when it fails, and why? (Hint: the transaction.)
3. *(Builds on section 5.)* Make a library with `chemlib.library(3_000, seed=41)` and write it as
   CSV twice: once with `lineterminator="\n"` and once with `lineterminator="\r\n"` (the two
   ways of ending a line, explained in section 5). Are the two SHA-256 hashes from `file_sha256`
   equal? Read both back with `pd.read_csv`: are the tables equal (`.equals`)? What does this mean
   for a manifest?
4. *(Builds on section 4.)* Add a rule to a copy of the lesson's `RULES` (for example
   `"max_heavy_atoms": 50`) without changing the version. What does `check_rules()` say? Then
   release it properly as version `2.2.0`, by giving the copy that version and adding its hash to
   `RELEASED_RULES`, and show that both versions now pass.
5. *(Builds on section 6.)* Use the lesson's `write_with_provenance()` to write a second result:
   the number of compounds per vendor in each stock band. A stock band is a range of stock, for
   example 0 to 99 mg, 100 to 999 mg and 1,000 mg or more (`pd.cut` sorts numbers into ranges).
   Choose your own bands and pass them as parameters, so they are in the record. Then change one
   parameter and rebuild: which fields of the record change, and which stay the same?
6. **To think about** *(no code)*: a colleague's paper reports a model trained on "ChEMBL 34 kinase
   data, standardised". List everything you would need to rebuild their training set exactly,
   which of those a provenance record like the lesson's would capture, and which it would not. What
   would you add to the record so that someone could rebuild your numbers in five years' time?
