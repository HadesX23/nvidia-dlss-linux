---
name: nvidia-dlss-linux
description: "Trigger: DLSS, DLSS 5, Neural Rendering, Ray Tracing, Path Tracing, Frame Generation, DLAA, Reflex, OptiScaler, RTX 3060 Ti, CachyOS, Proton, portable. Add and tune NVIDIA game tech on Linux."
license: Apache-2.0
metadata:
  author: "nvidia-dlss-linux contributors"
  version: "1.0"
---

## Activation Contract

Use for a single-player game on CachyOS/Omarchy that needs DLSS Super Resolution, DLAA, Ray Reconstruction, Reflex, Frame Generation (including modded x6), or DLSS 5 Neural Rendering under Steam Proton, Wine, UMU, or native Vulkan. This includes pre-installed portable Windows builds with no Steam appid. Every plan/install preflights upstream (1 h cache); `--refresh` forces it. Target: RTX 3060 Ti 8 GB. Use the bundled helper and local payloads first.

Do not use on anti-cheat multiplayer, native macOS, or to promise path tracing in an engine that does not implement it.

## Hard Rules

- Single-player only. Stop on EAC, BattlEye, kernel anti-cheat, or OnlineFix.
- Portable builds are untrusted and often cracked. Never download cracks or bypass DRM; use a dedicated prefix and only the user's existing files.
- Inspect API, exe, prefix, and existing mods. Back up every file and write a rollback manifest before copying.
- Run the upstream preflight on every game. Warn on updates; never silently replace the neural OptiScaler fork or leaked NR DLL.
- For portable games pass `--prefix`, or set `WINEPREFIX`.
- Path tracing is native-only or RTX Remix. DLSS 5 NR is post-processing, not PT.
- RTX 3060 Ti: native SR/RR/DLAA/Reflex and NR are usable; native FG/MFG is not. Label x6 as modded (SM86 kernels, FSR FG Combo, or Live Flow).
- 6x is conditional: a game whose DLSS-G plugin only supports 4x cannot be forced to 6x. On Linux/Proton, 0.4.0 is Windows/D3D12 and has an open `Missing cuInit` issue; 2x-4x PTX is the reliable route.
- NR: start `Passes=1`, 1080p/1440p, watch 8 GB VRAM. NR and FG cost VRAM; they are not substitutes for lower textures or resolution.
- Prefer Proton-CachyOS; it installs the driver `nvngx.dll` and enables DXVK-NVAPI. Keep the neural OptiScaler fork. Do not claim NPI changes the host driver.

## Decision Gates

| Game state | Route | Action |
|---|---|---|
| Portable folder/exe, no appid | portable | `plan <folder> --prefix <pfx>`; use the printed Wine/UMU launch |
| Every game, version freshness | preflight | auto on plan/install; `--refresh` forces, `--no-update-check` skips |
| Native DLSS, only refresh DLLs | native | `install <appid> --route native` |
| DX12, wants SR+FG+NR | optiscaler | `install <appid> --route optiscaler --fg 4x --nr on` |
| DX11/DX9, needs NR | reshade | `install <appid> --route reshade --nr on` |
| Vulkan, NR only | vulkan | install DLSS5VKLayer, then `VKLayer_DLSS5=1 %command%` |
| No in-game FG, wants x6 | optiscaler | `--fg 6x --fg-mode combo` (experimental); only if the game supports 6x, otherwise 4x |
| 8 GB, wants balance | optiscaler | `--fg 2x --nr on` at 1080p; 4x only with measured headroom |
| Desktop/video x6 | liveflow | use `mod files/native`, not in-game FG |
| RT/PT requested | native/remix | enable only if the game ships it |

## Execution Steps

1. Run `python3 assets/nvidia-stack.py doctor`. Steam: `scan`. Portable: use the folder or `.exe`.
2. Run `plan <appid|name|folder|exe> [--prefix <pfx>]`. The preflight checks upstream; review route, proxy, API, portable, anti-cheat, and warnings.
3. Run `install <appid|name|folder|exe> [--prefix <pfx>]` with explicit flags. Read the printed launch options.
4. For Steam set launch options. For portable use the printed `WINEPREFIX`/`wine` or `umu-run` command, or add it as a non-Steam game and force Proton-CachyOS. Add `WINEDLLOVERRIDES` only if the proxy does not load.
5. Launch, enable DLSS/DLAA/Reflex, tune NR/FG with `verify` and Mangohud. On regression, `rollback <appid|name>`.

## Output Contract

Report: appid or portable id; API, exe, prefix, runner; route/proxy; preflight result; files changed; backup/manifest paths; FG multiplier (native/modded); NR passes; launch options; verify result; caveats.

## References

- `references/hardware-matrix.md` — RTX 3060 Ti capability and VRAM limits.
- `references/linux-proton.md` — prefix, NGX, DXVK-NVAPI, Steam, Vulkan layer.
- `references/portable-games.md` — pre-installed portable builds, Wine vs Proton, prefix setup, launch.
- `references/install-recipes.md` — exact per-route recipes and INI keys.
- `references/toolchain.md` — local payloads, versions, update checks.
- `references/upstream-watch.md` — release URLs and version status.
- `references/troubleshooting.md` — logs, black screens, VRAM, rollback.
- `assets/nvidia-stack.py` — scan, plan, install, verify, rollback, doctor.
- `assets/OptiScaler.ini.template` — managed baseline.
- `assets/launch-options.md` — Steam launch examples.
