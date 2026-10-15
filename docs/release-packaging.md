# Integration release packaging

The release payload remains `ha-desloc.zip`, containing only tracked files under `custom_components/desloc/`, plus `SHA256SUMS`. The directory layout matches the existing `v0.3.3b1` and `v0.3.2` assets. Configuration, application data, local captures, credentials, development tools and Git metadata are not part of the ZIP. The build preserves translations and brand images together with the Python integration.

## Version plan and package identity

The committed `version` file and `custom_components/desloc/manifest.json` use the same numeric base version, prepared together before a new release series. The historical `0.3.3b1` development marker was replaced by this numeric-base scheme; the published old prerelease and its assets are preserved. Every new release run reserves a full version and source/policy-bound plan before building. The adapter checks that plan and applies only declared fields.

Using the historical base `0.3.3` as an example, beta 7 would have full tag `v0.3.3-beta.7`, text version `0.3.3-beta.7`, and PEP 440 manifest version `0.3.3b7`; this example does not identify the current release. Nightlies use a PEP 440 development version derived from the frozen run/attempt. Under the explicit `promote-bytes` profile, RC 7 for that base would have tag `v0.3.3-rc.7` but already embed `0.3.3`. Stable can then copy accepted RC bytes without changing the integration or its manifest. The release manifest retains the exact RC origin and source revision.

The source branch and GitHub's automatic source archives keep the numeric base. Candidate metadata is a build overlay, never an automatically committed version bump. Use `prepare-version --dry-run` or `prepare-version --pr` from clean default-branch HEAD to prepare the next base across both owned files. An already prepared, unreleased base is retained; major/minor changes require explicit intent. The dedicated allocation state must not be reset or reused after a failed run.

## HACS compatibility boundary

`hacs.json` is unchanged. Existing HACS installation and rollback continue to fetch the selected source revision. This preserves installation of already published stable releases without adding or mutating their assets. The shared lifecycle has no legacy stable workflow to replace in this repository: existing releases were published separately.

For exact new beta/RC acceptance, install the published `ha-desloc.zip` manually. HACS's source path does not include the frozen build overlay; its installed manifest will report the committed base even when a candidate tag is selected. Do not use that source download as proof that the receipted candidate was exercised. Stable source metadata and stable package metadata agree on the base version, but the publication receipt specifically covers the uploaded asset.

The current HACS implementation obtains repository metadata separately from applying an explicitly requested install version. Switching `zip_release` and introducing a new asset name could therefore require additional compatibility checks for older releases. This change deliberately preserves the established mode. The [HACS integration requirements](https://www.hacs.dev/docs/publish/integration/) and [HACS repository installer](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py) describe the relevant source and asset paths. A future asset-mode migration must validate old-release installation and rollback before changing `hacs.json`.

## Build verification and local reproduction

The release-build workflow downloads the allocator's immutable plan, runs `version_plan.py sync`, builds the ZIP, checks checksums and stages it into `release-assets/package`. `stage_release_assets.py` reads the ZIP's actual manifest version and creates `release-inputs-package.json` covering the exact payload sizes and hashes. The publisher requires that receipt and the declared package metadata. A changed manifest, missing receipt, modified ZIP or incomplete inventory blocks publication.

Reproduce in a disposable checkout of the release manifest's exact source SHA, restoring its `version_plan` object as `.release-plan.json`. The following example uses historical base `0.3.3` and channel `beta`; substitute the actual saved base and channel:

```sh
python3 scripts/version_plan.py sync --plan .release-plan.json
bash scripts/package-release.sh 0.3.3 beta
python3 scripts/stage_release_assets.py --target package --pattern 'release-dist/*'
```

Substitute the actual saved base/channel. Do not invent a local tag, sequence or counter. Without a plan, a base-only development package can be built but cannot be staged as a publishable candidate. The plan, input evidence and build directories are ignored local outputs.

The package contract tests exercise beta, RC and nightly overlays, compare every archived file against its prepared source, extract the ZIP into a disposable Home Assistant configuration layout, and verify the final receipt and package metadata. The existing Python 3.14/Home Assistant test suite, HACS validation, Hassfest and code/dependency checks remain required. Existing validators are callable behind the aggregate gates so candidate builds do not bypass them.

```sh
python3 -m unittest discover -s .github/release-tests
python3 -m unittest discover -s .github/workflow-tests
python3 -m pytest -q
```

The application tests need the existing hash-locked `requirements-dev.txt`. The package contracts do not contact devices or cloud accounts. To refresh generated tooling, change the shared toolkit and run its `install_release.py` for this repository; `--check` detects drift.

## Acceptance and rollback

A maintainer must record the exact RC tag, source SHA, ZIP checksum and tested scope before stable approval. Existing unit tests and package extraction establish only their exercised behavior. They do not establish cloud authentication, account concurrency, discovery, lock/unlock, PIN management, or physical hardware compatibility for a new installation. Follow the existing model-compatibility and operational guidance; do not infer live-lock acceptance from a successful build.

Back up the installed integration directory and Home Assistant configuration before replacing it. Preserve credentials and entity configuration. Install the exact ZIP, restart Home Assistant, and record any limitations. If rollback is needed, restore a previously accepted immutable ZIP and compatible configuration. Do not overwrite a published asset or edit its receipt. Changed source, policy, dependencies or packaging requires a fresh candidate and new acceptance. Stable publication and deployment remain distinct manual operations.
