---
name: bump
description: Release a new version of holmes or holmes-rs in one step — detect what changed since the last release, write the changelog, pick the semver bump (major/minor/patch), update the version files, and commit. Use when cutting a release. Argument: "holmes" (default) or "holmes-rs".
---

# Bump (release) a new version

One step: figure out the changelog, decide the version bump, update the files, commit.
Replaces the old `bump-holmes`, `bump-holmes-rs`, and `changelog` skills.

## Usage

- `/bump` or `/bump holmes` — release the holmes Python package
- `/bump holmes-rs` — release the holmes-rs Rust extension

## Target reference

|                       | holmes                                            | holmes-rs                                                                                     |
| --------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| source paths          | `src/holmes/` (excluding `src/holmes-rs/`)        | `src/holmes-rs/src/`                                                                          |
| version source        | `pyproject.toml` (root) `version`                 | `src/holmes-rs/Cargo.toml` `version`                                                          |
| version files         | `pyproject.toml` (root) `version`                 | `src/holmes-rs/Cargo.toml`, `src/holmes-rs/pyproject.toml`, root `pyproject.toml` `holmes-rs>=X.Y.Z` dep |
| changelog             | `CHANGELOG.md` (root)                             | `src/holmes-rs/CHANGELOG.md`                                                                  |
| last-release tag      | latest `git tag` matching `^[0-9]+\.[0-9]+\.[0-9]+$` | latest `git tag` matching `^holmes-rs-[0-9]`                                                 |
| extra step            | —                                                 | `cd src/holmes-rs && cargo update --workspace` (refresh `Cargo.lock`)                        |
| commit message        | `Bump holmes to X.Y.Z`                            | `Bump holmes-rs to X.Y.Z`                                                                     |

## Steps

1. **Resolve target** from the argument (default `holmes`).

2. **Detect changes since the last release.**
   - Find the last-release tag for the target (see table). If no tag exists, fall back to the last `Bump <target> to ...` commit.
   - `git diff <last-tag> -- <source paths>` to see everything released since, plus `git diff HEAD -- <source paths>` for uncommitted/staged work.
   - Filter strictly to the target's source paths (for holmes, exclude anything under `src/holmes-rs/`).

3. **Write the changelog.** Categorize changes with [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) headings (Added / Changed / Deprecated / Removed / Fixed / Security) under `[Unreleased]`:
   - Merge with any entries already under `[Unreleased]`; do not duplicate.
   - One concise, user-facing bullet per change; group related changes; describe behavior, not implementation.

4. **Decide the bump** from the full set of `[Unreleased]` changes (state your reasoning and the chosen version in your final message):
   - **holmes (1.x+, standard semver):** breaking change → **major**; new feature, no break → **minor**; only fixes / internal changes → **patch**.
   - **holmes-rs (0.x convention):** breaking change → **minor**; new feature → **minor**; only fixes / internal changes → **patch**. Never auto-jump to 1.0.
   - "Breaking" = removed/renamed public API or behavior that breaks existing callers (usually the Removed / breaking-Changed entries).

5. **Compute the new version** from the version source of truth.

6. **Release the changelog section:** rename `[Unreleased]` → `[X.Y.Z] - YYYY-MM-DD` using today's date.

7. **Update the version file(s)** for the target. For holmes-rs, *edit in place* the single `holmes-rs>=X.Y.Z` line in the root `pyproject.toml` (there must be exactly one — if duplicates exist, collapse to one in alphabetical order).

8. **holmes-rs only:** `cd src/holmes-rs && cargo update --workspace`.

9. **Commit** every changed file (including `Cargo.lock` for holmes-rs) with the target's commit message.

## Notes

- Don't create git tags — an external release process does that. Only commit.
- If detection finds no changes since the last release, stop and say so rather than cutting an empty release.
