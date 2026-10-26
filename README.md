# nvidia-dlss-linux

An OpenCode skill plus a Python helper for adding NVIDIA gaming features to
single-player games on Linux. It targets CachyOS/Omarchy and Wine/Proton, with
specific tuning for the RTX 3060 Ti 8 GB.

## What it covers

- DLSS Super Resolution, DLAA, Ray Reconstruction and Reflex when the game
  provides the required hooks.
- DLSS 5 Neural Rendering through a user-supplied `nvngx_dlssnr.dll` and the
  NVIDIA driver's NGX core.
- Frame Generation: OptiScaler 2x-4x on RTX 20/30, plus experimental 6x paths
  where the game and runtime support them.
- Steam games, non-Steam games, and pre-installed portable Windows folders.
- Automatic upstream release preflight on `plan` and `install`.

## What it does not do

This repository contains documentation and a Python helper only. It does **not**
include NVIDIA DLLs, game files, cracks, DRM circumvention tools, or download
links. Bring your own legally obtained runtimes.

It does not inject path tracing into games that do not implement it. It does not
support anti-cheat multiplayer games. Use it only with single-player games you
own and are allowed to modify.

## Requirements

- Linux with an NVIDIA GPU and a driver that provides NGX and DXVK-NVAPI.
- Python 3.10+ (the helper uses the standard library only).
- Wine or Proton. Proton-CachyOS is recommended because it installs the driver
  `nvngx.dll` and enables DXVK-NVAPI.
- Local NVIDIA payloads. The helper expects them under
  `$HOME/Software/NVIDIA` by default; set `NVIDIA_STACK_ASSETS` to another path.
- `objdump` from binutils for the most reliable PE import detection.

## Install as an OpenCode skill

Copy or symlink this directory into your global skills directory:

```bash
git clone <repository-url> nvidia-dlss-linux
ln -s "$PWD/nvidia-dlss-linux" "$HOME/.config/opencode/skills/nvidia-dlss-linux"
```

Restart OpenCode after adding the skill.

## Usage

```bash
python3 assets/nvidia-stack.py doctor
python3 assets/nvidia-stack.py scan
python3 assets/nvidia-stack.py plan <appid-or-name>
python3 assets/nvidia-stack.py install <appid-or-name> --route optiscaler --fg 2x --nr on
```

## Steam + Proton

Steam games are the primary path. The helper reads `libraryfolders.vdf` and
`appmanifest_<appid>.acf`, finds the game and its `compatdata/<appid>/pfx`, and
does not need `--prefix`.

```bash
python3 assets/nvidia-stack.py scan
python3 assets/nvidia-stack.py plan 12345
python3 assets/nvidia-stack.py install 12345 --route optiscaler --fg 2x --nr on
```

Put the printed line in Steam > Properties > Launch Options. Prefer
Proton-CachyOS or Proton-GE; Valve's default Proton may not expose
DXVK-NVAPI/NGX. `--prefix` is only for portable or custom prefixes.

### Portable folder or executable

```bash
python3 assets/nvidia-stack.py plan /path/to/Game --prefix /path/to/prefix
python3 assets/nvidia-stack.py install /path/to/Game --prefix /path/to/prefix --fg 2x --nr on
```

Other commands:

```bash
python3 assets/nvidia-stack.py verify <appid-or-name>
python3 assets/nvidia-stack.py rollback <appid-or-name>
python3 assets/nvidia-stack.py update-check --refresh
```

Every install records backups and a JSON manifest. `rollback` restores the
previous files.

`plan` and `install` run the upstream preflight automatically. Results are
cached for one hour. Use `--refresh` to force a fresh check or
`--no-update-check` to skip it.

## RTX 3060 Ti 8 GB notes

- Native DLSS SR, RR, DLAA, Reflex and DLSS 5 NR are usable.
- Native DLSS Frame Generation / Multi Frame Generation is not available on
  Ampere. The 2x-4x routes are modded and use SM86 kernels.
- 6x is conditional and experimental. A game whose DLSS-G plugin only supports
  4x cannot be forced to 6x.
- Start Neural Rendering with `Passes=1` at 1080p or 1440p and watch VRAM.
- Path tracing remains native-only or RTX Remix.

## Documentation

- `SKILL.md` - activation contract and execution flow.
- `references/hardware-matrix.md` - GPU capabilities and VRAM guidance.
- `references/linux-proton.md` - prefixes, NGX, DXVK-NVAPI, Vulkan layer.
- `references/portable-games.md` - portable builds and Wine/Proton setup.
- `references/install-recipes.md` - per-route recipes and INI keys.
- `references/toolchain.md` - payloads, versions and update commands.
- `references/upstream-watch.md` - release status and version traps.
- `references/troubleshooting.md` - logs, crashes, VRAM and rollback.
- `assets/nvidia-stack.py` - the helper CLI.
- `assets/OptiScaler.ini.template` - baseline configuration.
- `assets/launch-options.md` - Steam and portable launch examples.

## License

Apache-2.0. See `LICENSE`.
