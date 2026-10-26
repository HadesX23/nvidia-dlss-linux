# Upstream watch

Snapshot: 2026-10-26. Re-check before claiming a package is current.

## Automatic preflight

Every `plan` and `install` calls the update check before building the plan. Results are cached for one hour under `$XDG_CACHE_HOME/nvidia-stack/update-check.json` (fallback `~/.cache`). Only changed rows are printed to stderr, so `--json` output stays clean. Network failure is a warning, never a blocker.

```bash
plan <game> --refresh          # force a new check
plan <game> --no-update-check  # skip it
update-check --refresh         # manual full report
```

Updates are advisory. The helper never silently replaces the neural OptiScaler fork, the leaked NR DLL, or the bundled `dlssg_sm86` 0.2.3.

## Direct sources

| Project | URL | Current | Use |
|---|---|---|---|
| DLSS Swapper | https://github.com/beeradmoore/dlss-swapper/releases | v1.2.7.0 (2026-10-18) | DLL catalog and native refresh |
| NVIDIA Profile Inspector | https://github.com/Orbmu2k/nvidiaProfileInspector/releases | v3.0.2.3 prerelease (2026-10-13) | driver profile overrides |
| DLSS5 Manager | https://github.com/NODIX-TECH/DLSS-5-MANAGER/releases | 1.3.8 (2026-10-22) | OptiScaler + NR + ReShade payloads |
| DLSS5VKLayer | https://github.com/bmitch87/DLSS5VKLayer/releases | 0.3.2-1 (2026-10-26) | Vulkan/Proton NR layer |
| Streamline | https://github.com/NVIDIA-RTX/Streamline/releases | 2.14.16 (2026-10-16) | DLSS-G/Reflex runtime |
| dlssg_for_sm86 | https://github.com/sdli1995/dlssg_for_sm86/releases | 0.4.0 (2026-10-14) | Ampere/Turing DLSS-G; Windows/D3D12, Proton experimental, up to 6x if game supports it |
| RTX40MFG-Unlock | https://github.com/dashdogy/RTX40MFG-Unlock/releases | 1.7.0 (2026-10-25) | RTX 40 only |
| OptiScaler upstream | https://github.com/optiscaler/OptiScaler/releases | v0.9.4 (2026-07-18) | reference; do not replace neural fork |
| DLSS Enabler | https://github.com/artur-graniszewski/DLSS-Enabler/releases | v0.9.4 (2026-07-19) | Combo needs a headless/ASI build; 0.9.4 does not ship `dlss-enabler-headless.dll` |
| DXVK-NVAPI | https://github.com/jp7677/dxvk-nvapi/releases | v0.9.2 (2026-05-12) | NVAPI/NGX bridge |
| ReShade | https://reshade.me | 6.8.0 bundled | addon build |
| RenoDX | https://github.com/clshortfuse/renodx | rolling | DLSS5 addons |

`Nukem9/dlssg_to_fsr3_amd_is_better` no longer resolves as a public release source. Do not cite it as a live download.

## Version traps

- **NPI 3.0.2.3 is a prerelease.** `/releases/latest` may report 3.0.2.1. Check `/releases?per_page=5` and compare the `prerelease` flag.
- **DLSS5 Manager's OptiScaler is a fork.** Upstream v0.9.4 is not a drop-in replacement for the neural 0.7.7 build.
- **Bundled `dlssg_sm86` is 0.2.3 and caps at 4x.** 0.4.0 is a standalone DLSS-G replacement (`version.dll` + `dlssg_sm86/`), not a drop-in OptiScaler plugin. For 6x, use Combo or install 0.4.0 separately with OptiScaler FG disabled. 0.4.0 is Windows/D3D12 and has an open Proton `Missing cuInit` issue; 6x also requires the game's plugin to support it. Do not force 6x in a 4x-only game.
- **Streamline 2.14.16 is newer than the bundled 2.14.1.** Update only when a game or DLSS-G path needs it; keep the old `sl.*` set.
- **ReShade/RenoDX are rolling.** File dates and commit hashes, not release tags, are the version.
- **NPI on Linux is prefix-local.** A newer NPI does not mean newer host driver profiles.

## Update commands

Latest tag:
```bash
curl -fsSL https://api.github.com/repos/<owner>/<repo>/releases/latest \
  | jq -r '.tag_name + " " + .published_at'
```

All recent releases, including prereleases:
```bash
curl -fsSL "https://api.github.com/repos/<owner>/<repo>/releases?per_page=5" \
  | jq -r '.[] | [.tag_name, .prerelease, .published_at] | @tsv'
```

Download one asset:
```bash
gh release download <tag> --repo <owner>/<repo> --pattern '<asset>'
```

Verify a payload:
```bash
cd "mod files/if OptiScaler neural-upstream"
sha256sum -c SHA256SUMS.txt
```

## 6x update procedure

1. Back up the game's `version.dll` (if any), `dlssg_sm86.ini`, and `dlssg_sm86/`.
2. Download `sdli1995/dlssg_for_sm86` 0.4.0.
3. Copy `version.dll`, `dlssg_sm86.ini`, and the whole `dlssg_sm86/` folder beside the rendering EXE. If `version.dll` is occupied, use one of the `alternatives/` proxies.
4. Set `MaxGeneratedFrames=5` in `dlssg_sm86.ini`.
5. Disable OptiScaler FG (`[FrameGen] Enabled=false`) while 0.4.0 owns the DLSS-G path.
6. Test 2x, then 3x, then 4x, then 6x. Roll back on artifacts or crashes.
7. Do not combine with `RTX40MFG-Unlock`, `AdaMfgUnlock`, or another external FG unlocker.

## When not to update

- A game is stable and the current DLL set works.
- The only change is a newer tag with no relevant fix.
- The update replaces the neural OptiScaler fork with upstream.
- You cannot verify the payload hash or keep a rollback copy.
