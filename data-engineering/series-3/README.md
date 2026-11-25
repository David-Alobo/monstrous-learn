# Series 3: Data Pipelines for Digital and Autonomous Chemistry

Track: Data Engineering for Chemistry. The data side of automated synthesis: from designed molecules to checked results.

**Status:** Planned · **Level:** After Series 1 and 2 · **[Read it online](https://monstrous.com.ng/learn/data-engineering/series-3/)**

What it takes to move data safely between molecular design, robotic synthesis and analysis: checks before synthesis, reaction metadata, instrument data, pipeline monitoring and a small intake service.

## Modules

1. **From design to make.** Why moving from a virtual library to robotic synthesis is a data problem.
2. **Checking molecules before synthesis.** An intake check for stereocentres, salts and unstable groups. *RDKit*
3. **Reaction and synthesis metadata.** Relational tables for conditions, building blocks, yields and purity, including reading free-text conditions such as reaction times and temperatures with their units. *PostgreSQL*
4. **Instrument data back into the pipeline.** Parse LC-MS and NMR exports into structured tables to confirm what was made. *mzML*
5. **Monitoring lab data pipelines.** Catch schema drift, missing readings and corrupted values before they reach a model. *Pandera, Prefect*
6. **A chemical intake service.** Wrap the checks and structure previews in a small web API. *FastAPI*
7. **Capstone: a closed-loop pipeline.** Validate targets, log metadata, check analytical results and update the dataset safely. *Everything above*

Each module will have its own folder here, with its lesson and notebook.

*This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;
the course page is https://monstrous.com.ng/learn/data-engineering/series-3/.*
