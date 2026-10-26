# Toolchain and local payloads

Root: `$HOME/Software/NVIDIA`

## Native-DLSS tools

| Path | What it is | Use |
|---|---|---|
| `Juegos con DLSS Nativo/DLSS Swapper/dlss-swapper-1.2.7.0/` | DLSS Swapper source + DLL database | Find and update `nvngx_dlss.dll`, `nvngx_dlssg.dll`, `nvngx_dlssd.dll` |
| `Juegos con DLSS Nativo/DLSS Swapper/DLSS.Swapper-1.2.7.0-portable/` | Windows portable app | Optional under Wine; does not scan Linux Steam reliably |
| `Juegos con DLSS Nativo/ProfileInspector/nvidiaProfileInspector-3.0.2.3/` | NVIDIA Profile Inspector source/app | Per-profile DLSS/RR/FG overrides inside a prefix only |

DLSS Swapper's useful files are `src/Data/DLLManager.cs`, `src/Data/Game.cs`, and `src/Helpers/NVAPIHelper.cs`. Treat them as a catalog of known DLL versions, not as a Linux library scanner.

## Non-native-DLSS payload

`Juegos sin DLSS Nativos/DLSS5 Manager/DLSS.5.MANAGER/mod files/`

| Path | Contents |
|---|---|
| `if OptiScaler neural-upstream/` | OptiScaler 0.7.7 neural fork; the correct build for RTX 20/30 |
| `if Optiscaler RTX40/` | OptiScaler build for RTX 40/50; **do not use on RTX 3060 Ti** |
| `dlss 5/nvngx_dlssnr.dll` | DLSS 5 NR runtime, 276,162,560 bytes, NGX rel_310_9 |
| `streamline_dlss/dlss/nvngx_dlss.dll` | DLSS SR 310.9.1.0, 74,187,376 bytes |
| `streamline_dlss/dlss/nvngx_dlssg.dll` | DLSS-G 310.9.1.0, 7,506,544 bytes |
| `streamline_dlss/streamline/` | Streamline 2.14.1.0: `sl.common`, `sl.dlss`, `sl.dlss_d`, `sl.dlss_g`, `sl.reflex`, `sl.pcl`, `sl.interposer`, `sl.nis`, `sl.nvperf`, `sl.deepdvc`, `sl.directsr` |
| `if dx9/` | dgVoodoo: `D3D9.dll`, `dgVoodoo.conf`, `dgVoodooCpl.exe` |
| `if Vulkan/`, `if emulator/` | Deep-fried chicken NVNGX payload |
| `if amd/` | AMD/RDNA route files; not for this NVIDIA card |
| `if 32 bit/host64/` | Side-by-side 64-bit host for 32-bit games |
| `native/` | Live Flow / NeuralScreen desktop FG: `dlssg_compat/version.dll` 0.3.5, `supermotion/`, `screen/`, embedded Python runtime |
| `ReShade_Setup_6.8.0_Addon.exe` | ReShade 6.8.0 addon installer, 4,318,424 bytes |
| `renodx-dlss.addon64` | RenoDX DLSS addon, 3,013,120 bytes |
| `renodx-dlss5.addon64` | Multipass NR addon, 3,198,976 bytes |
| `renodx-mfgunlock.addon64` | RTX 40 MFG unlock addon; not for RTX 30 |
| `dlss5-feed.addon64` / `dlss5-feed.addon32` | Neural feed addons, 329,728 / 189,952 bytes |
| `nvngx.dll.addon64` | 710,017-byte addon |
| `reshade-shaders/` | Standard Shaders + Textures |

## OptiScaler neural fork details

Root: `mod files/if OptiScaler neural-upstream/`

- `OptiScaler.dll` 26,116,608 bytes, version `0.7.7-final (e237f895)`.
- `OptiScaler.ini` 62,198 bytes.
- `nvngx.dll_dlssnr.dll` 151,552 bytes; exports the private `DLSSNR.*` parameter API.
- `OptiScaler/amd_fidelityfx_framegeneration_dx12.dll` 40,085,776 bytes.
- `OptiScaler/amd_fidelityfx_loader_dx12.dll`, `amd_fidelityfx_upscaler_dx12.dll` 28,761,864 bytes, `amd_fidelityfx_vk.dll`.
- `OptiScaler/libxess.dll` 77,795,704 bytes, `libxess_dx11.dll`, `libxess_fg.dll`, `libxell.dll`.
- `OptiScaler/dlssg_sm86/`: `dlssg_sm86.dll` 15,667,520 bytes; `dlssg_sm86.ini` says native 0.2.3, `MaxGeneratedFrames=3` (4x).
- `OptiScaler/dlssg_sm75/`: Turing equivalent.
- `OptiScaler/plugins/XeFGUnlock.ini`, `OptiScaler/D3D12_OptiScaler`, `OptiScaler/nvfp4/`.

