# Install recipes

All paths assume `$HOME/Software/NVIDIA` and the helper `assets/nvidia-stack.py`. Run `doctor` and `plan` first. Every recipe backs up before writing.

## 0. Common preparation

1. Confirm single-player. Stop on EAC/BattlEye/OnlineFix.
2. For Steam, find appid, game directory, prefix, and exe with `scan` (`appmanifest_*.acf`, `libraryfolders.vdf`). For a portable folder, skip `scan`: pass the folder or `.exe` and `--prefix`.
3. Detect API from PE imports. Priority: DX12, Vulkan, DX11, DX9. For Unity, also inspect `UnityPlayer.dll`.
4. Record existing `nvngx_dlss.dll`, `nvngx_dlssg.dll`, `nvngx_dlssd.dll`, `sl.interposer.dll`, `OptiScaler.ini`, `ReShade.ini`.
5. Check `pfx/drive_c/windows/system32/nvngx.dll` and `nvapi64.dll`. If missing, fix Proton or prepare plain Wine before installing mods.
6. `plan` and `install` run the upstream preflight automatically (1 h cache). Use `--refresh` to force it, `--no-update-check` to skip. Treat update warnings as review items, not automatic replacements.

### Steam / Proton

```bash
python3 assets/nvidia-stack.py scan
python3 assets/nvidia-stack.py plan <appid> --fg 2x --nr on
python3 assets/nvidia-stack.py install <appid> --fg 2x --nr on
```

Do not pass `--prefix`. The helper reads `appmanifest_<appid>.acf`, searches every library, and uses `compatdata/<appid>/pfx`. If the game has never been launched, start it once with Proton so the prefix exists. Then paste the printed line into Steam > Properties > Launch Options.

### Portable folders

```bash
python3 assets/nvidia-stack.py plan "/path/to/Game" --prefix "/path/to/prefix" --fg 2x --nr on
python3 assets/nvidia-stack.py install "/path/to/Game" --prefix "/path/to/prefix" --fg 2x --nr on
```

Use `--exe` if the helper picks a launcher. Proton-CachyOS/UMU is preferred; plain Wine needs `winetricks dxvk dxvk_nvapi vcrun2022` and the driver NGX DLLs in `system32`. See `references/portable-games.md`.

## 1. Native refresh (game already ships DLSS)

Use when the game has native DLSS and only needs newer DLLs. This adds no proxy and no injector.

```bash
python3 assets/nvidia-stack.py install <appid> --route native
```

What it does:
- Replaces `nvngx_dlss.dll` with `mod files/streamline_dlss/dlss/nvngx_dlss.dll` (310.9.1).
- If `nvngx_dlssg.dll` exists, replaces it with the bundled 310.9.1 DLSS-G.
- Leaves `nvngx_dlssd.dll` alone. Ray Reconstruction needs the game's RR DLL; the bundle does not include one. Update it from DLSS Swapper's database or the game's own update.
- Does not add Streamline. If the game already ships `sl.interposer.dll`, you may update Streamline manually from `mod files/streamline_dlss/streamline` after checking the game's version. Keep a backup.

In-game:
- DLSS Super Resolution: Quality/Balanced/Performance.
- DLAA: DLSS at 100% render scale, if the game exposes it.
- Ray Reconstruction: enable only if the game has the option.
- Reflex: On + Boost.
- RT/PT: enable only if the game ships the path. Path tracing is not injectable.

Verify:
```bash
DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" %command%
```
The indicator proves the DLL is loaded. If the game crashes, restore the backup and test the previous DLL.

## 2. OptiScaler route (DX12 / Vulkan Windows games)

Payload root:
`$HOME/Software/NVIDIA/Juegos sin DLSS Nativos/DLSS5 Manager/DLSS.5.MANAGER/mod files/if OptiScaler neural-upstream`

Use this for DX12 games and Windows Vulkan games. It adds DLSS SR, DLSS-G, NR, and optional FSR/XeSS fallbacks.

```bash
python3 assets/nvidia-stack.py install <appid> --route optiscaler --fg 4x --nr on
```

Files placed next to the exe:
- `OptiScaler/` (runtime tree, FidelityFX, XeSS, `dlssg_sm86/`, `dlssg_sm75/`)
- `OptiScaler.ini` (created if absent; existing file is backed up and patched)
- `OptiScaler.dll` copied to the chosen proxy name
- `nvngx.dll_dlssnr.dll`
- `nvngx_dlssnr.dll`
- `nvngx_dlss.dll`
- `nvngx_dlssg.dll`
- `OptiScaler/streamline/` with `sl.interposer.dll`, `sl.common.dll`, `sl.dlss.dll`, `sl.dlss_g.dll`, `sl.reflex.dll`, `sl.pcl.dll`

