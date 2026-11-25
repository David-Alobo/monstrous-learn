# Homework: Orchestration

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse (weeks 1 to 12), the tasks, the `weekly` flow and Prefect's record of its runs exist. If
you are in a cohort, you will be told where to send your answers; everyone can check theirs
against the answers published after the cohort's deadline.

1. *(Builds on section 1.)* Change `receive` so that the share fails at *every* attempt for week
   12, and run `weekly(12, return_state=True)`. How many attempts did Prefect make, how long did it
   wait between them, and which tasks ran after `receive`? Then give `receive`
   `retries=3, retry_delay_seconds=[1, 2, 4]` (a list) and explain what that changes, and why
   waiting longer each time suits a share that is down.
2. *(Builds on section 1.)* Prefect can run tasks at the same time. `check_chemistry` and `draw`
   do not depend on each other: call them with `.submit(...)` instead of calling them directly,
   and get their results with `.result()`. Does the flow give the same summary? What would have to
   be true of two tasks for running them at the same time to be safe?
3. *(Builds on section 3.)* Delete the drawings of week 12 (`work/published/structures`), then run
   `weekly(12)` again. Did `draw` run, or did it return its cached result? What does that tell you
   about what `cache_policy=INPUTS` checks, and what it does not? Change the cache so that it
   expires after one day (`cache_expiration=timedelta(days=1)`, from `datetime`).
4. *(Builds on section 3.)* Make the chemistry check fail the flow when more than five compounds
   are in quarantine, and only warn below that. Test it with a stricter rule that some compounds
   break: add `pc.mol_weight(400)` to `COMPOUND_RULES` and run `weekly(12, return_state=True)`.
   How many compounds were quarantined, did the flow fail, and which tasks did not run?
5. *(Builds on section 4.)* With the client, read the task runs of the failed run of week 12 only
   (`client.read_task_runs(flow_run_filter=...)`; see Prefect's documentation for the filter, or
   filter in Python on `flow_run_id`). Which tasks ran, and in which state did each finish?
6. *(Builds on section 5.)* Write the cron expression for each of these, and check it with a cron
   website or by reasoning field by field: (a) 06:30 every weekday; (b) every hour on the hour; (c)
   midnight on the first day of every month; (d) every 15 minutes between 08:00 and 18:00 on
   weekdays. Which would suit the "run often" approach of section 5 for this lab, and why?
7. **To think about** *(no code; builds on sections 2 and 5)*: in week 10 the flow completed
   although the week's assay file never came. List the people who should know that a week's file
   is missing, and how quickly. Should the flow fail, warn, or do something else? (Module 8 takes
   this up.)
