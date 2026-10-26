# Portable / pre-installed games

Portable releases are usually pre-installed Windows folders, not Steam appids and not installers. The user extracts the archive and runs an `.exe` directly, often `bin/x64/<Game>.exe` or `<Game>/Binaries/Win64/<Game>.exe`. Treat every such build as untrusted: it may contain a crack, an online fix, a repack launcher, or missing runtimes. This skill only supports single-player use and never downloads or repairs cracks.

## Detect the game

```bash
python3 assets/nvidia-stack.py plan /path/to/Game --prefix /path/to/prefix
python3 assets/nvidia-stack.py plan /path/to/Game/Game.exe --prefix /path/to/prefix
```

The helper gives a portable game a stable `portable-<name>-<hash>` id, finds the best `.exe`, detects PE vs native ELF, and reads PE imports for D3D12/D3D11/D3D9/Vulkan. If it picks a launcher or the wrong binary, pass `--exe`:

```bash
python3 assets/nvidia-stack.py plan /path/to/Game --exe /path/to/Game/bin/x64/Game.exe --prefix /path/to/prefix
```

## Choose the runner

| Situation | Use | Why |
|---|---|---|
| DLSS/NR/FG wanted | Proton-CachyOS via non-Steam game or `umu-run` | Copies driver `nvngx.dll`/`_nvngx.dll` into the prefix and enables DXVK-NVAPI |
| Already have a Proton prefix | `--prefix .../compatdata/<appid>/pfx` | Reuses DXVK, NVAPI, and NGX |
| Plain Wine only | `winetricks dxvk dxvk_nvapi vcrun2022`, then add NGX | More manual; no guarantee of NGX |
| Native Linux Vulkan build | DLSS5VKLayer | No Wine prefix; `VKLayer_DLSS5=1` |

Proton-CachyOS is the default recommendation. Plain Wine does not ship DXVK, DXVK-NVAPI, or the NVIDIA NGX core by default.

## Prefix rules

`--prefix` accepts either a Wine prefix root (the directory containing `drive_c`) or a Proton `.../pfx` directory. The helper normalizes both. If `--prefix` is omitted for a portable game, it uses `WINEPREFIX`, then `~/.wine` when that prefix has `drive_c`.

A usable NVIDIA prefix should contain:

```text
<pfx>/drive_c/windows/system32/nvngx.dll
<pfx>/drive_c/windows/system32/nvapi64.dll
```

`nvngx.dll` is the NGX core; `nvapi64.dll` is DXVK-NVAPI. Missing files produce warnings in `plan`. Fix by launching once with Proton-CachyOS/UMU, or for plain Wine:

```bash
export WINEPREFIX=/path/to/prefix
winetricks dxvk dxvk_nvapi vcrun2022
cp /usr/lib/nvidia/wine/nvngx.dll /usr/lib/nvidia/wine/_nvngx.dll \
   /usr/lib/nvidia/wine/nvngx_dlssg.dll \
   "$WINEPREFIX/drive_c/windows/system32/"
```

Do not copy the 276 MB `nvngx_dlssnr.dll` into `system32`; the route installs it beside the game executable.

## Launch

With an existing prefix, the helper prints:

```bash
WINEPREFIX="/path/to/prefix" wine "/path/to/Game/Game.exe"
```

Prefer registering the `.exe` as a non-Steam game and forcing Proton-CachyOS. The generated prefix is then:

```text
~/.local/share/Steam/steamapps/compatdata/<generated-appid>/pfx
```

For UMU:

```bash
GAMEID=0 PROTONPATH=/usr/share/steam/compatibilitytools.d/proton-cachyos-slr \
  umu-run "/path/to/Game/Game.exe"
```

Use the real Proton directory that contains the `proton` script. Add `WINEDLLOVERRIDES="<proxy>=n,b"` only when the chosen OptiScaler proxy does not load.

## Install

```bash
python3 assets/nvidia-stack.py plan /path/to/Game --prefix /path/to/prefix --fg 2x --nr on
python3 assets/nvidia-stack.py install /path/to/Game --prefix /path/to/prefix --fg 2x --nr on --dry-run
python3 assets/nvidia-stack.py install /path/to/Game --prefix /path/to/prefix --fg 2x --nr on
```

Every `plan` and `install` runs the upstream preflight. It uses a one-hour cache, prints only changed versions to stderr, and never blocks on network failure. `--refresh` forces a check; `--no-update-check` skips it. Updates are warnings: the neural OptiScaler fork and the leaked NR runtime are not replaced silently.

## Folder and permission gotchas

- Repacks often ship `_CommonRedist`, `redist`, `DirectX`, or `dotnet` folders. Install missing VC++/.NET only if the game actually needs them.
- Some games write saves/config next to the `.exe`. Keep the folder writable; avoid read-only NTFS mounts.
- External drives appear under Wine as `Z:`; use the Linux path in the helper.
- A game may ship its own `dxgi.dll`, `winmm.dll`, or `version.dll`. The helper picks a free proxy slot; do not overwrite a game DLL that is already there.
- 32-bit games need the `host64` side-by-side layout; the helper warns.
- If the game has `EasyAntiCheat`, `BattlEye`, `OnlineFix`, or a protected launcher, stop. Do not install mods.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No executable found` | Pass `--exe` with the real game binary, not the launcher |
| `Graphics API not detected` | Inspect the PE imports or set the route explicitly |
| `prefix not found` / no `nvngx.dll` | Use Proton-CachyOS/UMU or prepare the plain-Wine prefix as above |
| Game starts but no DLSS menu | Confirm the exe, API, and proxy; inspect `OptiScaler.log` |
| Black screen after install | Roll back, try the other proxy, or disable NR/FG |
| Overlay or launcher conflict | Test without Steam overlay; use a direct `wine` launch |