The fork is newer than upstream OptiScaler v0.9.4 for this use case. Do not replace it with upstream unless a specific upstream fix is required; you would lose the neural parameter contract.

## Version status (2026-10-26)

| Project | Current | Local | Note |
|---|---|---|---|
| DLSS Swapper | v1.2.7.0 (2026-10-18) | same | current |
| NVIDIA Profile Inspector | v3.0.2.3 prerelease (2026-10-13) | same | current; 3.0.2.1 is stable |
| DLSS5 Manager | 1.3.8 (2026-10-22) | same | current |
| OptiScaler upstream | v0.9.4 (2026-07-18) | neural 0.7.7 fork | do not blindly upgrade |
| DLSS5VKLayer | 0.3.2-1 (2026-10-26) | not bundled | install separately |
| Streamline | 2.14.16 (2026-10-16) | 2.14.1 | update only if a game needs it |
| dlssg_for_sm86 | 0.4.0 (2026-10-14) | 0.3.5 liveflow / 0.2.3 OptiScaler | needed for 6x in-game |
| RTX40MFG-Unlock | 1.7.0 (2026-10-25) | not bundled | RTX 40 only |
| ReShade | 6.8.0 | bundled | rolling upstream |
| RenoDX | rolling | bundled addons | rolling upstream |
| DXVK-NVAPI | `jp7677/dxvk-nvapi` | via Proton | verify repo before use |

## Update checks

Use the GitHub API without authentication for release tags:
```bash
for repo in beeradmoore/dlss-swapper Orbmu2k/nvidiaProfileInspector \
            NODIX-TECH/DLSS-5-MANAGER bmitch87/DLSS5VKLayer \
            NVIDIA-RTX/Streamline sdli1995/dlssg_for_sm86; do
  printf '%s ' "$repo"
  curl -fsSL "https://api.github.com/repos/$repo/releases/latest" \
    | jq -r '.tag_name + " " + .published_at'
done
```

For NPI, `/releases/latest` can return the stable release while the newest is a prerelease. Check `/releases?per_page=5` and compare `prerelease`.

Download a release asset:
```bash
gh release download <tag> --repo <owner/repo> --pattern '<asset>'
```

Source updates:
```bash
git -C "$HOME/Software/NVIDIA/Juegos sin DLSS Nativos/DLSS5 Manager/DLSS-5-MANAGER-1.3.8" pull
```

ReShade and RenoDX have no stable GitHub release tags; compare the bundled file sizes/dates and upstream commits.

## Portable games

Portable releases have no appid and no installer. Pass the folder or `.exe` plus `--prefix`:

```bash
python3 assets/nvidia-stack.py plan "/path/to/Game" --prefix "/path/to/prefix"
```

The helper assigns a stable `portable-<name>-<hash>` id, finds the exe, and detects PE/ELF and the API. For DLSS/NR, Proton-CachyOS or UMU is preferred; plain Wine needs DXVK-NVAPI and the driver NGX files. See `references/portable-games.md`.

## Integrity

`mod files/if OptiScaler neural-upstream/SHA256SUMS.txt` covers that payload. Verify before and after copying:
```bash
cd "mod files/if OptiScaler neural-upstream"
sha256sum -c SHA256SUMS.txt
```

For the 276 MB NR DLL, compare size and SHA-256 with the manager's manifest. A truncated copy causes NGX initialization failure, not a clear error.

## Update policy

1. `plan`/`install` run the upstream preflight automatically (1 h cache); use `--refresh` to force a new check and `--no-update-check` to skip it. Never auto-replace the neural fork or NR DLL.
2. Re-download the whole DLSS5 Manager release, not individual files.
3. Keep the old `mod files` tree until the new one passes `doctor` and one game test.
4. Never overwrite `if OptiScaler neural-upstream` with upstream OptiScaler.
5. Do not replace `OptiScaler/dlssg_sm86/` 0.2.3 with the 0.4.0 release: 0.4.0 is a standalone `version.dll` + `dlssg_sm86/` payload. Keep 0.2.3 for `AmpereMfgUnlock` 2x–4x; use 0.4.0 manually only with OptiScaler FG disabled.
6. Re-run `sha256sum -c` after any manual replacement.
