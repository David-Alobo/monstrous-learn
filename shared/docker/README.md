# The courses' databases, in Docker

Some lessons need a database server: PostgreSQL with the RDKit cartridge (Series 1, Module 4) and
Neo4j (Module 5). A **database server** is a program that keeps data in tables or graphs and
answers questions about it; your Python code talks to it over a network connection, even when both
are on the same computer. Installing a database server by hand is different on every computer and
easy to get subtly wrong, so the course runs both in **Docker**, which gives every learner the same
database on Windows, macOS and Linux.

This guide assumes nothing: if a step says "type", it also says where, and after each step it says
what you should see. If what you see is different, go to [When something goes wrong](#when-something-goes-wrong).

## What Docker does, in four words

- An **image** is a packaged program with everything it needs: an operating system's files, the
  database, its libraries, at exact versions. `compose.yml` names the two images the course uses.
- A **container** is a running copy of an image, kept apart from the rest of your computer. It can
  be stopped, deleted and started again from the same image in seconds.
- A **volume** is where a container keeps data that must outlive it: your tables survive stopping
  and deleting the container, until you delete the volume.
- **Compose** starts several containers from one file (`compose.yml`), with their settings, ports
  and volumes, so one command brings up the whole stack.

Module 13 comes back to images, as a way to pin a pipeline's whole environment.

## Before you start: a terminal and the course's files

**A terminal** is a window where you type commands instead of clicking. Every command in this guide
is typed into one and run by pressing Enter.

| Your computer | Which terminal to open |
|---|---|
| Windows (with the WSL route below) | **Ubuntu**, from the Start menu. Its prompt looks like `you@COMPUTER:~$`. |
| macOS | **Terminal**, from Applications → Utilities (or press Cmd+Space and type "Terminal"). |
| Linux | Your distribution's terminal (often Ctrl+Alt+T). |

Two things surprise people the first time. When a command starts with `sudo` ("do as
administrator"), the terminal asks for **your password** (on Windows, the Ubuntu password you chose
when installing Ubuntu, not your Windows one), and **nothing appears while you type it**, not even
dots: type it and press Enter. And a command that prints nothing has usually worked: terminals
report problems, not successes.

**The course's files** live in a Git repository. Get a copy once, in the terminal:

```bash
git clone https://github.com/David-Alobo/monstrous-learn.git
cd monstrous-learn
```

The first line downloads the repository into a new folder called `monstrous-learn`; the second
moves the terminal into it (`cd` means "change directory"). This folder is **the repository's
root**: when a step says "from the repository's root", first `cd` into it. `ls` lists what is in
the folder you are in; at the root you see `README.md`, `shared` and `data-engineering` among
others. If `git` is not found, install it first (`sudo apt install git` in Ubuntu; on macOS, typing
`git` offers to install it).

## 1. Install Docker

Pick the row for your computer. Everything listed is free for learners.

| Your computer | Recommended | Alternative |
|---|---|---|
| Windows 10 or 11 | Docker Engine inside WSL (below) | Docker Desktop |
| macOS (Intel or Apple silicon) | [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) | [Colima](https://github.com/abiosoft/colima) (`brew install colima docker docker-compose`, then `colima start`) |
| Linux | Docker Engine from your distribution or [Docker's own packages](https://docs.docker.com/engine/install/) | |
| A tablet, a locked-down computer, or no install wanted | [GitHub Codespaces](https://docs.github.com/codespaces): open the repository in a codespace, which has Docker already | |

Docker Desktop is free for personal use, education and small businesses; a large company needs a
paid subscription for it, which is one reason this guide prefers Docker Engine on Windows. On
macOS, open Docker Desktop after installing it and wait until it shows "Engine running" before
going on.

### Windows: Docker Engine inside WSL

WSL (Windows Subsystem for Linux) runs a real Ubuntu Linux inside Windows. Docker Engine runs
there, as on any Linux server, and what it serves can be reached from Windows at `localhost` (the
name every computer uses for itself).

1. **Install WSL and Ubuntu.** Click Start, type "PowerShell", right-click **Windows PowerShell**
   and choose **Run as administrator**. In that window type `wsl --install -d Ubuntu`, press Enter,
   and restart Windows when it has finished. Then open **Ubuntu** from the Start menu: the first
   time, it asks you to choose a user name and a password. They are for Ubuntu only; write the
   password down, because `sudo` asks for it.
2. **Check that Ubuntu uses systemd**, the part of Linux that starts services such as Docker for
   you. In the Ubuntu terminal type `ps -p 1 -o comm=`. It should print `systemd`. If it prints
   anything else, type `sudo nano /etc/wsl.conf` to open that file in a simple editor, add these
   two lines, save with Ctrl+O then Enter, and leave with Ctrl+X:

   ```ini
   [boot]
   systemd=true
   ```

   Then, in PowerShell (an ordinary window is fine), type `wsl --shutdown`, open Ubuntu again, and
   repeat the check.

3. **Install Docker Engine and Compose.** In the Ubuntu terminal, one line at a time:

   ```bash
   sudo apt update                                   # refresh the list of available software
   sudo apt install -y docker.io docker-compose-v2   # install Docker and Compose
   sudo systemctl enable --now docker                # start Docker now, and whenever Ubuntu starts
   sudo usermod -aG docker $USER                     # let your user run Docker without sudo
   exit                                              # close Ubuntu; open it again for the last line to count
   ```

   The first two print many lines and take a minute or two; they end without an error.

4. **Check it works.** In a new Ubuntu terminal type `docker run --rm hello-world`. The first time
   it downloads a tiny image, then prints a few paragraphs starting with **Hello from Docker!**.

Keep the repository inside Ubuntu: run the `git clone` above in the Ubuntu terminal, which puts it
in your Ubuntu home folder. Files under `/mnt/c/...` (your Windows drive) also work, but are slower
to read from Linux. Windows Explorer shows your Ubuntu files under **Linux** in its left-hand pane,
and VS Code opens them with its **WSL** extension.

## 2. Choose your passwords: the `.env` file

A database server only answers someone who logs in, with a user name and a password. Passwords
never go in code or in files that Git stores (Module 4 explains why), so the course keeps them in a
file called **`.env`**, at the repository's root, that only you have. The repository holds a
template, `.env.example`, with every setting the course needs and a placeholder for each password.
Make your own copy once. In the terminal, from the repository's root:

| macOS, Linux, WSL | Windows (PowerShell) |
|---|---|
| `cp .env.example .env` | `Copy-Item .env.example .env` |

Then open `.env` in a text editor and replace each `change-me-...` with a password of your own
(letters and digits, at least 8 characters, different from any password you use elsewhere): in
WSL or Linux type `nano .env` (save with Ctrl+O then Enter, leave with Ctrl+X); on Windows,
`notepad .env`; on macOS, `open -e .env`. It looks like this, with your passwords in place of the
placeholders:

```ini
POSTGRES_USER=learn
POSTGRES_PASSWORD=change-me-postgres
POSTGRES_DB=chem
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
ANALYST_PASSWORD=change-me-analyst
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me-neo4j
NEO4J_URI=bolt://localhost:7687
```

Each line is one setting, `NAME=value`. `DATABASE_URL` is the address the lessons use for
PostgreSQL, built from the lines above it (`${POSTGRES_PASSWORD}` means "the value of
`POSTGRES_PASSWORD`"), so each password is written only once. The repository's `.gitignore` file
lists `.env`, so Git never stores it: never remove it from that list, and never share the file.
(Files whose names start with a dot are hidden in most file browsers; the terminal's `ls -a` shows
them.)

## 3. Start the databases

In the terminal, from the repository's root:

```bash
docker compose --env-file .env -f shared/docker/compose.yml up -d postgres neo4j
```

`up` starts the containers, `-d` leaves them running in the background, `--env-file .env` gives
Docker your passwords, and `-f` says which Compose file to use. The first time, Docker downloads
the two images (about 1 GB in all), which takes a few minutes and prints download progress. It
ends with:

```text
 Container docker-postgres-1  Started
 Container docker-neo4j-1  Started
```

Wait about 30 seconds for the databases to finish starting inside their containers, then check:

```bash
docker compose --env-file .env -f shared/docker/compose.yml ps
```

Both lines should say `Up`, and PostgreSQL's also `(healthy)`, meaning it answers queries. Neo4j
has no health check, so it only says `Up`.

The passwords count from the first start: both databases set them only when their data is created.
To change a password later, change it in `.env`, delete the old data (`down -v`, in section 7) and
start again.

## 4. Where the databases are, and who can log in

| Database | Address | User name | Password | Database name |
|---|---|---|---|---|
| PostgreSQL | `localhost`, port `5432` | `POSTGRES_USER` in your `.env` (`learn`) | `POSTGRES_PASSWORD` in your `.env` | `chem` |
| Neo4j | `localhost`, ports `7474` (browser) and `7687` (Python) | `neo4j` | `NEO4J_PASSWORD` in your `.env` | (the default) |

These databases can be reached from your own computer and nowhere else: `compose.yml` opens their
ports only on `127.0.0.1` and `::1`, the two addresses (IPv4 and IPv6) that mean `localhost`, and
not to the network. A database on a server or a virtual machine also needs long random passwords,
kept by whoever runs it.

## 5. Look inside the databases

### Neo4j, in your web browser

Neo4j comes with a web page for looking at the graph and typing queries.

1. Open <http://localhost:7474> in any web browser on the same computer (type it in the address
   bar, where you would type a website's name).
2. You see a form called **Connect to instance**. Leave **Protocol** (`neo4j://`) and
   **Connection URL** (`localhost:7687`) as they are. **Database user** already says `neo4j`.
   Click in **Password**, type your `NEO4J_PASSWORD` from `.env`, and click **Connect**.

   ![The "Connect to instance" form: Protocol neo4j://, Connection URL localhost:7687, Database user neo4j, an empty Password box and a Connect button](images/neo4j-connect.png)

3. You are in. The top line shows the instance, the database and the user, with a green dot when
   connected. On the first visit a purple box offers a tour ("Work in tabs"): click **Dismiss**.

   ![Neo4j Browser after logging in: a green dot and "Instance: neo4j://localhost:7687" at the top, a $ line for typing queries with a Run button, welcome cards below, and a purple "Work in tabs" tour box with Dismiss and Next buttons](images/neo4j-logged-in.png)

4. Click the line that starts with `$` near the top: this is where you type queries. Type
   `RETURN 1 AS ok` and click **Run** (or press Ctrl+Enter; Cmd+Enter on a Mac). A result appears
   underneath, as a table with the column `ok` and the value `1`:

   ![The query RETURN 1 AS ok and its result: a table with one column, ok, and one row, 1](images/neo4j-first-query.png)

   Each query you run adds its result on top of the earlier ones; the **×** on the right removes
   one.

Module 5 uses this page to draw molecules and their links as a graph.

### PostgreSQL, in the terminal

PostgreSQL comes with `psql`, a program for typing SQL. It is already inside the container, so
nothing needs installing. From the repository's root:

```bash
docker compose --env-file .env -f shared/docker/compose.yml exec postgres psql -U learn -d chem
```

`exec postgres` runs a command inside the running `postgres` container; `-U learn -d chem` logs in
as user `learn` to the database `chem` (use your `POSTGRES_USER` and `POSTGRES_DB` if you changed
them; inside the container no password is asked). The prompt changes to `chem=#`. Type this query,
ending with a semicolon, and press Enter:

```sql
select mol_from_smiles('OC1=CC=CC=C1') as phenol;
```

The RDKit cartridge reads the SMILES and writes it back in its own form:

```text
  phenol
-----------
 Oc1ccccc1
(1 row)
```

Type `\q` and press Enter to leave `psql`.

## 6. The lessons find the databases by themselves

The lessons that use a database (Modules 4 and 5) read your `.env` file when their Setup block
runs, with the small package python-dotenv, so there is nothing more to do. Their settings are
**environment variables**: named values that programs read from their surroundings. A value that
is already set in your terminal wins over the one in `.env`, which is how GitHub's automatic tests
give the lessons their own passwords.

To check that Python can reach both databases, start Python in the series' environment (from
`data-engineering/series-1`, type `uv run python`; the prompt becomes `>>>`), paste this, and
press Enter twice:

```python
import os

import psycopg
from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

load_dotenv(find_dotenv(usecwd=True))  # finds .env in this folder or the folders above
with psycopg.connect(os.environ["DATABASE_URL"]) as db:
    print(db.execute("select mol_to_smiles(mol_from_smiles('OC1=CC=CC=C1'))").fetchone()[0])
auth = (os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=auth) as driver:
    driver.verify_connectivity()
    print("neo4j: ok")
```

It prints `Oc1ccccc1` (phenol, written by the RDKit cartridge) and `neo4j: ok`. Type `exit()` to
leave Python. Notice that no password appears in the code: it is read from `.env`.

## 7. Stop them

From the repository's root:

```bash
docker compose --env-file .env -f shared/docker/compose.yml stop      # stop; start again with "up -d"
docker compose --env-file .env -f shared/docker/compose.yml down      # remove the containers; the data is kept
docker compose --env-file .env -f shared/docker/compose.yml down -v   # remove the containers and delete the data
```

Until you stop them, the containers start again on their own whenever Docker starts, so the
databases are there when you come back. The images are pinned to exact versions (`compose.yml`),
so every learner gets the same database.

## When something goes wrong

| What you see | What it means, and what to do |
|---|---|
| `docker: command not found` | Docker is not installed in this terminal. On Windows, check you are in the **Ubuntu** terminal, not PowerShell. Then follow section 1. |
| `Cannot connect to the Docker daemon` | Docker is installed but not running. WSL or Linux: `sudo systemctl start docker`. Docker Desktop: open it and wait for "Engine running". |
| `permission denied ... docker.sock` | Your user is not in the `docker` group yet: run `sudo usermod -aG docker $USER`, then close the terminal and open it again. |
| `no configuration file provided` or `open shared/docker/compose.yml: no such file` | The terminal is not at the repository's root. `cd` into the `monstrous-learn` folder and try again. |
| `port is already allocated` or `address already in use` | Something else already uses the port, usually a PostgreSQL installed on the computer. Stop it, or in `compose.yml` change both lines ending `5432:5432` to end `5433:5432` (keep the address in front of them) and use port 5433 in `DATABASE_URL`. |
| The Neo4j page says the connection or the password failed | Wait 30 seconds after starting (Neo4j starts slowly), check you typed the `NEO4J_PASSWORD` from your `.env`, and that the Connect URL ends in `localhost:7687`. |
| `password authentication failed for user "learn"` | The database was first started with a different password from the one now in `.env` (it keeps the first one). Delete the data (`down -v`) and start again, or put the first password back in `.env`. |
| `required variable POSTGRES_PASSWORD is missing` | Docker did not find your `.env`. Check the file exists at the repository's root (`ls -a` lists it), that the command includes `--env-file .env`, and that you run it from the repository's root (section 2). |
| A lesson skips its database blocks although the databases are running | The lesson did not find `.env`: run the lesson from inside the repository, so the file is in a folder above it. |
| The containers stop a minute after you close the terminal (WSL) | WSL shuts Ubuntu down when nothing is using it. Keep an Ubuntu terminal open while you work; the containers start again with Ubuntu. |
| Docker Desktop does not open, or closes at once | Often an update that did not finish. Reinstall it from docker.com, or use the WSL route above instead. Do not run Docker Desktop and Docker Engine in WSL at the same time: both want the same ports. |
| Neo4j's log says `Changed password ... only take effect ... first time` | Normal on the first start. |
| Python waits about 15 seconds before connecting, or seems to hang | `localhost` is tried as IPv6 (`::1`) first, and the database is only listening on IPv4. Use the `compose.yml` from the repository, which listens on both, or write `127.0.0.1` instead of `localhost`. |
| Text comes back from PostgreSQL as `b'...'` in Python | The database was created with the `SQL_ASCII` encoding, by an older `compose.yml`. Delete the data and start again (`down -v`, then `up -d`): the current file creates it as UTF-8. |

## No Docker?

Lessons that need a database say so at the top, and their code that needs it is marked
`# needs: postgres` or `# needs: neo4j`; the rest of each lesson runs without it.
