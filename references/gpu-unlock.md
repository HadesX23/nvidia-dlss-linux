# GPU Unlock (optional compute unlock)

`Zagitta/gpu-unlock` is a Linux kernel module, **not a DLSS mod**. It unlocks
the FP/BF16 FMA issue rate on GA102/GA103/GA104/GA106 to the professional
equivalents. It does not add DLSS SR/RR/FG/NR, tensor cores, or path tracing.

Do not install it expecting a DLSS or FPS win. It changes compute issue rate;
games only benefit when they are limited by that path. Measure before and after.
Never enable it automatically; treat it as an explicit, system-level opt-in.

## What it changes

- Writes speed selectors SS0 `0x88888888` (full BF16 rate) and SS1 `0x8`
  (IMLA4) before the unmodified NVIDIA driver binds.
- Performs an FLR before `nvidia` loads; no patched driver, no UEFI app.
- Doubles FP/BF16 FMA issue speed into FP32 on GA102/103/104/106.
- RTX 3060 Ti is GA104 and is covered by 1.1.0.
- It does **not** unlock tensor cores, DLSS, frame generation, or RT cores.

Reference numbers from the project (RTX 3090 Ti, not a 3060 Ti): FP16
87.46 -> 118.39 TFLOPS, BF16 87.50 -> 157.41 TFLOPS, TF32 42.58 -> 82.61
TFLOPS. Treat these as compute benchmarks, not game FPS.

## Requirements

- Linux, kernel headers, initramfs tooling, and a reboot.
- An Ampere GA102/GA103/GA104/GA106 card. Turing/Ada forks exist but are not
  part of 1.1.0 and are not covered here.
- Secure Boot: the module is unsigned; sign it or disable Secure Boot, or it
  will not load.
- Hibernation is not covered. Suspend/resume is supported; use
  `gpu_unlock.resume=0` to disable the resume path.

## Install

```bash
git clone https://github.com/Zagitta/gpu-unlock
cd gpu-unlock
sudo make install
```

Add the opt-in to the kernel command line: `gpu_unlock.targets=all`, or a
comma-separated list of full PCI addresses from `lspci -D`.

Arch/CachyOS examples:

```bash
# GRUB
sudoedit /etc/default/grub
# append gpu_unlock.targets=all to GRUB_CMDLINE_LINUX_DEFAULT
sudo grub-mkconfig -o /boot/grub/grub.cfg

# systemd-boot: append to the options line in the loader entry
# UKI: append to /etc/kernel/cmdline, then:
sudo mkinitcpio -P
```

Reboot. The module must load before `nvidia`; the packaging installs it into
the initramfs. Without `gpu_unlock.targets=` it does nothing.

## Verify

```bash
journalctl -k -b | grep gpu_unlock
cat /proc/cmdline | tr ' ' '\n' | grep gpu_unlock
lspci -nnk -s 0000:01:00.0
```

`doctor` also reports `GPU Unlock (optional)` when `modinfo` is available.

## Disable or remove

Remove `gpu_unlock.targets=` from the kernel command line and reboot. Removing
the packages also removes the module and initramfs drop-ins. Keep a known-good
boot entry before changing the command line.

## Risks

- Kernel module and initramfs changes; a bad entry can prevent boot.
- Unsigned module/Secure Boot conflict.
- Possible heat/power changes and workload-specific instability.
- Proprietary firmware remains under NVIDIA terms; the module/packaging is
  GPL-2.0-only.
- No Windows support and no official NVIDIA support.

## Skill integration

- `doctor` checks module presence and the kernel command line.
- `update-check` tracks the latest commit because the project has no releases
  or tags. Preflight skips it when the module is not installed, so it does not
  nag on every game.
- `plan`/`install` never enable or install it. It is a separate system change,
  not a game route.
