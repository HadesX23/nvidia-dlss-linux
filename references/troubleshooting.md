# Troubleshooting

## First checks

```bash
python3 assets/nvidia-stack.py doctor
python3 assets/nvidia-stack.py verify <appid>
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv
vulkaninfo --summary | grep -i nvidia
```

Inside the prefix:
```bash
ls -l "$PREFIX/drive_c/windows/system32/nvngx.dll" \
      "$PREFIX/drive_c/windows/system32/nvapi64.dll"
```

If `nvngx.dll` is missing, fix Proton/NVAPI before touching game files.

## Logs

| File | What it tells you |
|---|---|
| `<game>/OptiScaler.log` | proxy load, API hook, upscaler/FG/NR init |
| `<game>/ReShade.log` | ReShade runtime, addon load, effect compile |
| `<game>/dlss5-feed.cfg` | neural feed settings written by the addon |
| `<game>/dlssnr_on_amd.log` | AMD route only; ignore on NVIDIA |
| `<game>/dgVoodoo.log` | DX9 wrapper |
| `<game>/dlssnr-capture/` | NR before/after frames when `AutoCapture=true` |
| `~/.local/state/dlssnr/helper.log` | DLSS5VKLayer helper |
| `~/.config/dlssnr/config.ini` | Vulkan layer config |
| `/tmp/dlssnr-$UID/` | Vulkan layer shared memory/PID |

Enable more detail:
```bash
DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" %command%
VK_LOADER_DEBUG=error,warn %command%
MANGOHUD=1 %command%
```

## Game does not launch or black screen

1. Remove the proxy temporarily: rename `dxgi.dll`/`winmm.dll` to `.off`, launch. If it starts, the proxy is the problem.
2. Check the API. OptiScaler on a DX11 game with `Dx12Upscaler` only will not hook; use `Dx11Upscaler=dlss_12`.
3. Check proxy conflicts. ReShade, OptiScaler, Special K, and DLSS5VKLayer can all want `dxgi.dll`.
4. Restore the pre-install DLLs with `rollback`. If the game still fails, verify the game files in Steam.
5. For NR, disable FG first. Multi-pass NR plus FG on 8 GB can hard-hang.
6. Delete stale `OptiScaler.log` before a retest so you read the new run.

## NR is not active

- `nvngx_dlssnr.dll` must be next to the exe.
- `nvngx.dll` must exist in `system32` and come from the NVIDIA driver.
- DX11 needs `Dx11Upscaler=dlss_12`.
- Set `[DlssNr] Enabled=true`, `Passes=1`, `Precision=0`.
- Try `DeferredDLSS=true` if NGX initializes before the swapchain.
- Try `FinishedPicture=true` if NR before SR is incompatible with the game.
- `RunBeforeSR=auto`; force `false` only for testing.
- For Vulkan, `VKLayer_DLSS5=1` must be set and `dlssnr-helper status` must be running.
- DLSS5VKLayer: run `dlssnr-helper doctor`; check runner discovery with `dlssnr-helper runners`; confirm the imported `nvngx_dlssnr.dll` is in `$XDG_DATA_HOME/dlssnr/binaries`.

## Frame Generation option is missing

- Native DLSS-G requires the game to ship Streamline + DLSS-G. A game with only DLSS SR will not show an FG menu.
- OptiScaler `FGOutput=dlssg` requires `OptiScaler/streamline/sl.interposer.dll`, `sl.common.dll`, `sl.dlss_g.dll`, `sl.reflex.dll`, `sl.pcl.dll`, and `nvngx_dlssg.dll`.
- `AmpereMfgUnlock=true` requires `OptiScaler/dlssg_sm86/dlssg_sm86.dll` on SM86. If the folder is missing, the unlock does nothing.
- On Linux use `AmpereMfgKernelImage=ptx`, not `Cubin`.
- `AmpereMfgMaxFrames=3` advertises up to 4x. For 6x use the Combo path, or the standalone 0.4.0 payload with `MaxGeneratedFrames=5` and OptiScaler FG disabled.
- 6x cannot be forced in a game whose Streamline/DLSS-G plugin only supports 4x; use 4x. The standalone 0.4.0 backend is Windows/D3D12 and may fail under Proton with `Missing cuInit`; fall back to OptiScaler PTX 2x-4x.
- The game may hide MFG behind its own menu; enable DLSS-G there first.

## FG stutters, tears, or feels worse