Proxy order: `dxgi.dll`, `winmm.dll`, `version.dll`, `dbghelp.dll`, `d3d12.dll`, `wininet.dll`, `winhttp.dll`, `OptiScaler.asi`. Vulkan starts with `winmm.dll`. If a slot is occupied by a real game file or another mod, skip it.

### Baseline INI

```ini
[Upscalers]
Dx12Upscaler=dlss
Dx11Upscaler=dlss_12
VulkanUpscaler=dlss

[DlssNr]
Enabled=true
Precision=0
Passes=1
WorkingScale=1.0
FinishedPicture=false
DeferredDLSS=auto
UnlockPasses=false
AutoCapture=true

[FrameGen]
External=true
Enabled=true
FGInput=auto
FGOutput=dlssg
FGNvngxReplacement=None

[DLSSG]
AmpereMfgUnlock=true
AmpereMfgMaxFrames=3
AmpereMfgKernelImage=ptx
InterpolationCount=auto
UseGamesReflexMarkers=auto
```

Start only NR first (`[FrameGen] Enabled=false`), confirm the image and VRAM, then enable FG. A black screen on the first launch is usually the proxy not loading or NR running before the upscaler.

### Frame generation modes

**2x–4x, DLSS-G path (recommended on SM86):**
- `AmpereMfgUnlock=true`
- `AmpereMfgMaxFrames=3` (advertises up to 4x; 0 = runtime default 3x)
- `AmpereMfgKernelImage=ptx` on Linux/Proton
- `FGOutput=dlssg`; set `FGInput=dlssg` when the game already ships DLSS-G, or `FGInput=upscaler` when it only has an upscaler
- `FGNvngxReplacement=None`
- The game's own MFG menu controls the multiplier. Use 2x first.

The bundled `OptiScaler/dlssg_sm86/` is native 0.2.3 and caps at 4x. The `sdli1995/dlssg_for_sm86` 0.4.0 release is a standalone DLSS-G replacement: it ships `version.dll`, `dlssg_sm86.ini`, and the `dlssg_sm86/` folder beside the EXE. It is not a drop-in `OptiScaler/dlssg_sm86` plugin; do not copy it there, and do not enable `AmpereMfgUnlock` or OptiScaler FG at the same time. Use it manually only if you disable OptiScaler FG; otherwise use the Combo path below. The helper does not install this standalone 0.4.0 route. It is Windows x64/D3D12; under Proton, issue #10 reports `Missing cuInit` in Bundled mode, so do not assume it works. 6x also requires the game's own Streamline/DLSS-G plugin to support 6x or Dynamic MFG; a 4x-only game cannot be forced to 6x.

**6x, FSR FG Combo (experimental fallback):**
- `[FrameGen] External=false`
- `Enabled=true`
- `FGInput=upscaler` (game has only upscaling) or `nofg`
- `FGOutput=fsrfg`
- `FGNvngxReplacement=Combo`
- `[DLSSG] InterpolationCount=5` (6x)
- `AmpereMfgUnlock=false`

Combo requires the FidelityFX FG DLLs (present in `OptiScaler/`) plus `dlss-enabler-headless.dll`. The DLSS Enabler v0.9.4 installer does not ship that exact filename: use a DLSS Enabler build that includes `dlss-enabler.asi` and rename it to `dlss-enabler-headless.dll`, or use standalone `dlssg_for_sm86` 0.4.0 instead. Put the DLL in the game directory or `~/.local/share/nvidia-stack/vendor/`; the helper copies it. It uses FFX for middle frames and the Enabler for the rest. Expect artifacts and higher latency. It is not native DLSS MFG.

**NR tuning:**
- `Passes=1` first. Two or three passes only at 1080p with RT off and measured headroom.
- `Precision=0` (FP8) on RTX 30. Do not use `Precision=4`.
- `WorkingScale=1.0`; lower only if VRAM is exhausted.
- `FinishedPicture=false` when NR should run before SR; `true` applies NR to the final image.
- `DeferredDLSS=auto`; set `true` if the game creates NGX too early.
- `AutoCapture=true` writes before/after frames to `dlssnr-capture`; use it for a quick visual check, then turn it off.

### DX11

Use the DX11→DX12 bridge:
- `Dx11Upscaler=dlss_12` (required for NR on DX11)
- Proxy `dxgi.dll` or `winmm.dll`
- Same `[DlssNr]` and `[FrameGen]` blocks
- If the game crashes at startup, try `version.dll` and `WINEDLLOVERRIDES="version=n,b"`

### Vulkan

