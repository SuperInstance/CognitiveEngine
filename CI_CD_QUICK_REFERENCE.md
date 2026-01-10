# CI/CD Quick Reference Guide

## Overview
All 6 extracted packages now have comprehensive CI/CD pipelines with automated testing, publishing, and validation.

## Package List
1. hierarchical-memory
2. multi-provider-router
3. character-library
4. local-model-manager
5. character-agent-integration
6. character-skill-trees

## Workflows per Package

### 1. test.yml - Automated Testing
**Triggers:** Push to main/develop, Pull requests, Manual

**What it does:**
- Tests on Python 3.8-3.12 (package-specific)
- Runs on Ubuntu, Windows, macOS
- Linting: black, ruff/flake8
- Type checking: mypy
- Coverage with pytest
- Uploads to Codecov

**Quick test locally:**
```bash
pytest --cov=<package_name> -v
black --check <package_name>/
mypy <package_name>/
```

### 2. publish.yml - PyPI Publishing
**Triggers:** GitHub release, Manual dispatch

**What it does:**
- Builds distribution packages
- Publishes to PyPI (using trusted publishing)
- Creates GitHub release
- Runs smoke tests

**Publish a new version:**
```bash
# Option 1: Tag and push
git tag v1.0.0
git push origin v1.0.0

# Option 2: Create release in GitHub UI
# Go to Releases → Create new release → Tag: v1.0.0
```

### 3. validate.yml - Package Validation
**Triggers:** Push to main/develop, Pull requests, Manual

**What it does:**
- Validates package structure
- Tests installation on multiple platforms
- Validates examples
- Checks dependencies

## Setup Required

### 1. PyPI Trusted Publishing (Recommended)

For each package:

1. Go to https://pypi.org/
2. Create project (if not exists)
3. Go to project settings → Publishing
4. Add new publisher:
   - PyPI Project Name: `package-name`
   - Owner: `your-username`
   - Repository name: `repo-name`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

### 2. Codecov (Optional)

For coverage tracking:

1. Go to https://codecov.io/
2. Sign up with GitHub
3. Add repositories
4. Copy token
5. Add to GitHub: Settings → Secrets → Actions → New secret
   - Name: `CODECOV_TOKEN`
   - Value: `your-token`

### 3. GitHub Environments

For each package:

1. Go to repository settings
2. Environments → New environment
3. Name: `pypi`
4. Add protection rules (optional):
   - Required reviewers
   - Wait timer

## Package-Specific Details

### hierarchical-memory
- **Python:** 3.8-3.11
- **Extras:** embeddings, chromadb, faiss
- **Path:** `/mnt/c/users/casey/hierarchical-memory/.github/workflows/`

### multi-provider-router
- **Python:** 3.10-3.12
- **Extras:** postgres, celery
- **Linter:** ruff
- **Security:** bandit scanning
- **Path:** `/mnt/c/users/casey/multi-provider-router/.github/workflows/`

### character-library
- **Python:** 3.8-3.11
- **Extras:** agent
- **Path:** `/mnt/c/users/casey/character-library/.github/workflows/`

### local-model-manager
- **Python:** 3.10-3.12
- **Special:** GPU detection tests
- **Path:** `/mnt/c/users/casey/local-model-manager/.github/workflows/`

### character-agent-integration
- **Python:** 3.8-3.11
- **Deps:** character-library, hierarchical-memory
- **Path:** `/mnt/c/users/casey/character-agent-integration/.github/workflows/`

### character-skill-trees
- **Python:** 3.8-3.11
- **Extras:** examples (matplotlib)
- **Path:** `/mnt/c/users/casey/character-skill-trees/.github/workflows/`

## Common Commands

### Run Tests Locally
```bash
# Install package
pip install -e ".[dev]"

# Run tests
pytest -v

# Run with coverage
pytest --cov=<package> --cov-report=html

# View coverage
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Code Quality
```bash
# Format code
black <package>/

# Check formatting
black --check <package>/

# Lint with flake8
flake8 <package>/

# Lint with ruff
ruff check <package>/

# Type check
mypy <package>/

# Sort imports
isort <package>/
```

### Build and Check Package
```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Check distribution
twine check dist/*

# Test installation from dist
pip install dist/<package>-<version>.tar.gz
```

### Test Publishing Locally
```bash
# Install to TestPyPI
pip install --index-url https://test.pypi.org/simple/ <package>

# Or build and upload to TestPyPI
python -m build
twine upload --repository testpypi dist/*
```

## Troubleshooting

### Test Failures
- Check Python version compatibility
- Verify all dependencies installed
- Check for platform-specific issues

### Publish Failures
- Verify PyPI trusted publishing configured
- Check tag version format (v1.0.0)
- Ensure environment exists: `pypi`

### Coverage Issues
- Add CODECOV_TOKEN secret
- Check .coverage file is generated
- Verify tests actually run

### Import Errors
- Ensure package installed: `pip install -e .`
- Check PYTHONPATH includes package
- Verify all dependencies installed

## GitHub Actions Status

View workflow runs:
1. Go to repository on GitHub
2. Click "Actions" tab
3. Select workflow from left sidebar
4. View run history and logs

## Branch Protection (Recommended)

1. Go to repository settings
2. Branches → Add rule
3. Branch name pattern: `main`
4. Enable:
   - [ ] Require status checks to pass
   - [ ] Require branches to be up to date
   - Select required checks:
     - Test Suite
     - Validate Package
   - [ ] Require pull request reviews

## Release Process Checklist

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with changes
3. **Run tests** locally: `pytest -v`
4. **Commit changes**: `git commit -am "Release v1.0.0"`
5. **Create tag**: `git tag v1.0.0`
6. **Push tag**: `git push origin v1.0.0`
7. **Create release** on GitHub
8. **Publish workflow** runs automatically
9. **Verify on PyPI**: https://pypi.org/project/<package>/

## Quick Links

- **GitHub Actions**: https://github.com/owner/repo/actions
- **PyPI**: https://pypi.org/project/<package>/
- **Codecov**: https://codecov.io/github/owner/repo
- **Documentation**: See each package's README.md

## Support

For issues with:
- **Workflows**: Check Actions logs
- **Publishing**: Check PyPI settings
- **Tests**: Run locally with verbose flag
- **Coverage**: Check Codecov dashboard

## Summary

✅ 6 packages configured
✅ 18 workflows created (3 per package)
✅ Automated testing on Python 3.8-3.12
✅ Multi-platform support (Linux, macOS, Windows)
✅ Automated PyPI publishing
✅ Coverage tracking
✅ Package validation
✅ Security scanning (where applicable)

**Ready to use!**
