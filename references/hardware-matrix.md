# Hardware matrix — RTX 3060 Ti 8 GB

Target: NVIDIA GeForce RTX 3060 Ti, GA104, SM86, 8 GB GDDR6, 448 GB/s, driver 615.78.08 on CachyOS/Omarchy. This is an Ampere card: strong tensor and RT hardware, but no native DLSS Frame Generation and no native Multi Frame Generation.

## Feature capability

| Feature | On this card | How |
|---|---|---|
| DLSS Super Resolution | Native | Game option plus current `nvngx_dlss.dll` (310.9.x or newer) |
| DLAA | Native | DLSS at 100% render scale; same DLL |
| DLSS Ray Reconstruction | Native if game supports it | Game option plus `nvngx_dlssd.dll`; no universal injector |
| NVIDIA Reflex | Native | Game option; also required by DLSS FG |
| DLSS Frame Generation | Not native | Modded SM86 DLSS-G kernels, or FSR FG replacement |
| DLSS Multi Frame Generation x2–x4 | Not native | `AmpereMfgUnlock` with `dlssg_sm86`; modded |
| DLSS MFG x5–x6 | Not native | Standalone `dlssg_sm86` 0.4.0 (`MaxGeneratedFrames=5`, Windows/D3D12; Proton experimental) or FSR FG Combo; only if the game supports 6x |
| DLSS 5 Neural Rendering | Usable | Leaked `nvngx_dlssnr.dll`, NGX feature 18, RTX 20/30/40 compatibility runtime |
| Ray Tracing | Native only | DXR path must exist in the game |
| Path Tracing | Native or RTX Remix only | Cannot be injected into an arbitrary renderer |
| Live Flow desktop FG | Usable | SM86 compatibility worker, up to 5 generated frames |

Native DLSS FG/MFG is an RTX 40/50 feature. Any x6 result on this GPU is **modded**, not NVIDIA-certified MFG. Say so in every report.

## What actually helps on 8 GB

| Tech | FPS | VRAM | Reality |
|---|---|---|---|
| DLSS SR | + | usually lower | Biggest reliable win; it lowers internal render resolution, not texture pressure |
| Ray Reconstruction | + for RT | neutral | Replaces RT denoisers where the game supports it |
| Reflex | latency down | neutral | Does not raise FPS or free VRAM |
| FG 2x | displayed FPS up | +~350 MiB at 1080p, +~540 MiB at 1440p, +~810 MiB at 4K | Base simulation rate is unchanged |
| FG 4x/6x | displayed FPS up more | similar to 2x | Needs game support; adds GPU time and latency |
| DLSS 5 NR | costs | costs | Neural post-process, not a performance feature |
| DLAA | costs | neutral | Native-resolution AA; use only with headroom |

Frame Generation raises the displayed frame rate but not the base render rate. At 8 GB, reduce textures, RT, or output resolution before adding NR or a higher FG multiplier. The 0.4.0 README reports FG VRAM depends on output resolution, not multiplier; that does not make 6x free.

## VRAM budget (8 GB)

These are planning numbers, not guarantees. Measure with Mangohud and `nvidia-smi`.

| Target | DLSS SR | RT | NR | FG | Expected VRAM |
|---|---|---|---|---|---|
| 1080p, DLSS Quality | yes | off/medium | 1 pass | 2x | 5.5–7 GB |
| 1080p, DLSS Quality | yes | medium | 1 pass | 4x | 6–7.5 GB |
| 1440p, DLSS Performance | yes | medium | 1 pass | 2x | 6.5–8 GB |
| 1440p, DLSS Quality | yes | high | 2 passes | 4x | likely over 8 GB |
| 4K | any | any | any | any | not recommended |

Rules:
- Start NR with `Passes=1` and `WorkingScale=1.0`. Raise passes only after measuring.
- `Precision=0` (NVIDIA FP8) is the intended RTX 30 path. Do not use the Blackwell FP8+NVFP4 mode (`Precision=4`).
- FG costs VRAM and does not fix a CPU bottleneck. If base FPS is below ~40, FG will feel bad.
- At 8 GB, prefer 1080p for NR + RT + FG. At 1440p drop RT or NR passes.

## The three x6 routes

1. **SM86 DLSS-G unlock** — `AmpereMfgUnlock=true` in `[DLSSG]`, bundled `OptiScaler/dlssg_sm86/` 0.2.3, `AmpereMfgMaxFrames=3`, `AmpereMfgKernelImage=ptx` on Linux. This uses the game's DLSS-G path and is the closest to native, but caps at 4x. For 6x, the standalone `sdli1995/dlssg_for_sm86` 0.4.0 release is a separate `version.dll` proxy plus `dlssg_sm86/` folder beside the EXE; it is not an OptiScaler plugin and must not run with OptiScaler FG enabled. It is Windows x64/D3D12; under Proton an open `Missing cuInit` issue can block the backend, so treat it as experimental and keep 2x-4x PTX as the Linux fallback. A game whose plugin only supports 4x cannot be forced to 6x.
2. **FSR FG Combo** — `FGNvngxReplacement=Combo`, `FGOutput=fsrfg`, `InterpolationCount=5`. Uses FidelityFX middle frames plus the Enabler for the rest. Works on games without DLSS-G but is the most artifact-prone and least latency-friendly route.
3. **Live Flow / NeuralScreen** — desktop-capture frame generation in `mod files/native`, `dlssg_compat` 0.3.5 for SM86. This is not in-game FG: it captures the composited desktop/game window and inserts frames. Useful for games with no FG path, but it cannot use engine depth or HUD-free color, and it adds latency.

Do not use `RTX40MFG-Unlock` on this card. It is an RTX 40 external unlock, not an Ampere FG provider.

## What "native" means in this skill

- `native` route = refresh DLLs in a game that already ships DLSS, without adding a proxy or injector.
- `optiscaler` = add or replace upscaling/FG/NR through OptiScaler.
- `reshade` = ReShade addon path for DX11/DX9 or when OptiScaler cannot hook.
- `vulkan` = DLSS5VKLayer, NR only, for Vulkan-native or Proton Vulkan games.
