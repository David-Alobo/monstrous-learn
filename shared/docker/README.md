# The courses' databases, in Docker

Some lessons need a database server: PostgreSQL with the RDKit cartridge (Series 1, Module 4) and
Neo4j (Module 5). Both run in Docker, the same on every computer.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) or
   Docker Engine (Linux), and start it.
2. From the repository's root: `docker compose -f shared/docker/compose.yml up -d postgres neo4j`
3. Tell the lessons where the databases are (the defaults in `compose.yml`):

   | | macOS, Linux (bash, zsh) | Windows (PowerShell) |
   |---|---|---|
   | PostgreSQL | `export DATABASE_URL=postgresql://learn:learn@localhost:5432/chem` | `$env:DATABASE_URL="postgresql://learn:learn@localhost:5432/chem"` |
   | Neo4j | `export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=learn-neo4j` | `$env:NEO4J_URI="bolt://localhost:7687"; $env:NEO4J_USER="neo4j"; $env:NEO4J_PASSWORD="learn-neo4j"` |

4. Stop them with `docker compose -f shared/docker/compose.yml down` (add `-v` to delete the data).

The images are pinned to exact versions (`compose.yml`), so every learner gets the same database.
The passwords are for databases on your own computer only.

No Docker? Lessons that need a database say so at the top, and their code that needs it is marked
`# needs: postgres` or `# needs: neo4j`; the rest of each lesson runs without it.
