# Homework: Structure-activity dashboards

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there, or change `work/dashboard.py` and test it
with `run_app()`. Run the whole lesson first, so that the published warehouse, the app and the
`add` and `run_app` functions exist. If you can, also run the app with `streamlit run` on your own
computer and look at your changes. If you are in a cohort, you will be told where to send your
answers; everyone can check theirs against the answers published after the cohort's deadline.

1. *(Builds on section 2.)* Add a fifth metric, "Median LipE", for the compounds shown, and a filter
   by chemist in the sidebar. Test both with `run_app()`: what are the metrics for chemist EF's
   compounds only, and what do they say about the drift Module 8 found?
2. *(Builds on section 3.)* The weekly chart shows means, which hide how many compounds each point
   stands for. Add the number of compounds to each point's tooltip, and make the point's size show
   it (`size=alt.Size(...)`). Which week and series rest on the fewest compounds?
3. *(Builds on section 4.)* Give the scatter plot a second view: LipE against EGFR pIC50, with a
   line at LipE = 5 (a common target for optimised compounds). Which series has the most compounds
   above it? Check your chart's layers with `json.loads(chart.proto.spec)` as the lesson did.
4. *(Builds on section 5.)* Add a download button under the table (`st.download_button`) that
   gives the shown compounds as a CSV file without the structure pictures. Test that the button is
   there (`app.get("download_button")`) and that its data has the right number of rows.
5. *(Builds on section 6.)* For a compound tested on the panel, add a small bar chart of its mean
   pIC50 on each of the five kinases, with EGFR in its own colour and the panel kinases in grey.
   Use LAB-0023 to test it: which kinase comes closest to EGFR?
6. *(Builds on section 1.)* Change `ttl` to 5 seconds, rebuild the warehouse with one more change
   (for example, run `labstack.dbt` on a project in which a compound's series is renamed), publish
   it again and rerun the app twice, more than five seconds apart. When did the change appear?
   What would go wrong if the app read the working warehouse instead of the published copy while
   the pipeline was building?
7. **To think about** *(no code; builds on the whole module)*: write down three questions a
   medicinal chemist on this project might ask that the dashboard cannot answer yet. For each, say
   which layer of the warehouse would have to change (raw, staging, a mart, or only the app), and
   why.
