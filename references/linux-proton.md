# Linux, Proton, and prefix mechanics

## Steam layout

Typical libraries:
- `$HOME/.local/share/Steam`
- `/mnt/games/Steam`
- other paths listed in `steamapps/libraryfolders.vdf`

For an appid:
- manifest: `<library>/steamapps/appmanifest_<appid>.acf`
- game: `<library>/steamapps/common/<installdir>`
- prefix: `<library>/steamapps/compatdata/<appid>/pfx`

The prefix may live in a different library than the game. Search every library. A prefix contains:
- `pfx/drive_c/windows/system32/nvngx.dll`
- `pfx/drive_c/windows/system32/nvapi64.dll`
- `pfx/drive_c/users/steamuser/...`

Wine resolves `Z:` to `/`. A game at `/mnt/games/Game/game.exe` is `Z:\mnt\games\Game\game.exe` inside the prefix.

## Steam workflow

For Steam, run `scan` to get the appid, then `plan <appid>`. Do not pass `--prefix`; the helper searches every library, reads `appmanifest_<appid>.acf`, and selects `compatdata/<appid>/pfx`. Install with `install <appid> ...`, then put the printed options in Steam. Use `--prefix` only for a custom or non-Steam prefix.

## Portable games (no Steam appid)

Portable releases are pre-installed folders, often with the game at `bin/x64/<Game>.exe` or `Binaries/Win64/<Game>.exe`. There is no `appmanifest` and no installer. Pass the folder or `.exe` directly:

```bash
python3 assets/nvidia-stack.py plan "/path/to/Game" --prefix "/path/to/prefix"
python3 assets/nvidia-stack.py plan "/path/to/Game/Game.exe" --exe "/path/to/Game/bin/x64/Game.exe" --prefix "/path/to/prefix"
```

For portable games the helper auto-detects `WINEPREFIX`, then `~/.wine` if it has `drive_c`. Proton-CachyOS/UMU is preferred because it installs the driver `nvngx.dll` and DXVK-NVAPI. Plain Wine needs `winetricks dxvk dxvk_nvapi vcrun2022` and the driver NGX files copied into `system32`. A portable prefix should contain both `nvngx.dll` and `nvapi64.dll`; `plan` warns if either is missing.

Launch with the printed command:

```bash
WINEPREFIX="/path/to/prefix" wine "/path/to/Game/Game.exe"
```

Or add the `.exe` as a non-Steam game and force Proton-CachyOS; its prefix is `compatdata/<generated-appid>/pfx`. For UMU use `GAMEID=0 PROTONPATH=/usr/share/steam/compatibilitytools.d/proton-cachyos-slr umu-run "/path/to/Game/Game.exe"`.

Treat the folder as untrusted: it may contain a crack, OnlineFix, or missing runtimes. Single-player only; never download a crack. See `references/portable-games.md` for the full workflow.

## NGX and DLSS on this machine

The NVIDIA driver ships:
- `/usr/lib/nvidia/wine/nvngx.dll` (NGX core)
- `/usr/lib/nvidia/wine/_nvngx.dll`
- `/usr/lib/nvidia/wine/nvngx_dlssg.dll`

`/usr/lib64/nvidia/wine/` mirrors them. Proton-CachyOS has `find_nvidia_wine_dll_dir()` and `setup_prefix()`; it copies `_nvngx.dll` and `nvngx.dll` into `drive_c/windows/system32` automatically. The verified prefix `compatdata/<appid>` already has both `nvngx.dll` and `nvapi64.dll`.

Proton-CachyOS defaults:
- `DXVK_ENABLE_NVAPI=1` unless the compatibility config says `disablenvapi` and not `forcenvapi`.
- `DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS=DLSSIndicator=0,DLSSGIndicator=0,`
- the `dlsshud` compatibility option sets `DLSSIndicator=1024,DLSSGIndicator=2,`

Use Proton-CachyOS SLR at `/usr/share/steam/compatibilitytools.d/proton-cachyos-slr` for the full path. Proton Experimental is at `~/.steam/steam/steamapps/common/Proton - Experimental`.

## Environment variables

Set these in Steam launch options, not globally, unless debugging:

```bash
# Show DLSS/DLSS-G state in the corner
DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" %command%

# Force NVAPI for older Proton/GE builds
PROTON_ENABLE_NVAPI=1 %command%

# Load a proxy that Wine may otherwise prefer from system32
WINEDLLOVERRIDES="dxgi=n,b" %command%
WINEDLLOVERRIDES="winmm=n,b" %command%
WINEDLLOVERRIDES="version=n,b" %command%

# Frame stats
MANGOHUD=1 %command%
DXVK_HUD=fps,frametimes,gpuload %command%

# Enable DXR when a game hides the option
VKD3D_CONFIG=dxr,dxr11 %command%
```

