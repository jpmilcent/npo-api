# nature-photo-organizer API


## Development

We use :
- [uv](https://docs.astral.sh/uv/) to manage the project
- [Ruff](https://docs.astral.sh/ruff/) to lint and format code
- [Fastapi](https://fastapi.tiangolo.com/learn/) as microframework to build this REST API

### Installation and Usage

Check that you have Exiftool install on your system :

```bash
exiftool --version
# If necessary install it:
sudo apt install libimage-exiftool-perl
```

Clone the project into your local workspace:

```bash
git clone git@github.com:jpmilcent/npo-api.git
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). You can use:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Check your installed version: `uv -V`

Navigate to the cloned project folder:

```bash
cd npo-api/
```

Install the project with uv:

```bash
uv sync --locked --all-extras --dev
```

Create your config file:

```bash
cp .env.sample .env
# Edit the .env file and adapt the settings to your system
```

To start the development server:
```bash
uv run fastapi dev src/npo/main.py
```

The API documentation can be found in two variants :
- [Swagger UI](http://127.0.0.1:8000/docs)
- [Redoc](http://127.0.0.1:8000/redoc)

### Postgresql database

By default, we use SQLite, but you can use PostgreSQL. You will need to add a new user and create a new database. Here are the steps to follow:

Connect to Psql terminal with a superadmin user:

```bash
sudo -u postgres psql
```

In Psql terminal, create a new user (`<user-name>`) with password (`<user-password>`) and a new database (`<new-database-name>`):

```sql
CREATE USER <user-name> WITH ENCRYPTED PASSWORD '<user-password>';
CREATE DATABASE <new-database-name> WITH TEMPLATE template1 OWNER <user-name>;
GRANT ALL PRIVILEGES ON DATABASE <new-database-name> TO <user-name> ;
```

The database content is installed by default when FastAPI app is launch if it doesn't exist. The same applies to the migrations. But you need to change the environment variable or `.env` file parameter `NPO_DATABASE_URI` with this:

```properties
NPO_DATABASE_URI="postgresql+asyncpg://<user-name>:<user-password>@localhost:5432/<new-database-name>"
```

### Tests

By default all tests use an SQLite database in memory. But you can use a PostgreSQL database.
For that, you need to create a file `.env.test` base on `.env.test.sample` and edit the
parameter `TEST_DATABASE_URL`.

You can also use the SQLAlchemy models files to create the database content or the Alembic migrations with the parameter `USE_ALEMBIC_MIGRATIONS` avec la valeur `True`.
