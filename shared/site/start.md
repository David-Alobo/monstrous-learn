---
title: Start here
summary: What you need, how to run a lesson (in your browser or on your own computer), how a lesson page works, and the words you will meet. Nothing is assumed.
---

This page is for anyone starting the courses, whatever you know already. It says what you need,
how to run a lesson, and how to read one. You can come back to it at any time.

## Is this course for me?

The courses are for chemists, and for anyone else who works with chemical data, who want to handle
that data the way software engineers do: reliably, at any size, and so that every number can be
traced back to where it came from. That work is called **data engineering**.

You need to have written a little Python: if you have run a few cells in a Jupyter notebook, used a
`for` loop and called a function, you can start. If Python is new to you, work through the first
five sections of [the official Python tutorial](https://docs.python.org/3/tutorial/) first (an
afternoon or two); everything else is taught here. Git, databases, Docker and the other tools you
see listed are **taught in the course**: none of them is needed to start.

## How the courses are organised

- A **track** is a subject: Data Engineering for Chemistry is the first.
- A track has **series**, which are courses taken in order: Series 1 is *Data Engineering for
  Cheminformatics*.
- A series has **modules**, one lesson each, released one a week while a cohort runs. Every module
  page has the lesson, its code, and homework at the end.

You can follow a series with a **cohort** (a group starting together on a set date, with a weekly
module, homework, a Discord community and a certificate), or on your own, at your own pace. The
modules already written are open to read now.

## What you need

| To... | You need |
|---|---|
| Read the lessons | Any device with a web browser: phone, tablet or computer. |
| Run the code, the easy way | A web browser and a free Google account (for Google Colab). Nothing to install. |
| Run the code on your own computer (optional) | Windows, macOS or Linux, and about 3 GB of free disk space. |
| Run the database lessons (Modules 4 and 5) | Your own computer with Docker; [the database guide]({base}databases/) shows how. |

## Run a lesson in your browser (recommended)

**Google Colab** is Google's free service for running Python notebooks in a web browser. A
**notebook** is a document made of **cells**: some cells are text, some are code you can run, and
what a code cell prints appears right under it.

1. Open a lesson's page (for example [Module 1]({base}data-engineering/series-1/01-graphs-and-matrices/))
   and, in its **Get set up** box, click **Open this lesson in Google Colab**.
2. The notebook opens. To run anything, Colab asks you to **sign in** with a Google account (top
   right): do so.
3. Run the **first code cell**: move the mouse over it and click the round ▶ button at its left, or
   click inside the cell and press **Shift+Enter** (Shift+Enter also moves you to the next cell).
   This cell installs what the lesson needs; it takes a minute or two and prints a few lines.
4. Colab may show **"Warning: This notebook was not authored by Google"**. That is Colab's standard
   notice for notebooks that come from GitHub, where this course's files are kept. Click
   **Run anyway**.
5. Run the other cells **in order, from the top**, one after another. Each one can use what the
   cells above it made, so skipping one usually makes a later one fail.
6. Compare what you see with the lesson's page: under each piece of code the page has a box
   labelled **Output**, and your cell should print the same. (Boxes labelled **Example output**
   show timings or memory, which differ from computer to computer.)

