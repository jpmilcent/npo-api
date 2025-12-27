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

To start the development server:
```bash
uv run fastapi dev src/npo/main.py
```

The API documentation can be found in two variants :
- [Swagger UI](http://127.0.0.1:8000/docs)
- [Redoc](http://127.0.0.1:8000/redoc)

