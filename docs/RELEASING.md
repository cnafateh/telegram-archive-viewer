# Releasing

The repository includes a GitHub Actions release workflow.

## Versioning

Use semantic version tags:

```text
v1.0.0
v1.1.0
v1.1.1
```

## Release process

1. Make sure `main` is green in CI.
2. Update `CHANGELOG.md`.
3. Commit the changelog.
4. Create and push a version tag.

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow in `.github/workflows/release.yml` publishes a generic image to GHCR and creates a GitHub Release.

## GHCR package visibility

The workflow uses the repository `GITHUB_TOKEN`; no personal access token is required for publishing from the same repository.

After the first package is published, verify the package visibility and access settings in GitHub. If you want the container image to be publicly pullable, make the package public.

## Important privacy rule

The release image is built with the normal `Dockerfile`, not `Dockerfile.private`.

Never modify the release workflow to publish `Dockerfile.private`, because that Dockerfile is explicitly intended to bake a local Telegram archive into an image.
