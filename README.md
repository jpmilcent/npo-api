# 🌿 nature-photo-organizer API

⚠️ **This project is currently a sandbox**

## 🛠️ Development

**Note**: Operational guidance for AI agents and contributor workflows is in [.github/copilot-instructions.md](.github/copilot-instructions.md).

We use:
- [uv](https://docs.astral.sh/uv/) to manage the project
- [Ruff](https://docs.astral.sh/ruff/) to lint and format code
- [Fastapi](https://fastapi.tiangolo.com/learn/) as microframework to build this REST API
- [![Pyright Badge](https://img.shields.io/badge/Pyright-basic-296896?logo=microsoft&logoColor=fff&style=plastic)](https://github.com/microsoft/pyright) for static type checking
- [![pip-audit Badge](https://img.shields.io/badge/pip--audit-3775A9?logo=pypi&logoColor=fff&style=plastic)](https://pypi.org/project/pip-audit/) to audit dependencies for known vulnerabilities
- [![pre-commit Badge](https://img.shields.io/badge/pre--commit-FAB040?logo=precommit&logoColor=fff&style=plastic)](https://github.com/pre-commit/pre-commit) with [Gitleaks](https://github.com/gitleaks/gitleaks), [Gitlint](https://github.com/jorisroovers/gitlint/wiki/Pre-commit-notes) and [Ruff](https://github.com/astral-sh/ruff-pre-commit) to check Git commit content and [![Conventional Commits Badge](https://img.shields.io/badge/Conventional%20Commits-FE5196?logo=conventionalcommits&logoColor=fff&style=plastic)](https://www.conventionalcommits.org/en/v1.0.0/) message
- [![SemVer Badge](https://img.shields.io/badge/SemVer-3F4551?logo=semver&logoColor=fff&style=plastic)](https://semver.org/) Semantic Versioning for Git tags and releases

### 🚀 Installation and Usage

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

### 🐘 Postgresql database

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

### 🛡️ Pre-commit (Git hooks) installation

Install this tools :
- [Pipx](https://github.com/pypa/pipx?tab=readme-ov-file#on-linux)
- [Pre-commit](https://pre-commit.com/index.html#install)
- [Gitleaks](https://github.com/gitleaks/gitleaks?tab=readme-ov-file#installing)
- [Gitlint](https://jorisroovers.com/gitlint/latest/installation/)
- [Ruff](https://github.com/astral-sh/ruff?tab=readme-ov-file#installation)
- [BasedPyright](https://docs.basedpyright.com/v1.31.1/installation/pre-commit%20hook/)
- [Pip-audit](https://pypi.org/project/pip-audit/)

Installation steps for *Debian 13*:
```bash
# Debian packages
sudo apt update
sudo apt install pipx golang
# Enable pipx
pipx ensurepath
# Install Python packages with Pipx
pipx install pre-commit gitlint ruff
# Creation of necessary local directories
mkdir ~/Applications ~/bin
# Install gitleaks
cd Applications
git clone https://github.com/gitleaks/gitleaks.git
cd gitleaks
make build
cd ~/bin
ln -s ~/Applications/gitleaks/gitleaks gitleaks
source ~/.bashrc
# Check install
gitleaks --version
gitlint --version
ruff --version
# Install Pre-commit in your repository (Ex.: ~/workspace/npo-api)
cd ~/workspace/npo-api
pre-commit install
```

After this installation, the 3 tools will be launch at each commit.


#### Gitleaks, Gitlint, Ruff, BasedPyright and Pip-audit manual usage

They can also be used manually to check the project.

To launch them manually from the root directory of this project, use:
```bash
gitleaks git .
gitlint --commits HEAD
# Check only Python files
ruff check .
# Fix issues automatically
ruff check . --fix
# Check type checking with BasedPyright
uv run basedpyright
# Or for a specific file
uv run basedpyright src/npo/main.py
# Security audit of dependencies
uv run pip-audit .
```

### 🧪 Tests

By default all tests use an SQLite database in memory. But you can use a PostgreSQL database.
For that, you need to create a file `.env.test` base on `.env.test.sample` and edit the
parameter `TEST_DATABASE_URL`.

You can also use the SQLAlchemy models files to create the database content or the Alembic migrations with the parameter `USE_ALEMBIC_MIGRATIONS` avec la valeur `True`.

All large files (> 10MB) used by tests are stored in the `v0.0.1-alpha` release on the GitHub repository.
The first time, a fixture automatically downloads these files (mostly RAW and DNG files) in the `test/data/` directory.

By default, pytest shows durations for the 5 longest tests. Use `uv run pytest --durations=0` to show all test durations.

#### 📊 Tests coverage

To update the coverage report use: `uv run pytest --cov --cov-report=html`
To view the report in your browser, open the _index.html_ file in the `htmlcov` directory.

### 🆙 Update version

To force update of file `version.py` use: `uv run -m setuptools_scm --force-write-version-files`

### 🌐 Internationalization

We use `pybabel` to manage translations.

To extract messages from source code to the template file (`.pot`):
```bash
uv run pybabel extract -F babel.cfg -o src/npo/locales/messages.pot .
```

To update the catalog files (`.po`) from the template file (`.pot`):
```bash
uv run pybabel update -i src/npo/locales/messages.pot -d src/npo/locales
```
At this step, you must translate the strings inside `.po` files.

To compile catalog files (`.po`) to binary (`.mo`) files:
```bash
uv run pybabel compile -d src/npo/locales
```

To add a new language (e.g. es):
```bash
uv run pybabel init -i src/npo/locales/messages.pot -d src/npo/locales -l es
```
