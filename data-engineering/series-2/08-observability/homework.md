# Homework: Observability

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse (weeks 1 to 12), the `monitoring` tables, the checks and the `weekly` flow exist. If you
are in a cohort, you will be told where to send your answers; everyone can check theirs against
the answers published after the cohort's deadline.

1. *(Builds on section 1.)* For each of the lab's planted problems (`lab.events`), say which of the
   four kinds of check (freshness, volume, schema, distribution) should catch it, and which check
   of the lesson did. Is there one that only a check of a different kind could catch?
2. *(Builds on section 3.)* Change the source freshness limits so that dbt warns after one minute
   (`{count: 1, period: minute}`), wait a little over a minute, and run
   `labstack.dbt(PROJECT, "source", "freshness", log=quiet)` again. What status does it give now?
   Explain why that check would still have passed in week 10 on a real schedule.
3. *(Builds on section 4.)* The volume check compares with the median of the weeks before. Change
   it to compare with the mean, and rerun the checks on the recorded metrics (call
   `check_volume.fn(week)` for weeks 7 to 12). Which alerts change, and why is the median the
   better choice for a lab whose weeks include a resent file and a late one?
4. *(Builds on section 4.)* Write a new check, `check_panel`, that alerts when the share of
   this week's EGFR results potent enough for the selectivity panel (pIC50 of 7 or more) differs
   from the baseline weeks' share by more than 15 percentage points. Add it to `CHECKS` and rerun
   week 12 in a fresh copy of the lesson. Does it fire? Why might potency drift follow structure
   drift a week later?
5. *(Builds on section 5.)* Plot `drift_mw`, `drift_clogp` and `drift_heavy_atoms` week by week from
   `monitoring.metrics`, with matplotlib, on one figure with the `DRIFT_LIMIT` drawn as a line.
   Then compare the compounds EF registered in weeks 11 and 12 with the other chemists' compounds
   of the same series: which substituents does EF use that the others do not? (`lab.compounds` has
   each compound's chemlib index; `chemlib.parts_at` turns it into substituents.)
6. *(Builds on section 6.)* Make a free incoming webhook (for example a Discord channel's, or
   `https://webhook.site`, which shows what it receives), set `LAB_ALERT_WEBHOOK` to its address,
   and rerun week 11. What arrived? Then make `send` post one message per week, listing all of that
   week's alerts, instead of one per alert. Why is that better for the people who receive them?
7. **To think about** *(no code; builds on section 6)*: a week with five alerts, four of them about
   the same drift, is noisy. Propose rules that would make the lab's alerts fewer without hiding
   anything important: for example, one alert per cause, or alerts that stop once someone has
   acknowledged them. What would each need the monitoring tables to record?
