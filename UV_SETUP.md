# UV Package Manager Setup

This project now uses [uv](https://github.com/astral-sh/uv) as its package manager for faster, more reliable dependency management.

## Quick Start

### Installation

Install all dependencies:

```bash
uv sync
```

This will create a virtual environment in `.venv` and install all dependencies specified in `pyproject.toml`.

### Running Python Scripts

Run any Python script using:

```bash
uv run python script.py
```

Or activate the virtual environment:

```bash
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### Platform-Specific PyTorch Installation

By default, the project is configured to use PyTorch CPU builds (suitable for macOS).

**For CUDA support** (Linux/Windows with NVIDIA GPU):

```bash
uv sync --extra-index-url https://download.pytorch.org/whl/cu121
```

**For CPU-only** (already configured by default):

```bash
uv sync
```

## Adding Dependencies

Add a new package:

```bash
uv add package-name
```

Add a development dependency:

```bash
uv add --dev package-name
```

## Updating Dependencies

Update all dependencies:

```bash
uv sync --upgrade
```

Update a specific package:

```bash
uv add package-name --upgrade
```

## Migration from requirements.txt

The dependencies from both `requirements.txt` and `requirements-mac.txt` have been consolidated into `pyproject.toml`. The old requirements files are kept for reference but are no longer used.

## Benefits of UV

- **Faster**: 10-100x faster than pip for dependency resolution and installation
- **Reliable**: Better dependency resolution algorithm
- **Modern**: Uses `pyproject.toml` standard
- **Reproducible**: Generates lock files for exact version control
- **Compatible**: Works seamlessly with existing Python tools

## Troubleshooting

If you encounter issues:

1. Clear the cache and reinstall:
   ```bash
   rm -rf .venv
   uv sync --no-cache
   ```

2. Ensure you're using Python 3.10-3.13:
   ```bash
   uv sync --python 3.10
   ```

3. For package index issues, the project uses `unsafe-best-match` strategy to search across PyPI and PyTorch indexes.
