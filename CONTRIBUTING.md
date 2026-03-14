# Contributing to usdagent

Thank you for your interest in contributing! This document explains how to get started.

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

## Getting Started

1. **Fork the repo** on GitHub: https://github.com/jordanhubbard/usdagent
2. **Clone your fork**:
   ```bash
   git clone https://github.com/<your-username>/usdagent
   cd usdagent
   ```
3. **Set up a virtualenv**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Run the tests**:
   ```bash
   pytest
   ```
5. **Run linting**:
   ```bash
   ruff check src/ tests/
   ```

## Making Changes

- Create a branch: `git checkout -b feat/my-feature`
- Write code and tests
- Ensure `pytest` passes and `ruff check` is clean
- Commit with a descriptive message
- Open a pull request against `main`

## Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Update `docs/api.md` if you change API behavior
- Reference any related GitHub issues in your PR description

## Issues

Open GitHub Issues for bugs, feature requests, or questions. Use the issue templates when available.

## Architecture

Before making large changes, read [docs/architecture.md](docs/architecture.md) to understand the system design.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 license.
