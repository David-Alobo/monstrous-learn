# Homework: Monitoring pipelines

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. Make a night's file with `chemlib.library(2000, seed=7)` and `chemlib.add_defects(..., rate=0.06,
   seed=7)`, and run it through the lesson's four steps with `run_pipeline`. How many rows does each
   step take in and pass on, and does the run reconcile?
2. Add a step that drops every molecule with a molecular weight above 450 **without** reporting
   them (return `NO_ROWS` and 0 duplicates). Run the night again. What does `reconcile` report, and
   how would you rewrite the step so the counts add up and the reason is kept?
3. Write a log line for a run whose source is `https://api.example.org/v1/compounds?token=abc123&page=2`.
   What does the formatter write to the file? Add `secret=` to the redaction pattern and test it on a
   string of your own.
4. Compute the PSI and the KS statistic for molecular weight and logP of
   `chemlib.library(1500, seed=300)` against the lesson's reference, then for a batch streamed from
   molecule number 113,400 (`chemlib.stream(1500, batch=1500, start=113_400)`). Which way has each
   property moved, and which descriptor would alert first?
5. PSI depends on its bins. For the ordinary batch in question 4, compute PSI for molecular weight
   with 5, 10, 20 and 50 bins, and for random samples of 200, 1,500 and 10,000 molecules. How do
   the values change, and what does that mean for a fixed threshold of 0.1?
6. **To think about.** Your team runs ten pipelines and gets about forty alerts a week, most of
   which nobody acts on. Which alerts would you keep as pages, which would you turn into tickets or a
   weekly report, and which would you delete? What would you measure to know the change worked?