- Base FPS below ~40 makes FG feel bad. Lower settings or resolution first.
- Enable Reflex in-game, or `[fakenvapi] ForceReflex=2` if there is no toggle.
- Keep `UseGamesReflexMarkers=auto`; forcing markers can desync pacing.
- Try `AllowedFrameAhead=1`.
- Disable V-Sync and cap below monitor refresh with Reflex.
- For Combo/FSR FG, expect more artifacts around UI and fast camera motion. It is not native DLSS MFG.

## VRAM exhaustion

Symptoms: stutter after a few minutes, driver reset, `nvidia-smi` shows ~8 GB, `Xid` in `dmesg`.

- Drop NR `Passes` to 1.
- Lower `WorkingScale` below 1.0.
- Turn off RT or lower RT resolution.
- Use DLSS Performance instead of Quality.
- Reduce FG multiplier; 6x adds buffers.
- Close browser/recording apps.
- At 1440p, NR + high RT + FG is usually over budget on 8 GB.

## ReShade does not load

- Confirm the addon build, not the standard build.
- `dxgi.dll` may be owned by another mod. Rename the other proxy or choose a different API slot.
- Check `ReShade.log` for "addon" and effect compile errors.
- Add `AddonSearchPaths=.\\` and the shader paths in `ReShade.ini`.
- On DX9, confirm ReShade moved to `dxgi.dll` and dgVoodoo owns `d3d9.dll`.
- 32-bit games need `dlss5-feed.addon32` and the `host64` side-by-side layout.

## Vulkan layer does not load

- `VKLayer_DLSS5=1` is required; the layer is disabled without it.
- `dlssnr-helper status` and `dlssnr-helper doctor`.
- Check `~/.config/environment.d/dlssnr.conf`; log out/in after install.
- `VK_INSTANCE_LAYERS` must include `VK_LAYER_NV_dlssnr:VK_LAYER_NV_present`.
- Steam pressure-vessel: keep shared memory in `/tmp`; do not point `DLSSNR_SHM` at a private `XDG_RUNTIME_DIR`.
- Stale state: `rm -f /tmp/dlssnr_shm.bin; rm -rf "${XDG_RUNTIME_DIR:-/nonexistent}/dlssnr"`, then restart the helper.
- Use Proton-CachyOS/GE with DXVK-NVAPI, not a Proton build without it.

## NPI has no effect

NPI edits the Windows NVIDIA driver profile through NVAPI. Under Wine it sees the prefix's NVAPI, not the Linux host driver. If the prefix lacks `nvapi64.dll`, NPI cannot do anything. Use in-game settings or OptiScaler instead. Do not expect `nvidia-settings` to reflect NPI changes.

## Anti-cheat

If the game uses EAC/BattlEye, remove all proxies and ReShade/OptiScaler files and verify the game. Do not attempt to bypass. The skill is for single-player only.

## Portable game problems

| Symptom | Fix |
|---|---|
| `No executable found` | Pass `--exe` with the real game binary, not a launcher/repack stub |
| `Proton prefix not found` | Pass `--prefix`, set `WINEPREFIX`, or add the exe as a non-Steam game with Proton-CachyOS |
| Prefix has no `nvngx.dll` | Use Proton-CachyOS/UMU, or plain Wine with `winetricks dxvk dxvk_nvapi` plus the driver NGX files |
| Game cannot write saves | Keep the portable folder writable; avoid read-only NTFS mounts |
| Upstream preflight fails | Network/rate limit; continue with the cached check or `--no-update-check` |
| `OnlineFix` present | Stop. Do not install proxies or ReShade. |

## GPU Unlock (optional)

- Not loaded: check `gpu_unlock.targets=` in `/proc/cmdline`; the module is opt-in.
- Missing after install: `sudo make install`, regenerate the initramfs, reboot.
- Secure Boot: may reject the unsigned module; sign/enroll it or disable Secure Boot; check `mokutil --sb-state`.
- Boot failure: boot the previous entry, remove `gpu_unlock.targets=`, regenerate.
- Hibernation is not covered; suspend/resume is supported.
- No FPS gain expected: compute unlock, not DLSS/tensor cores.

## Rollback

```bash
python3 assets/nvidia-stack.py rollback <appid>
```

The script restores files recorded in the manifest and removes files it created. If the manifest is lost, backups are under `~/.local/share/nvidia-stack/backups/<appid>/`. Restore the newest set manually, then verify the game in Steam.

After rollback:
- delete `OptiScaler.log`, `ReShade.log`, `dlssnr-capture/`
- remove launch options
- confirm `nvngx_dlss.dll` is the game's original
