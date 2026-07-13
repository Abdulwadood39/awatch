# Publishing to PyPI

PyPI package name: **`monitorit`**  
Import: `from monitorit import awatch`

## One-time setup (you already did Trusted Publishing)

1. PyPI → Account settings → **Publishing** → trusted publisher for:
   - Owner: `Abdulwadood39`
   - Repository: `awatch`
   - Workflow: `publish.yml`
   - Environment: `pypi`
2. GitHub repo → **Settings → Environments → New environment** named exactly `pypi`
   - Optional: add a required reviewer for safer releases

## Each release

1. Bump version in **both**:
   - `pyproject.toml` → `version = "..."`
   - `src/monitorit/__init__.py` → `__version__`
   - `src/monitorit/awatch/__init__.py` → `__version__` (keep in sync)
2. Update `CHANGELOG.md`
3. Commit on `main`, then tag and push:

```bash
git add -A
git commit -m "Release 0.1.0"
git tag -a v0.1.0 -m "v0.1.0"
git push origin main --tags
```

4. GitHub Actions runs **Publish** → uploads to https://pypi.org/project/monitorit/
5. Verify:

```bash
pip install monitorit==0.1.0
python -c "from monitorit import awatch; print(awatch.__version__)"
```

PyPI never reuses a version — fixes need a new bump (e.g. `0.1.1`).
