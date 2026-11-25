# Recorded ChEMBL answers

These ten files are ChEMBL web service answers, recorded once on 25 November 2026 for Module 2:
the first two pages of 100 IC50 activities (with a pChEMBL value) for each of the lab's five
kinase targets. The lesson replays them through `chembl_replay.py`, so it gives the same results
on every computer and works offline. Each file is named by a hash of the request it answers.

The data come from ChEMBL (https://www.ebi.ac.uk/chembl/) and are licensed under the Creative
Commons Attribution-ShareAlike 3.0 Unported licence (CC BY-SA 3.0), not under this repository's
code or content licences. If you reuse them, credit ChEMBL and share under the same licence.

Zdrazil, B. et al. (2024). The ChEMBL Database in 2023: a drug discovery platform spanning
multiple bioactivity data types and time periods. *Nucleic Acids Research*, 52(D1), D1180–D1192.
https://doi.org/10.1093/nar/gkad1004

To record them again (the answers will differ, because ChEMBL keeps growing), from the series
folder: `CHEMBL_MODE=record uv run python lessonkit.py 02-declarative-ingestion --write`.