If a cell shows a red error, read its last line: it says what went wrong. The most common causes are
a cell skipped above it (click **Runtime → Run before** in Colab's menu, then run the cell again)
and Colab having restarted after a long pause (run the cells from the top again). Your changes in
Colab are not saved to the course; **File → Save a copy in Drive** keeps your own copy.

## Run a lesson on your own computer (optional)

Pick one of the two ways.

### If you already use Jupyter or Anaconda

1. On the lesson's page, click **Download the notebook** (it saves a file ending in `.ipynb`).
2. Open Jupyter as you usually do (for example, **Anaconda Navigator → JupyterLab**), find the file
   and open it.
3. Run the cells in order, from the top, as in Colab. The first cell installs what the lesson needs
   and downloads the course's small helper files next to the notebook.

### With a terminal, Git and uv (the way the course's own tests run)

A **terminal** is a window where you type commands instead of clicking. Every command below is
typed into one and run by pressing Enter. On Windows open **PowerShell** (Start menu, type
"PowerShell"); on macOS open **Terminal** (Cmd+Space, type "Terminal"); on Linux, your terminal.

1. **Install Git**, the tool that downloads the course's files and keeps track of their versions.
   Windows: download and run the installer from [git-scm.com](https://git-scm.com/downloads),
   accepting its suggested settings. macOS: type `git --version`; if Git is missing, macOS offers to
   install it. Linux: `sudo apt install git` (Ubuntu, Debian) or your distribution's equivalent.
   Check: `git --version` prints a version number.
2. **Install uv**, the tool that installs Python and the course's packages, at the exact versions the
   course was tested with. Windows (PowerShell):
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
   macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Then **close the terminal
   and open a new one**, so it finds uv. Check: `uv --version` prints a version number.
3. **Download the course** and move into Series 1's folder (`cd` means "change directory"):

   ```bash
   git clone https://github.com/David-Alobo/monstrous-learn.git
   cd monstrous-learn/data-engineering/series-1
   ```

4. **Install everything Series 1 uses**, once: `uv sync`. It downloads Python itself if needed and
   about a hundred packages, and ends with a line like `Installed 136 packages`.
5. **Run a lesson.** Either run its code from start to end in the terminal:
   `uv run python 01-graphs-and-matrices/code.py` (it prints the same outputs as the lesson's page),
   or open its notebook in JupyterLab: `uv run --with jupyterlab jupyter lab`, which opens your web
   browser; double-click the module's folder, then `notebook.ipynb`, and run the cells from the top.

When the course changes, `git pull` (in the `monstrous-learn` folder) fetches the new version and
`uv sync` installs anything new.

## How a lesson page works

Each module is one page, read from top to bottom:

1. **The title and one-line summary**, then **Where this module fits**: the steps of the course's
   big picture, with this module's step highlighted.
2. **Get set up**: how to run this lesson (the steps above, in short).
3. **The introduction** and **By the end of this module you will be able to**: what you will learn.
4. **Setup**: one block of code that every lesson starts with. It loads the packages the lesson
   uses (`import ...`) and sets the lesson's settings, written in CAPITALS, so they are all in one
   place.
5. **Numbered sections**, each a few paragraphs of explanation, code, and the code's **Output**.
   The code on the page is exactly the code in the notebook. Diagrams and pictures show what the
   code does.
6. **Try it yourself**: the homework, a few questions answered by running code like the lesson's.
7. **Further reading**, then links to the module before and after.

Some code prints with `log.info(...)` instead of `print(...)`: lines that start with `INFO` or
`WARNING` in an output come from it. Module 1 explains why, at the end of its lesson.

## Words you will meet

| Word | Meaning |
|---|---|
| Data engineering | Building the systems that collect, check, store and deliver data, so it can be trusted and used at any size. |
| Pipeline | A program that takes data through a series of steps (read, check, clean, store), the same way every time. |
| Package (library) | Code someone else wrote that you load with `import`: RDKit for chemistry, pandas for tables, NumPy for arrays of numbers. |
| SMILES | A way of writing a molecule as one line of text: `CCO` is ethanol. Module 2 explains it fully. |
| Notebook, cell | A document of text and runnable code cells (Jupyter, Colab). |
| Terminal | A window where you type commands. |
| Repository | A folder of files whose history Git keeps; the course's is on GitHub. |
| Database | A program that stores data in tables (or graphs) and answers questions about it. |
| Schema | The description of a table: its columns, their types and the rules the data must follow. |
| Docker | A tool that runs programs, such as a database, in a packaged form that works the same on every computer. |

## Stuck?

- Read the last line of the error: it usually names the problem.
- Run the cells again from the top: most errors come from a skipped cell.
- On Windows, if installing fails with a message about a path being too long, put the course in a
  short folder (for example `C:\code`) and try again: Windows limits paths to 260 characters unless
  [long paths are enabled](https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation).
- Ask in the course's Discord community (cohort members), or open an issue on the course's GitHub
  page.
