# Tool versions are pinned to the ones the lint workflow uses, so that a local
# `just lint` and CI cannot disagree. Keep them in sync with .github/workflows/lint.yml.
ruff_version := "0.16.1"
clang_format_version := "22.1.8"

# Default recipe: list all available recipes
default:
    @just --list

# Install the package with test and lint dependencies
install:
    uv sync --extra test --extra lint --extra arrow

# Rebuild the extension and reinstall it
build:
    uv sync --extra test --extra lint --extra arrow --reinstall-package protosaurus

# Build source distribution
sdist:
    uv build --sdist

# Build wheel
wheel:
    uv build --wheel

# Build both sdist and wheel
dist:
    uv build

# Run all tests
test:
    uv run pytest

# Run tests with verbose output
test-verbose:
    uv run pytest -v

# Run a specific test file
test-file file:
    uv run pytest {{ file }} -v

# Run tests matching a keyword expression
test-k expr:
    uv run pytest -k "{{ expr }}" -v

# Lint Python: style and import sorting, as in CI
lint:
    uvx ruff@{{ ruff_version }} check .
    uvx ruff@{{ ruff_version }} check --select I --diff .

# Check C++ formatting, as in CI
format-check:
    git ls-files -z '*.cpp' '*.h' \
      | xargs -0 uvx clang-format@{{ clang_format_version }} --dry-run --Werror

# Reformat C++ sources in place
format:
    git ls-files -z '*.cpp' '*.h' \
      | xargs -0 uvx clang-format@{{ clang_format_version }} -i

# Type check
types:
    uv run ty check src/

# Verify the vendored stub still matches the generated one
stub:
    #!/usr/bin/env bash
    # The lint workflow enforces this, so a drift here fails CI.
    set -euo pipefail
    generated="$(uv run python -c 'import protosaurus.protosaurus_ext as e, pathlib; print(pathlib.Path(e.__file__).parent)')/protosaurus_ext.pyi"
    diff -u "$generated" src/protosaurus/protosaurus_ext.pyi

# Copy the generated stub over the vendored one, after changing the bindings
stub-update:
    #!/usr/bin/env bash
    set -euo pipefail
    generated="$(uv run python -c 'import protosaurus.protosaurus_ext as e, pathlib; print(pathlib.Path(e.__file__).parent)')/protosaurus_ext.pyi"
    cp "$generated" src/protosaurus/protosaurus_ext.pyi

# Everything CI checks, in one go
check: lint format-check types stub test

# Clean build artifacts
clean:
    rm -rf build dist wheelhouse *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.so" -path "*/protosaurus/*" -exec rm -f {} + 2>/dev/null || true

# Build wheels via cibuildwheel (local). Needs a python.org framework Python on macOS.
cibw:
    uvx cibuildwheel --output-dir wheelhouse

# Show project info. The version comes from the git tag via setuptools_scm.
info:
    @echo "Project: protosaurus"
    @uv run python -c "import importlib.metadata as m; print('Version:', m.version('protosaurus'))"
    @echo "Tag: $(git describe --tags --always)"
