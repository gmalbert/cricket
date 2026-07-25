# Fixing GitHub Actions Node.js Deprecation Warnings

## Problem

GitHub Actions workflows produce deprecation warnings like:

> Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced
> to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5, ...

This happens because older major versions of GitHub's official actions are built on
Node.js 16 or Node.js 20, which GitHub has been phasing out in favor of Node.js 24.

## Technique

**Upgrade every official action to its latest major version that targets Node.js 24.**

The pattern is simple: for each `uses:` line in your workflow YAML files, bump to the
current latest. The most common actions and their Node.js 24 versions (as of July 2026):

| Action | Deprecated Version | Node.js 24 Version |
|---|---|---|
| `actions/checkout` | `@v4` (Node 20) | `@v7` |
| `actions/setup-python` | `@v5` (Node 20) | `@v7` |
| `actions/cache` | `@v4` (Node 20) | `@v5` |
| `actions/upload-artifact` | `@v4` (Node 20) | `@v7` |
| `codecov/codecov-action` | `@v4` (Node 20) | `@v7` |
| `actions/setup-node` | `@v4` (Node 20) | `@v7` |

### How to find the latest version

1. Go to `https://github.com/<owner>/<action>/releases`
2. Check the latest tag — if it says "runs on Node.js 24", that's your target
3. Look at the Marketplace page (`https://github.com/marketplace/actions/<action>`)
   for the "Latest" badge

### What to upgrade

Every `uses:` reference in `.github/workflows/*.yml` files:

```bash
# Quick audit — list all action references and their current versions
rg 'uses:\s+' .github/workflows/ --no-filename | sort -u
```

### Example diff

```diff
- uses: actions/checkout@v4
+ uses: actions/checkout@v7

- uses: actions/setup-python@v5
+ uses: actions/setup-python@v7

- uses: actions/cache@v4
+ uses: actions/cache@v5

- uses: actions/upload-artifact@v4
+ uses: actions/upload-artifact@v7

- uses: codecov/codecov-action@v4
+ uses: codecov/codecov-action@v7
```

### Breaking change risk

- **GitHub-hosted runners** (`ubuntu-latest`, `macos-latest`, `windows-latest`) —
  no risk, they already run Runner v2.327.1+ which supports Node.js 24 actions.
- **Self-hosted runners** — ensure Runner version >= 2.327.1 before upgrading.
  Verify with: `./run.sh --version` on the runner machine.

### Verify the fix

After pushing, look at the workflow run's Annotations tab. Zero deprecation
warnings means the upgrade worked. A successful run with the old annotation count
(e.g., "5 warnings") now showing zero confirms it.

## Why this works

GitHub Actions uses a JavaScript runtime to execute actions. When an action's
`action.yml` declares `runs.using: node20` but the runner only has Node.js 24,
GitHub auto-upgrades it with a warning. Upgrading to versions that declare
`runs.using: node24` eliminates the warning entirely because the action's
requested runtime matches what the runner provides.
