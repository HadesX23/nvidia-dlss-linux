---
name: nvidia-dlss-linux
description: "Trigger: DLSS, DLSS 5, Neural Rendering, Ray Tracing, Path Tracing, Frame Generation, DLAA, Reflex, OptiScaler, RTX 3060 Ti, CachyOS, Proton, portable. Add and tune NVIDIA game tech on Linux."
license: Apache-2.0
metadata:
  author: "nvidia-dlss-linux contributors"
  version: "1.0"
---

## Activation Contract

Use for a single-player game on CachyOS/Omarchy that needs DLSS Super Resolution, DLAA, Ray Reconstruction, Reflex, Frame Generation (including modded x6), or DLSS 5 Neural Rendering under Steam Proton, Wine, UMU, or native Vulkan. Steam: `scan` then `plan <appid>`; the helper finds the library and `compatdata/<appid>/pfx`. Pre-installed portable Windows builds use a folder or `.exe` plus `--prefix`. Preflight runs on plan/install (1 h cache; `--refresh` forces). Target: RTX 3060 Ti 8 GB.

Do not use on anti-cheat multiplayer, macOS, or to promise path tracing where the engine lacks it.

## Hard Rules

- Single-player only. Stop on EAC, BattlEye, kernel anti-cheat, or OnlineFix.
- Steam uses Proton; helper finds `compatdata/<appid>/pfx`. Do not use bare Wine. `--prefix` is for portable/custom only.
- Portable builds are untrusted; never download cracks or bypass DRM; use a dedicated prefix and existing files.
- Inspect API, exe, prefix, and existing mods. Back up every file and write a rollback manifest before copying.
- Run the upstream preflight on every game. Warn on updates; never silently replace the neural OptiScaler fork or leaked NR DLL.
- Path tracing is native-only or RTX Remix. DLSS 5 NR is post-processing, not PT.
- RTX 3060 Ti: native SR/RR/DLAA/Reflex and NR are usable; native FG/MFG is not. Label x6 as modded (SM86 kernels, FSR FG Combo, or Live Flow).
- 6x only if the game's DLSS-G plugin supports it; 0.4.0 on Linux is Windows/D3D12 with an open `Missing cuInit` issue; 2x-4x PTX is reliable.
- NR: `Passes=1`, 1080p/1440p, watch 8 GB VRAM; NR and FG are not substitutes for lower textures or resolution.
- Prefer Proton-CachyOS (driver `nvngx.dll`, DXVK-NVAPI). Keep the neural OptiScaler fork; NPI is prefix-local, not a host driver change.

## Decision Gates

| Game state | Route | Action |
|---|---|---|
| Steam game, Proton | steam | `scan` -> `plan <appid>` -> `install <appid>`; prefix is automatic |
| Portable folder/exe, no appid | portable | `plan <folder> --prefix <pfx>`; use the printed Wine/UMU launch |
| Every game, version freshness | preflight | auto on plan/install; `--refresh` forces, `--no-update-check` skips |
| Native DLSS, only refresh DLLs | native | `install <appid> --route native` |
| DX12, wants SR+FG+NR | optiscaler | `install <appid> --route optiscaler --fg 4x --nr on` |
| DX11/DX9, needs NR | reshade | `install <appid> --route reshade --nr on` |
| Vulkan, NR only | vulkan | install DLSS5VKLayer, then `VKLayer_DLSS5=1 %command%` |
| No in-game FG, wants x6 | optiscaler | `--fg 6x --fg-mode combo` (experimental); only if the game supports 6x |
| 8 GB, wants balance | optiscaler | `--fg 2x --nr on` at 1080p; 4x only with measured headroom |
| Desktop/video x6 | liveflow | use `mod files/native`, not in-game FG |
| RT/PT requested | native/remix | enable only if the game ships it |

## Execution Steps

1. Run `python3 assets/nvidia-stack.py doctor`. Steam: `scan`, then `plan <appid>`. Portable: use the folder or `.exe`.
2. Run `plan <appid|name|folder|exe> [--prefix <pfx>]`. The preflight checks upstream; review route, proxy, API, portable, anti-cheat, and warnings.
3. Run `install <appid|name|folder|exe> [--prefix <pfx>]` with explicit flags. Read the printed launch options.
4. For Steam set launch options in Steam. For portable use the printed `WINEPREFIX`/`wine` or `umu-run` command, or add it as a non-Steam game and force Proton-CachyOS. Add `WINEDLLOVERRIDES` only if the proxy does not load.
5. Launch, enable DLSS/DLAA/Reflex, tune NR/FG with `verify` and Mangohud. On regression, `rollback <appid|name>`.

## Output Contract

Report: appid or portable id; API, exe, prefix, runner (Steam Proton vs portable Wine/UMU); route/proxy; preflight result; files changed; backup/manifest paths; FG multiplier (native/modded); NR passes; launch options; verify result; caveats.

## References

- `references/hardware-matrix.md` — RTX 3060 Ti capability and VRAM limits.
- `references/linux-proton.md` — Steam/Proton prefix, NGX, DXVK-NVAPI, Vulkan layer.
- `references/portable-games.md` — portable builds, Wine vs Proton, prefix setup, launch.
- `references/install-recipes.md` — exact per-route recipes and INI keys.
- `references/toolchain.md` — local payloads, versions, update checks.
- `references/upstream-watch.md` — release URLs and version status.
- `references/troubleshooting.md` — logs, black screens, VRAM, rollback.
- `assets/nvidia-stack.py` — scan, plan, install, verify, rollback, doctor.
- `assets/OptiScaler.ini.template` — managed baseline.
- `assets/launch-options.md` — Steam and portable launch examples.
