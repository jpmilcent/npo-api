# nature-photo-organizer API


## Development

We use:
- [uv](https://docs.astral.sh/uv/) to manage the project
- [Ruff](https://docs.astral.sh/ruff/) to lint and format code
- [Fastapi](https://fastapi.tiangolo.com/learn/) as microframework to build this REST API

### Installation and Usage

Check that you have Exiftool installed on your system:

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

All large files (> 10MB) used by tests are stored in the `v0.0.1-alpha` release on the GitHub repository.
The first time, a fixture automatically downloads these files (mostly RAW and DNG files) in the `test/data/` directory.

To update the coverage report use: `uv run pytest --cov --cov-report=html`
To view the report in your browser, open the _index.html_ file in the `htmlcov` directory.

By default, pytest shows durations for the 5 longest tests. Use `uv run pytest --durations=0` to show all test durations.

### Update version

To force update of file `version.py` use: `uv run -m setuptools_scm --force-write-version-files`

### Internationalization

We use `pybabel` to manage translations.

To extract messages from source code to the template file (`.pot`):
```bash
uv run pybabel extract -F babel.cfg -o src/npo/locales/messages.pot .
```

To update the catalog files (`.po`) from the template file (`.pot`):
```bash
uv run pybabel update -i src/npo/locales/messages.pot -d src/npo/locales
```

To compile catalog files (`.po`) to binary (`.mo`) files:
```bash
uv run pybabel compile -d src/npo/locales
```

To add a new language (e.g. es):
```bash
uv run pybabel init -i src/npo/locales/messages.pot -d src/npo/locales -l es
```
