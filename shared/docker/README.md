# The courses' databases, in Docker

Some lessons need a database server: PostgreSQL with the RDKit cartridge (Series 1, Module 4) and
Neo4j (Module 5). Installing a database server by hand is different on every computer and easy to
get subtly wrong, so the course runs both in **Docker**, which gives every learner the same
database on Windows, macOS and Linux.

## What Docker does, in four words

- An **image** is a packaged program with everything it needs: an operating system's files, the
  database, its libraries, at exact versions. `compose.yml` names the two images the course uses.
- A **container** is a running copy of an image, isolated from the rest of your computer. It can
  be stopped, deleted and started again from the same image in seconds.
- A **volume** is where a container keeps data that must outlive it: your tables survive stopping
  and deleting the container, until you delete the volume.
- **Compose** starts several containers from one file (`compose.yml`), with their settings, ports
  and volumes, so one command brings up the whole stack.

Module 13 comes back to images, as a way to pin a pipeline's whole environment.

## 1. Install Docker

Pick the row for your computer. Everything listed is free for learners.

| Your computer | Recommended | Alternative |
|---|---|---|
| Windows 10 or 11 | Docker Engine inside WSL (below) | Docker Desktop |
| macOS (Intel or Apple silicon) | [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) | [Colima](https://github.com/abiosoft/colima) (`brew install colima docker docker-compose`, then `colima start`) |
| Linux | Docker Engine from your distribution or [Docker's own packages](https://docs.docker.com/engine/install/) | |
| A tablet, a locked-down computer, or no install wanted | [GitHub Codespaces](https://docs.github.com/codespaces): open the repository in a codespace, which has Docker already | |

Docker Desktop is free for personal use, education and small businesses; a large company needs a
paid subscription for it, which is one reason this guide prefers Docker Engine on Windows.

### Windows: Docker Engine inside WSL

WSL (Windows Subsystem for Linux) runs a real Ubuntu inside Windows. Docker Engine runs there, as
on any Linux server, and what it serves is reachable from Windows at `localhost`.

1. **Install WSL and Ubuntu.** In PowerShell opened as administrator:
   `wsl --install -d Ubuntu`, then restart Windows. Open "Ubuntu" from the Start menu and choose a
   user name and password when asked (they are for Ubuntu only).
2. **Check that Ubuntu uses systemd** (it starts Docker for you). In the Ubuntu terminal,
   `ps -p 1 -o comm=` should print `systemd`. If it does not, add these two lines to
   `/etc/wsl.conf` (`sudo nano /etc/wsl.conf`), then run `wsl --shutdown` in PowerShell and open
   Ubuntu again:

   ```ini
   [boot]
   systemd=true
   ```

3. **Install Docker Engine and Compose**, start it now and at every start of Ubuntu, and let your
   user run it without `sudo`:

   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose-v2
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER      # takes effect at your next login:
   exit                               # close Ubuntu, then open it again
   ```

4. **Check it works:** `docker run --rm hello-world` prints "Hello from Docker!".

Keep the repository inside Ubuntu (`git clone` it into your Ubuntu home folder, for example
`~/code`): files under `/mnt/c/...` work, but are slower to read from Linux. Windows reaches them
at `\\wsl$\Ubuntu\home\<you>\code`, and VS Code opens them with its WSL extension.

## 2. Start the databases

From the repository's root (in the Ubuntu terminal on Windows):

```bash
docker compose -f shared/docker/compose.yml up -d postgres neo4j
docker compose -f shared/docker/compose.yml ps        # both "Up"; postgres also "(healthy)"
```

The first start downloads the images (about 1 GB in all) and takes a few minutes; later starts take
seconds. Neo4j's browser interface is at <http://localhost:7474> (user `neo4j`, password
`learn-neo4j`).

Then tell the lessons where the databases are (the defaults in `compose.yml`). In the terminal you
run the lessons from:

| | macOS, Linux, WSL (bash, zsh) | Windows (PowerShell) |
|---|---|---|
| PostgreSQL | `export DATABASE_URL=postgresql://learn:learn@localhost:5432/chem` | `$env:DATABASE_URL="postgresql://learn:learn@localhost:5432/chem"` |
| Neo4j | `export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=learn-neo4j` | `$env:NEO4J_URI="bolt://localhost:7687"; $env:NEO4J_USER="neo4j"; $env:NEO4J_PASSWORD="learn-neo4j"` |

Check both from Python (in the series' environment, e.g. `uv run python`):

```python
import psycopg
from neo4j import GraphDatabase

with psycopg.connect("postgresql://learn:learn@localhost:5432/chem") as db:
    print(db.execute("select mol_to_smiles(mol_from_smiles('OC1=CC=CC=C1'))::text").fetchone()[0])
with GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "learn-neo4j")) as driver:
    driver.verify_connectivity()
    print("neo4j: ok")
```

It prints `Oc1ccccc1` (phenol, written by the RDKit cartridge) and `neo4j: ok`.

## 3. Stop them

```bash
docker compose -f shared/docker/compose.yml stop      # stop; start again with "up -d"
docker compose -f shared/docker/compose.yml down      # remove the containers; the data is kept
docker compose -f shared/docker/compose.yml down -v   # remove the containers and delete the data
```

The containers restart on their own whenever Docker starts, until you stop them, so the databases
are there when you come back. The images are pinned to exact versions (`compose.yml`), so every
learner gets the same database. The passwords are for databases on your own computer only: never
reuse them anywhere else.

## When something goes wrong

| What you see | What it means, and what to do |
|---|---|
| `Cannot connect to the Docker daemon` | Docker is not running. WSL or Linux: `sudo systemctl start docker`. Docker Desktop: open it and wait for "Engine running". |
| `permission denied ... docker.sock` | Your user is not in the `docker` group yet: run `sudo usermod -aG docker $USER`, then close the terminal and open it again. |
| `port is already allocated` or `address already in use` | Something else already uses the port, usually a PostgreSQL installed on the computer. Stop it, or change `"5432:5432"` to `"5433:5432"` in `compose.yml` and use port 5433 in `DATABASE_URL`. |
| The containers stop by themselves a minute after you close the terminal (WSL) | WSL shuts Ubuntu down when nothing is using it. Keep an Ubuntu terminal open while you work; the containers start again with Ubuntu. |
| Docker Desktop does not open, or closes at once | Often an update that did not finish. Reinstall it from docker.com, or use the WSL route above instead. Do not run Docker Desktop and Docker Engine in WSL at the same time: both want the same ports. |
| Neo4j logs `Changed password ... only take effect ... first time` | Normal on the first start. If you change `NEO4J_AUTH` later, delete the volume (`down -v`) so the new password is used. |
| PostgreSQL returns values as `b'...'` in Python | psycopg does not know the cartridge's `mol` type: cast to text in SQL (`mol_to_smiles(m)::text`). |

## No Docker?

Lessons that need a database say so at the top, and their code that needs it is marked
`# needs: postgres` or `# needs: neo4j`; the rest of each lesson runs without it.
