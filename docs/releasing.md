# Releasing Orcheo Packages

This repository now publishes three Python distributions independently:

- `orcheo` – core orchestration engine (`core-v*` tags)
- `orcheo-sdk` – Python SDK helpers (`sdk-v*` tags)
- `orcheo-backend` – deployable FastAPI wrapper (`backend-v*` tags)

The `build-and-release` job inside `.github/workflows/ci.yml` builds and uploads the
correct package whenever a matching tag is pushed. Follow the steps below to prepare
and cut a release.

## Prerequisites
- `uv` installed locally, matching the version used in CI.
- Ability to push tags to the repository.
- PyPI trusted publishing configured for the repository (already set up in CI).

## Shared Release Checklist
1. **Update version**: Edit the target package's `pyproject.toml` and bump the `version`
   field. Keep versions independent across the three packages. You can automate the
   edit with `bump2version` using the package-specific configuration files:

   ```bash
   # examples
   bump2version patch           # core package; produces tag core-vX.Y.Z
   (cd apps/backend && bump2version minor)   # tag backend-vX.Y.Z
   (cd packages/sdk && bump2version patch)   # tag sdk-vX.Y.Z
   ```

   Each config now commits and creates the tag with the correct prefix; remove
   `commit`/`tag`/`tag_name` options if you prefer to handle those manually.
2. **Update changelog/docs**: Capture the changes since the last release.
3. **Sync dependencies**: Run `uv sync --all-groups` if dependencies changed so the
   lockfile stays up to date.
4. **Verify quality gates**:
   ```bash
   uv run make lint
   uv run make test
   uv build --package <package-name>
   ```
5. **Commit** the changes and open a pull request. Merge once CI is green.
6. **Tag the release** from the merged commit using the naming convention in the table
   below, then push the tag.

| Package          | Tag pattern  |
| ---------------- | ------------ |
| `orcheo`         | `core-vX.Y.Z`|
| `orcheo-backend` | `backend-vX.Y.Z` |
| `orcheo-sdk`     | `sdk-vX.Y.Z` |

CI automatically runs the lint, coverage, and Postgres checks, then executes the
`build-and-release` job to publish the tagged package to PyPI. No manual uploads are
necessary.

## Package-specific Notes
### orcheo (core)
1. Run `bump2version <part>` from the repository root (for example `bump2version patch`).
2. If new public APIs were added, update `README.md` and relevant docs.
3. Push the release commit and tag: `git push origin HEAD && git push origin core-vX.Y.Z`.

### orcheo-backend
1. Ensure `apps/backend/pyproject.toml` references the desired `orcheo` version in
   its dependencies.
2. Run `(cd apps/backend && bump2version <part>)` to update the version.
3. Push the release commit and tag: `git push origin HEAD && git push origin backend-vX.Y.Z`.

### orcheo-sdk
1. Run `(cd packages/sdk && bump2version <part>)` to update the version.
2. Update SDK documentation or examples if interfaces changed.
3. Push the release commit and tag: `git push origin HEAD && git push origin sdk-vX.Y.Z`.

## Post-release Follow-up
- Announce the release, update sample code, and communicate dependency expectations
  (e.g., minimum `orcheo` version required by `orcheo-backend`).
- Remove local `dist/` directories if you performed a manual build.
