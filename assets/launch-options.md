# Steam launch options

Use one line per game. `%command%` must stay at the end.

## Portable / non-Steam games

Portable games have no `%command%`. Use the command printed by `plan`/`install`:

```bash
# existing Wine/Proton prefix
WINEPREFIX="/path/to/prefix" wine "/path/to/Game/Game.exe"

# UMU-managed prefix
GAMEID=0 PROTONPATH=/usr/share/steam/compatibilitytools.d/proton-cachyos-slr \
  umu-run "/path/to/Game/Game.exe"
```

Or add the `.exe` as a non-Steam game and force Proton-CachyOS; Steam then supplies the prefix and `%command%`.

`plan`/`install` automatically preflight upstream releases (1 h cache). Add `--refresh` to force a check or `--no-update-check` to skip it; these are helper flags, not launch options.

## OptiScaler DX12/Vulkan

```bash
DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" MANGOHUD=1 %command%
```

If the proxy does not load, add the matching override:

```bash
WINEDLLOVERRIDES="dxgi=n,b" DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" %command%
WINEDLLOVERRIDES="winmm=n,b" %command%
WINEDLLOVERRIDES="version=n,b" %command%
```

Do not add an override for a proxy that already loads; it can cause a recursive load.

## NR first test

```bash
DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024" MANGOHUD=1 %command%
```

Then enable FG after confirming the image.

## Vulkan NR (DLSS5VKLayer)

```bash
VKLayer_DLSS5=1 MANGOHUD=1 %command%
```

Native Linux Vulkan game:

```bash
VKLayer_DLSS5=1 ./GameBinary
```

## Ray tracing when the option is hidden

```bash
VKD3D_CONFIG=dxr,dxr11 MANGOHUD=1 %command%
```

Only use this when the game and `vkd3d-proton` support DXR. It does not add RT to a renderer that lacks it.

## ReShade

ReShade usually needs no launch option. For a proxy override:

```bash
WINEDLLOVERRIDES="d3d11=n,b" %command%
WINEDLLOVERRIDES="dxgi=n,b" %command%
```

## Debug

```bash
PROTON_LOG=1 DXVK_HUD=fps,frametimes,gpuload MANGOHUD=1 %command%
```

`PROTON_LOG=1` writes `~/steam-<appid>.log`. Remove it when done; it grows quickly.

## Avoid

- Stacking `dxgi=n,b` and `winmm=n,b` when only one proxy exists.
- `PROTON_DLSS_UPGRADE=1` with manual DLL swaps.
- `VKD3D_CONFIG=dxr` on a GPU/driver without DXR support.
- Forcing `VK_ICD_FILENAMES` to a non-NVIDIA ICD for NR.
