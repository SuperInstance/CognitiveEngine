# Comprehensive PyPI Publishing Guide

This guide provides step-by-step instructions for publishing all six LucidDreamer packages to PyPI using GitHub Actions with Trusted Publishing.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Package Preparation Checklist](#2-package-preparation-checklist)
3. [GitHub Actions Configuration](#3-github-actions-configuration)
4. [Publishing Steps](#4-publishing-steps)
5. [Verification](#5-verification)
6. [Troubleshooting](#6-troubleshooting)
7. [Package-Specific Publishing Checklists](#7-package-specific-publishing-checklists)

---

## 1. Prerequisites

### 1.1 PyPI Account Setup

1. **Create PyPI Account**
   - Go to https://pypi.org/account/register/
   - Create an account with your email
   - Enable 2-Factor Authentication (required for Trusted Publishing)

2. **Verify Account**
   - Check your email for verification link
   - Complete email verification

3. **Enable 2FA** (Required for Trusted Publishing)
   - Go to Account Settings → Two-factor authentication
   - Set up either TOTP app (recommended) or SMS
   - Generate recovery codes and store them securely

### 1.2 GitHub Repository Setup

Ensure each package has its own GitHub repository:

- `https://github.com/superinstance/hierarchical-memory`
- `https://github.com/superinstance/multi-provider-router`
- `https://github.com/superinstance/character-library`
- `https://github.com/superinstance/local-model-manager`
- `https://github.com/superinstance/character-agent-integration`
- `https://github.com/superinstance/character-skill-trees`

### 1.3 Trusted Publishing Configuration (Recommended)

Trusted Publishing is more secure than API tokens. Configure for each package:

#### Step 1: Create PyPI Trusted Publisher

For each package, go to: https://pypi.org/manage/account/publishing/

Click "Add a new pending publisher" with these settings:

- **PyPI Project Name**: `package-name` (e.g., `hierarchical-memory`)
- **Owner**: `superinstance`
- **Repository name**: `repository-name` (e.g., `hierarchical-memory`)
- **Workflow name**: `publish.yml`
- **Environment name**: `pypi`

Example for hierarchical-memory:
```
PyPI Project Name: hierarchical-memory
Owner: superinstance
Repository name: hierarchical-memory
Workflow name: publish.yml
Environment name: pypi
```

#### Step 2: Verify Trusted Publishing

- After adding, the publisher will be "pending"
- It will be automatically activated on first successful publish
- No API token needed!

---

## 2. Package Preparation Checklist

### 2.1 Verify setup.py/pyproject.toml

#### Check pyproject.toml

For each package, verify `/path/to/package/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "package-name"              # Must match PyPI project name
version = "1.0.0"                   # Current version
description = "Package description"
readme = "README.md"                # Must exist
requires-python = ">=3.7"
license = {text = "MIT"}           # Must match LICENSE file
authors = [
    {name = "SuperInstance", email = "contact@superinstance.ai"}
]
```

#### Verify package names match:

| Package | PyPI Name | Repository Name | pyproject.toml name |
|---------|-----------|-----------------|-------------------|
| 1 | hierarchical-memory | hierarchical-memory | hierarchical-memory |
| 2 | multi-provider-router | multi-provider-router | multi-provider-router |
| 3 | character-library | character-library | character-library |
| 4 | local-model-manager | local-model-manager | local-model-manager |
| 5 | character-agent-integration | character-agent-integration | character-agent-integration |
| 6 | character-skill-trees | character-skill-trees | character-skill-trees |

### 2.2 Run Test Suite

Before publishing, ensure all tests pass:

```bash
cd /mnt/c/users/casey/package-name
python -m pytest tests/ -v --cov=package_name
```

### 2.3 Check Version Numbers

Verify version consistency across files:

```bash
# Check __init__.py version
grep "__version__" package_name/__init__.py

# Check pyproject.toml version
grep "^version = " pyproject.toml

# Check setup.py version (if exists)
grep "version=" setup.py
```

**All three must match!**

### 2.4 Verify README.md

Ensure README.md:
- Exists in package root
- Is in Markdown format
- Contains installation instructions
- Has usage examples
- Includes badges (optional)

### 2.5 Check LICENSE File

Ensure LICENSE file:
- Exists in package root
- Is MIT License (matching pyproject.toml)
- Has correct copyright year
- Has correct copyright holder (SuperInstance)

---

## 3. GitHub Actions Configuration

### 3.1 Verify publish.yml Workflow

Each package should have `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to publish (e.g., v1.0.0)'
        required: true
        type: string

permissions:
  contents: read
  id-token: write  # Required for Trusted Publishing

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check distribution
        run: twine check dist/*

      - name: Store distribution packages
        uses: actions/upload-artifact@v4
        with:
          name: python-package-distributions
          path: dist/

  publish-to-pypi:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/package-name

    steps:
      - name: Download distribution packages
        uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

### 3.2 Alternative: API Token (Not Recommended)

If not using Trusted Publishing, configure PYPI_API_TOKEN:

1. Generate PyPI API Token:
   - Go to https://pypi.org/manage/account/token/
   - Create token with scope for specific package
   - Copy token (only shown once!)

2. Add GitHub Secret:
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Paste token value

3. Update publish.yml to use token:
```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_API_TOKEN }}
```

### 3.3 TestPyPI Configuration

For testing, you can also configure TestPyPI:

1. Create TestPyPI account: https://test.pypi.org/account/register/
2. Create TestPyPI API token
3. Add GitHub secret: `TEST_PYPI_API_TOKEN`
4. The publish.yml already includes TestPyPI support via workflow_dispatch

---

## 4. Publishing Steps

### 4.1 Local Testing Before Publishing

#### Build package locally:

```bash
cd /mnt/c/users/casey/package-name
python -m pip install --upgrade pip build twine
python -m build
twine check dist/*
```

#### Test install from local build:

```bash
pip install dist/package_name-1.0.0-py3-none-any.whl
python -c "import package_name; print(package_name.__version__)"
pip uninstall package_name -y
```

### 4.2 Create Git Tag

```bash
cd /mnt/c/users/casey/package-name
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### 4.3 Push to GitHub

Ensure all changes are pushed:

```bash
git push origin main
```

### 4.4 Create GitHub Release

#### Option A: Via GitHub Web UI
1. Go to repository on GitHub
2. Click "Releases" → "Create a new release"
3. Choose tag: `v1.0.0`
4. Release title: `v1.0.0`
5. Add release notes (copy from CHANGELOG.md)
6. Click "Publish release"

#### Option B: Via GitHub CLI
```bash
gh release create v1.0.0 \
  --title "v1.0.0" \
  --notes "Release version 1.0.0"
```

### 4.5 Verify CI/CD Success

1. Go to repository Actions tab
2. Click on "Publish to PyPI" workflow run
3. Verify all jobs completed successfully:
   - ✓ Build distribution
   - ✓ Publish to PyPI
   - ✓ Smoke test (if release)

### 4.6 Verify PyPI Publication

1. Go to `https://pypi.org/project/package-name/`
2. Verify version appears
3. Check package metadata
4. Verify README renders correctly

---

## 5. Verification

### 5.1 Install from PyPI

```bash
# Create fresh virtual environment
python -m venv /tmp/test_env
source /tmp/test_env/bin/activate  # On Windows: /tmp/test_env/Scripts/activate

# Install from PyPI
pip install package-name==1.0.0

# Verify import
python -c "import package_name; print(package_name.__version__)"
```

### 5.2 Run pip install test

```bash
# Test basic import
python -c "
from package_name import MainClass
print('Package imported successfully!')
print(f'Version: {package_name.__version__}')
"

# Test basic functionality
python -c "
from package_name import MainClass
instance = MainClass()
print('Package initialized successfully!')
"
```

### 5.3 Check on PyPI Website

1. Visit `https://pypi.org/project/package-name/`
2. Verify:
   - Version number
   - Description
   - Author information
   - README renders correctly
   - Download statistics
   - Project links work

### 5.4 Test Installation from TestPyPI (Optional)

If you published to TestPyPI first:

```bash
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  package-name
```

---

## 6. Troubleshooting

### 6.1 Common Errors and Fixes

#### Error: "403 Forbidden" or "Invalid or missing authentication credentials"

**Cause**: Trusted Publishing not configured correctly

**Fix**:
1. Verify Trusted Publisher settings in PyPI
2. Check workflow name matches exactly: `publish.yml`
3. Verify environment name: `pypi`
4. Ensure workflow has `id-token: write` permission

#### Error: "409 Conflict - File already exists"

**Cause**: Version already published

**Fix**:
1. Increment version number in `__init__.py` and `pyproject.toml`
2. Commit changes
3. Create new tag with new version

#### Error: "400 Bad Request - Invalid package metadata"

**Cause**: Invalid `pyproject.toml` or `setup.py`

**Fix**:
1. Run `twine check dist/*` locally
2. Fix reported errors
3. Ensure all required fields are present
4. Verify version consistency

#### Error: README doesn't render on PyPI

**Cause**: README not in correct format or content type

**Fix**:
1. Ensure README.md is valid Markdown
2. In `pyproject.toml`, set: `readme = "README.md"`
3. In `setup.py`, set: `long_description_content_type='text/markdown'`

#### Error: LICENSE not displayed

**Cause**: License not properly specified

**Fix**:
1. Ensure LICENSE file exists in root
2. In `pyproject.toml`, set: `license = {text = "MIT"}`
3. Verify classifiers include: `"License :: OSI Approved :: MIT License"`

#### Error: "Package not found on PyPI" after publishing

**Cause**: PyPI indexing delay (usually 1-5 minutes)

**Fix**:
1. Wait 5-10 minutes
2. Clear pip cache: `pip cache purge`
3. Try again

### 6.2 Rollback Procedure

If you need to yank (remove) a published version:

1. **Yank version from PyPI**:
   - Go to `https://pypi.org/manage/project/package-name/releases/`
   - Find the version
   - Click "Yank"
   - Provide reason

2. **Delete GitHub release**:
   ```bash
   gh release delete v1.0.0 -y
   ```

3. **Delete git tag** (if needed):
   ```bash
   git tag -d v1.0.0
   git push origin :refs/tags/v1.0.0
   ```

4. **Fix issue and republish**:
   - Fix the issue
   - Bump version to new version
   - Follow publishing steps again

**Note**: You cannot completely delete a version from PyPI, only yank it. Yanked versions can still be installed explicitly but won't be installed by default.

### 6.3 Version Bumping Process

Use Semantic Versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

#### Bump version in all files:

```bash
# Edit __init__.py
sed -i 's/__version__ = "1.0.0"/__version__ = "1.0.1"/' package_name/__init__.py

# Edit pyproject.toml
sed -i 's/version = "1.0.0"/version = "1.0.1"/' pyproject.toml

# Edit setup.py (if exists)
sed -i 's/version=get_version()/version="1.0.1"/' setup.py
```

Or use a version bumping tool:
```bash
pip install bump2version
bump2version patch  # or minor, or major
```

### 6.4 Testing Checklist

Before publishing:
- [ ] All tests pass locally
- [ ] Package builds successfully: `python -m build`
- [ ] Twine check passes: `twine check dist/*`
- [ ] Can install from local build
- [ ] Can import package
- [ ] Basic functionality works
- [ ] README displays correctly
- [ ] LICENSE is correct
- [ ] Version numbers match across all files
- [ ] Git tag is created
- [ ] GitHub release is created

After publishing:
- [ ] GitHub Actions workflow succeeds
- [ ] Package appears on PyPI
- [ ] Can install from PyPI
- [ ] Can import installed package
- [ ] README renders on PyPI
- [ ] All links work on PyPI
- [ ] Download statistics show installs

---

## 7. Package-Specific Publishing Checklists

### Package 1: hierarchical-memory

**Repository**: `/mnt/c/users/casey/hierarchical-memory`
**PyPI Name**: `hierarchical-memory`
**GitHub**: `https://github.com/superinstance/hierarchical-memory`

#### Pre-Publish Checklist:
- [ ] Version in `hierarchical_memory/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `hierarchical-memory`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/hierarchical-memory
git tag -a v1.0.0 -m "Release hierarchical-memory v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install hierarchical-memory==1.0.0
python -c "import hierarchical_memory; print(hierarchical_memory.__version__)"
```

#### PyPI URL: https://pypi.org/project/hierarchical-memory/

---

### Package 2: multi-provider-router

**Repository**: `/mnt/c/users/casey/multi-provider-router`
**PyPI Name**: `multi-provider-router`
**GitHub**: `https://github.com/superinstance/multi-provider-router`

#### Pre-Publish Checklist:
- [ ] Version in `multi_provider_router/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `multi-provider-router`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/multi-provider-router
git tag -a v1.0.0 -m "Release multi-provider-router v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install multi-provider-router==1.0.0
python -c "import multi_provider_router; print(multi_provider_router.__version__)"
```

#### PyPI URL: https://pypi.org/project/multi-provider-router/

---

### Package 3: character-library

**Repository**: `/mnt/c/users/casey/character-library`
**PyPI Name**: `character-library`
**GitHub**: `https://github.com/superinstance/character-library`

#### Pre-Publish Checklist:
- [ ] Version in `character_library/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `character-library`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/character-library
git tag -a v1.0.0 -m "Release character-library v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install character-library==1.0.0
python -c "import character_library; print(character_library.__version__)"
```

#### PyPI URL: https://pypi.org/project/character-library/

---

### Package 4: local-model-manager

**Repository**: `/mnt/c/users/casey/local-model-manager`
**PyPI Name**: `local-model-manager`
**GitHub**: `https://github.com/superinstance/local-model-manager`

#### Pre-Publish Checklist:
- [ ] Version in `local_model_manager/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `local-model-manager`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/local-model-manager
git tag -a v1.0.0 -m "Release local-model-manager v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install local-model-manager==1.0.0
python -c "import local_model_manager; print(local_model_manager.__version__)"
```

#### PyPI URL: https://pypi.org/project/local-model-manager/

---

### Package 5: character-agent-integration

**Repository**: `/mnt/c/users/casey/character-agent-integration`
**PyPI Name**: `character-agent-integration`
**GitHub**: `https://github.com/superinstance/character-agent-integration`

#### Pre-Publish Checklist:
- [ ] Version in `character_agent_integration/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `character-agent-integration`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/character-agent-integration
git tag -a v1.0.0 -m "Release character-agent-integration v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install character-agent-integration==1.0.0
python -c "import character_agent_integration; print(character_agent_integration.__version__)"
```

#### PyPI URL: https://pypi.org/project/character-agent-integration/

---

### Package 6: character-skill-trees

**Repository**: `/mnt/c/users/casey/character-skill-trees`
**PyPI Name**: `character-skill-trees`
**GitHub**: `https://github.com/superinstance/character-skill-trees`

#### Pre-Publish Checklist:
- [ ] Version in `character_skill_trees/__init__.py`: `__version__ = "1.0.0"`
- [ ] Version in `pyproject.toml`: `version = "1.0.0"`
- [ ] README.md exists and is complete
- [ ] LICENSE is MIT with copyright SuperInstance
- [ ] Tests pass: `pytest tests/`
- [ ] Build succeeds: `python -m build`
- [ ] Trusted Publishing configured on PyPI for `character-skill-trees`

#### Publish Commands:
```bash
cd /mnt/c/users/casey/character-skill-trees
git tag -a v1.0.0 -m "Release character-skill-trees v1.0.0"
git push origin main
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes "Release version 1.0.0"
```

#### Verify:
```bash
pip install character-skill-trees==1.0.0
python -c "import character_skill_trees; print(character_skill_trees.__version__)"
```

#### PyPI URL: https://pypi.org/project/character-skill-trees/

---

## Quick Reference: All-In-One Publish Script

Save this as `publish_all.sh` and run from `/mnt/c/users/casey/`:

```bash
#!/bin/bash

PACKAGES=(
    "hierarchical-memory"
    "multi-provider-router"
    "character-library"
    "local-model-manager"
    "character-agent-integration"
    "character-skill-trees"
)

VERSION="1.0.0"

for package in "${PACKAGES[@]}"; do
    echo "========================================"
    echo "Publishing $package v$VERSION"
    echo "========================================"

    cd "/mnt/c/users/casey/$package" || exit 1

    # Run tests
    echo "Running tests..."
    python -m pytest tests/ -v || exit 1

    # Build package
    echo "Building package..."
    python -m build || exit 1

    # Check distribution
    echo "Checking distribution..."
    twine check dist/* || exit 1

    # Create and push tag
    echo "Creating git tag..."
    git tag -a "v$VERSION" -m "Release $package v$VERSION" || exit 1
    git push origin main || exit 1
    git push origin "v$VERSION" || exit 1

    # Create GitHub release
    echo "Creating GitHub release..."
    gh release create "v$VERSION" --title "v$VERSION" --notes "Release version $VERSION" || exit 1

    echo "✓ $package v$VERSION published successfully!"
    echo ""
done

echo "========================================"
echo "All packages published!"
echo "========================================"
```

Make executable:
```bash
chmod +x publish_all.sh
./publish_all.sh
```

---

## Additional Resources

- PyPI Documentation: https://packaging.python.org/tutorials/packaging-projects/
- Trusted Publishing: https://docs.pypi.org/trusted-publishers/
- GitHub Actions for PyPI: https://github.com/pypa/gh-action-pypi-publish
- Semantic Versioning: https://semver.org/
- Twine Documentation: https://twine.readthedocs.io/

---

## Best Practices

1. **Always test locally first** - Build and test install before pushing
2. **Use Trusted Publishing** - More secure than API tokens
3. **Test on TestPyPI first** - Catch issues before production
4. **Use Semantic Versioning** - Clear version communication
5. **Maintain CHANGELOG** - Document changes for users
6. **Tag releases properly** - Use `v` prefix: `v1.0.0`
7. **Verify after publishing** - Always test install from PyPI
8. **Keep READMEs updated** - They display on PyPI
9. **Use dependencies wisely** - Minimize and pin versions
10. **Monitor PyPI statistics** - Track downloads and usage

---

## Support

For issues or questions:
- PyPI Support: https://pypi.org/help/
- GitHub Issues: https://github.com/superinstance/[package-name]/issues
- Python Packaging Guide: https://packaging.python.org/

---

**Last Updated**: 2025-01-09
**Maintainer**: SuperInstance
**License**: MIT