- Set `VulkanUpscaler=dlss`
- Proxy `winmm.dll` first
- `VK_ICD_FILENAMES` must point to the NVIDIA ICD; do not force Lavapipe
- If the game is native Vulkan and only needs NR, prefer DLSS5VKLayer

### DLAA and Reflex

- DLAA normally comes from the game's DLSS menu at 100% scale. If the game hides it, OptiScaler can expose DLSS quality overrides.
- `[DLSS] RenderPresetOverride=true` only when you need a specific transformer preset. Presets: 0 Default, 1 A … 15 O.
- Reflex: enable in-game. If the game has no toggle, `[fakenvapi] ForceReflex=2` forces it. `[DLSSG] UseGamesReflexMarkers=auto` keeps DLSS-G pacing correct.
- Do not force Reflex in a game that already uses it; duplicate Reflex markers cause stutter.

## 3. ReShade route (DX11/DX9 and fallback)

Use when OptiScaler cannot hook, or the game is DX11/DX9.

```bash
python3 assets/nvidia-stack.py install <appid> --route reshade --nr on
```

The script runs the addon setup headless through Wine when possible:
```bash
WINEPREFIX="$PREFIX" wine \
  ".../ReShade_Setup_6.8.0_Addon.exe" \
  "Z:\\path\\to\\game.exe" --api dx12 --headless
```

Then it deploys:
- `renodx-dlss5.addon64` (Multipass, preferred for NR) or `renodx-dlss.addon64`
- `dlss5-feed.addon64` (or `dlss5-feed.addon32` for 32-bit)
- `nvngx_dlssnr.dll`
- `reshade-shaders/` (Shaders + Textures) and updates `ReShade.ini` search paths

DX9:
- ReShade installs as `d3d9.dll`, then moves to `dxgi.dll`
- dgVoodoo `D3D9.dll`, `dgVoodoo.conf`, `dgVoodooCpl.exe` go next to the exe
- ReShade hooks the dgVoodoo output

If ReShade already exists, the script does not rerun the setup; it only adds the DLSS 5 addons and leaves the user's preset.

Do not combine ReShade and OptiScaler in the same game unless you deliberately use different proxy names and know the load order. Two `dxgi.dll` providers cannot coexist.

## 4. Vulkan NR route (DLSS5VKLayer)

Use for native Vulkan games and Proton Vulkan games when you only need NR. It does not add SR/FG.

```bash
tar -xzf dlssnr-0.3.2-1-linux-x86_64.tar.gz
cd dlssnr-0.3.2-1 && ./install.sh --user
# log out/in
dlssnr-helper init
dlssnr-helper import-binaries \
  "$HOME/Software/NVIDIA/Juegos sin DLSS Nativos/DLSS5 Manager/DLSS.5.MANAGER/mod files/dlss 5"
dlssnr-helper doctor
dlssnr-helper start
```

Launch:
```bash
VKLayer_DLSS5=1 %command%
```

If the helper cannot start, check `~/.local/state/dlssnr/helper.log`, `dlssnr-helper runners`, and the `runner_path` in `config.ini`. For Steam games, keep the shared memory under `/tmp`; pressure-vessel makes `XDG_RUNTIME_DIR` private.

## 5. Live Flow desktop x6

`mod files/native` is a desktop-capture path, not in-game FG. It uses `dlssg_compat/version.dll` 0.3.5 for SM75/SM86 and can generate up to five frames (6x total). It estimates motion and a constant depth plane; it does not have the game's depth buffer or HUD-free color.

Use only when:
- the game has no in-game FG,
- you accept extra latency,
- you run the Live Flow/NeuralScreen worker on the same Windows/Wine desktop.

It is experimental under Linux. Do not present it as equivalent to native DLSS MFG.

## 6. Ray tracing and path tracing

- RT: enable in-game. If the option is missing, check `VKD3D_CONFIG=dxr,dxr11`, `vkd3d-proton` version, and the game's DX12 mode. RT cannot be added to a renderer that does not implement it.
- PT: only native implementations (Cyberpunk 2077, Alan Wake 2, etc.) or RTX Remix. There is no generic path-tracing injector.
- RR: only game-supported; update `nvngx_dlssd.dll` if present.
- DLSS 5 NR is neural post-processing. It can improve image quality, but it is not RT or PT.

## 7. NVIDIA Profile Inspector

NPI is optional. Use it only inside the prefix and only if NVAPI is exposed:
- import/export `.nip`
- DLSS/DLSS RR/DLSS FG override entries
- `-silentImport`, `-exportCustomized`, `-createCSN`, `-showOnlyCSN`, `-disableScan`

On Linux it edits the prefix's NVAPI profile view, not the host driver. Do not claim global changes.