Do not combine `PROTON_DLSS_UPGRADE=1` with manual DLL swaps. Proton's upgrade path can replace your files on the next launch.

`WINEDLLOVERRIDES` is only for a proxy that is not loading. It is not needed for a normal `dxgi.dll`/`winmm.dll` in the game directory.

## DXVK-NVAPI

DXVK-NVAPI supplies the Windows NVAPI surface (`nvapi64.dll`) and NGX integration. It is what lets DLSS, Reflex, and NGX features work under Proton. The driver's `nvngx.dll` is the NGX core; DXVK-NVAPI is the bridge.

Check inside the prefix:
```bash
ls -l "$PREFIX/drive_c/windows/system32/nvngx.dll" \
      "$PREFIX/drive_c/windows/system32/nvapi64.dll"
```

If `nvngx.dll` is missing, the game cannot use DLSS 5 NR. Switch to Proton-CachyOS/GE or set `PROTON_ENABLE_NVAPI=1` and re-create the prefix. Do not copy a random `nvngx.dll` from the internet into system32; use the driver file.

## Native Vulkan and DLSS5VKLayer

`bmitch87/DLSS5VKLayer` is a Vulkan implicit layer plus a helper service. It forwards presented frames to a Windows NGX helper under Wine or custom Proton, then returns the neural-rendered frame to the swapchain. It is the cleanest NR route for Vulkan-native games and Proton Vulkan games, and it does not add DLSS SR or FG.

Install (user scope):
```bash
tar -xzf dlssnr-0.3.2-1-linux-x86_64.tar.gz
cd dlssnr-0.3.2-1
./install.sh --user
# log out and back in so ~/.config/environment.d/dlssnr.conf applies
dlssnr-helper init
dlssnr-helper import-binaries "$HOME/Software/NVIDIA/Juegos sin DLSS Nativos/DLSS5 Manager/DLSS.5.MANAGER/mod files/dlss 5"
dlssnr-helper doctor
dlssnr-helper start
```

Run a game:
```bash
VKLayer_DLSS5=1 %command%
```

Key paths:
- config: `$XDG_CONFIG_HOME/dlssnr/config.ini`
- runtime: `/tmp/dlssnr-$UID/`
- logs/state: `$XDG_STATE_HOME/dlssnr/` or `~/.local/state/dlssnr/`
- managed prefix: `~/.local/share/dlssnr/prefix/`
- binaries: `$XDG_DATA_HOME/dlssnr/binaries`

The public package excludes NVIDIA NGX DLLs. `nvngx_dlssnr.dll` is required; `nvngx.dll`, `nvapi64.dll`, and Streamline are optional. Use the local `mod files/dlss 5` directory as the import source.

Runner discovery checks user compatibility tools first, then Flatpak/Snap, then `/usr/share`. `dlssnr-helper runners` lists candidates. If the helper cannot find Proton-CachyOS, set `runner_type=proton` and `runner_path=/usr/share/steam/compatibilitytools.d/proton-cachyos-slr/proton` in `config.ini`.

The layer is fail-open: if the helper is missing, the game renders normally. It is disabled unless `VKLayer_DLSS5=1` is set.

## ReShade under Proton

ReShade needs the **addon build**. The DLSS5 Manager payload is `ReShade_Setup_6.8.0_Addon.exe`.

Headless install inside a prefix:
```bash
WINEPREFIX="$PREFIX" wine \
  "/path/ReShade_Setup_6.8.0_Addon.exe" \
  "Z:\\path\\to\\game.exe" --api dx12 --headless
```

`--api` is `dx12`, `dx11`, `dx9`, or `vulkan`. The setup writes `<api>.dll` and `ReShade.ini` next to the exe. DX9 is special: ReShade goes to `d3d9.dll`, then moves to `dxgi.dll`, and dgVoodoo takes `d3d9.dll`.

ReShade and OptiScaler both want `dxgi.dll`. Pick one route per game. If ReShade is already present, OptiScaler should use `winmm.dll` or `version.dll`.

## NVIDIA Profile Inspector

NPI is a Windows WPF tool that edits NVIDIA driver profiles through NVAPI. Under Wine it can only affect the prefix's NVAPI view, not the Linux driver globally. Use it for per-profile DLSS/RR/FG overrides only after confirming the prefix exposes NVAPI. Do not tell the user it changes `nvidia-settings` or the host driver.

## Anti-cheat

Stop if the game directory contains `EasyAntiCheat`, `BattlEye`, `start_protected_game.exe`, an EAC/BattlEye launcher, or an `OnlineFix`/online-fix DLL. Proxy DLLs, ReShade, and OptiScaler are exactly what these systems block. There is no safe automation for competitive multiplayer.
