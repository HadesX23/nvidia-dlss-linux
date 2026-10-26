#!/usr/bin/env python3
"""NVIDIA gaming stack helper for Linux/Proton.

Routes: native DLL refresh, OptiScaler (DX12/DX11/Vulkan), ReShade addons,
DLSS5VKLayer (Vulkan NR). Resolves Steam games and portable folders/exes.
Target: RTX 3060 Ti 8 GB on CachyOS/Omarchy. Plan/install preflight upstream.

The script never edits a game before recording a backup and a JSON manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ASSET_ROOT = Path.home() / "Software" / "NVIDIA"
ASSET_ROOT = Path(os.environ.get("NVIDIA_STACK_ASSETS", DEFAULT_ASSET_ROOT)).expanduser()
MANAGER_ROOT = ASSET_ROOT / "Juegos sin DLSS Nativos" / "DLSS5 Manager" / "DLSS.5.MANAGER"
MOD_ROOT = MANAGER_ROOT / "mod files"
OPTISCALER_SRC = MOD_ROOT / "if OptiScaler neural-upstream"
RESHADE_SRC = MOD_ROOT / "reshade-shaders"
DLSS_SRC = MOD_ROOT / "streamline_dlss" / "dlss"
STREAMLINE_SRC = MOD_ROOT / "streamline_dlss" / "streamline"
NR_SRC = MOD_ROOT / "dlss 5"
NR_DLL = NR_SRC / "nvngx_dlssnr.dll"
RESHADE_SETUP = MOD_ROOT / "ReShade_Setup_6.8.0_Addon.exe"
STATE_ROOT = Path(os.environ.get("NVIDIA_STACK_STATE", Path.home() / ".local/share/nvidia-stack")).expanduser()
BACKUP_ROOT = STATE_ROOT / "backups"
MANIFEST_ROOT = STATE_ROOT / "manifests"

SKIP_DIRS = {
    ".git", "__pycache__", "redist", "redistributables", "_commonredist",
    "support", "thirdparty", "easyanticheat", "battleye", "crashreporter",
    "crashreport", "benchmark", "tools", "editor", "sdk", "docs",
}
SKIP_EXE_PARTS = (
    "unins", "setup", "install", "vc_redist", "vcredist", "dxsetup", "dxwebsetup",
    "dotnet", "crash", "report", "touchup", "prereq", "eac", "battleye",
    "launcher", "config", "benchmark", "editor", "server",
)
PROXY_ORDER_DX = ["dxgi.dll", "winmm.dll", "version.dll", "dbghelp.dll",
                  "d3d12.dll", "wininet.dll", "winhttp.dll", "OptiScaler.asi"]
PROXY_ORDER_VK = ["winmm.dll", "version.dll", "dxgi.dll", "dbghelp.dll",
                  "d3d12.dll", "wininet.dll", "winhttp.dll", "OptiScaler.asi"]


class SkillError(RuntimeError):
    pass


@dataclass
class Game:
    appid: str
    name: str
    library: Path
    path: Path
    prefix: Path | None = None
    exe: Path | None = None
    api: str = "unknown"
    arch: str = "unknown"
    portable: bool = False


@dataclass
class Plan:
    game: dict[str, Any]
    route: str
    api: str
    proxy: str | None
    fg: str
    fg_mode: str
    nr: str
    launch_options: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mods: dict[str, Any] = field(default_factory=dict)


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def human_bytes(n: int | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} TB"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)


def which(name: str) -> str | None:
    return shutil.which(name)


def parse_library_paths(vdf: Path) -> list[Path]:
    try:
        text = vdf.read_text(errors="replace")
    except OSError:
        return []
    paths = []
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        p = m.group(1).replace("\\\\", "\\")
        paths.append(Path(p))
    return paths


def steam_libraries() -> list[Path]:
    roots = [
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        Path("/usr/share/steam"),
    ]
    env_root = os.environ.get("STEAM_ROOT")
    if env_root:
        roots.insert(0, Path(env_root))
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        if (root / "steamapps").is_dir():
            found[str(root.resolve())] = root
        vdf = root / "steamapps" / "libraryfolders.vdf"
        for p in parse_library_paths(vdf):
            if (p / "steamapps").is_dir():
                found[str(p.resolve())] = p
    return sorted(found.values(), key=lambda p: str(p))


def appmanifest_games() -> list[Game]:
    games_by_id: dict[str, Game] = {}
    skip_names = {
        "Steamworks Common Redistributables",
        "Proton Experimental",
        "Proton Hotfix",
    }
    for lib in steam_libraries():
        steamapps = lib / "steamapps"
        if not steamapps.is_dir():
            continue
        for acf in sorted(steamapps.glob("appmanifest_*.acf")):
            text = acf.read_text(errors="replace")
            appid = re.search(r'"appid"\s+"([^"]+)"', text)
            name = re.search(r'"name"\s+"([^"]+)"', text)
            installdir = re.search(r'"installdir"\s+"([^"]+)"', text)
            if not appid or not name:
                continue
            if name.group(1) in skip_names or name.group(1).startswith("Steam Linux Runtime"):
                continue
            if appid.group(1) in games_by_id:
                continue
            game_path = steamapps / "common" / (installdir.group(1) if installdir else name.group(1))
            if not game_path.is_dir():
                continue
            prefix = None
            for plib in steam_libraries():
                candidate = plib / "steamapps" / "compatdata" / appid.group(1) / "pfx"
                if candidate.is_dir():
                    prefix = candidate
                    break
            games_by_id[appid.group(1)] = Game(appid.group(1), name.group(1), lib, game_path, prefix)
    return sorted(games_by_id.values(), key=lambda g: g.name.lower())


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def elf_arch(path: Path) -> str:
    try:
        with path.open("rb") as f:
            head = f.read(6)
        if len(head) < 6 or head[:4] != b"\x7fELF":
            return "unknown"
        return "x64" if head[4] == 2 else "x86" if head[4] == 1 else "unknown"
    except OSError:
        return "unknown"


def pe_arch(path: Path) -> str:
    try:
        with path.open("rb") as f:
            head = f.read(0x400)
            if len(head) < 0x40 or head[:2] != b"MZ":
                return elf_arch(path)
            off = struct.unpack_from("<I", head, 0x3C)[0]
            f.seek(off)
            sig = f.read(6)
            if len(sig) < 6 or sig[:4] != b"PE\0\0":
                return "unknown"
            machine = struct.unpack_from("<H", sig, 4)[0]
            return "x64" if machine == 0x8664 else "x86" if machine == 0x14C else "unknown"
    except OSError:
        return "unknown"


def pe_imports(path: Path) -> set[str]:
    names: set[str] = set()
    if which("objdump"):
        try:
            out = run(["objdump", "-p", str(path)], timeout=20).stdout
            names.update(m.group(1).lower() for m in re.finditer(r"DLL Name:\s*([^\s]+)", out))
        except Exception:
            pass
    if not names:
        try:
            with path.open("rb") as f:
                data = f.read(16 * 1024 * 1024)
            names.update(m.group(0).decode("ascii", "ignore").lower()
                         for m in re.finditer(rb"[A-Za-z0-9_.+-]+\.dll", data))
        except OSError:
            pass
    return names


def detect_api(exe: Path) -> str:
    if is_elf(exe):
        blobs = [exe]
        for name in ("UnityPlayer.so", "libvulkan.so.1", "libGL.so.1"):
            p = exe.parent / name
            if p.exists():
                blobs.append(p)
        data = b""
        for p in blobs:
            try:
                with p.open("rb") as f:
                    data += f.read(16 * 1024 * 1024)
            except OSError:
                pass
        if b"libvulkan.so" in data or b"vkCreateInstance" in data:
            return "vulkan"
        if b"libGL.so" in data or b"glXCreateContext" in data:
            return "opengl"
        return "unknown"

    imports = pe_imports(exe)
    unity = exe.parent / "UnityPlayer.dll"
    if unity.exists():
        imports |= pe_imports(unity)
    if "unityplayer.dll" in imports:
        for sibling in (exe.parent / "GameAssembly.dll", exe.parent / "baselib.dll"):
            if sibling.exists():
                imports |= pe_imports(sibling)
    if "d3d12.dll" in imports:
        return "dx12"
    if "vulkan-1.dll" in imports:
        return "vulkan"
    if "d3d11.dll" in imports:
        return "dx11"
    if "d3d9.dll" in imports:
        return "dx9"
    if "dxgi.dll" in imports:
        return "dx11"
    if "opengl32.dll" in imports:
        return "opengl"
    return "unknown"


def score_exe(p: Path, root: Path) -> int:
    name = p.stem.lower()
    score = 0
    if name == root.name.lower() or name in root.name.lower():
        score += 60
    if p.parent.name.lower() in {"win64", "win32", "binaries", "bin", "x64", "game"}:
        score += 20
    if "shipping" in name:
        score += 15
    if "launcher" in name:
        score -= 40
    if any(part in name for part in SKIP_EXE_PARTS):
        score -= 60
    try:
        size = p.stat().st_size
        score += 20 if size > 10_000_000 else 10 if size > 1_000_000 else 0
    except OSError:
        pass
    score += max(0, 10 - len(p.relative_to(root).parts))
    if pe_arch(p) == "x64":
        score += 5
    return score


def find_exe(root: Path) -> Path | None:
    candidates: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= 5:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if fn.lower().endswith(".exe"):
                candidates.append(p)
            elif (os.access(p, os.X_OK) and p.stat().st_size > 1024 and is_elf(p)
                  and not fn.endswith((".so", ".so.1")) and ".so." not in fn):
                candidates.append(p)
        if len(candidates) > 3000:
            break
    candidates = [p for p in candidates if not any(x in p.name.lower() for x in SKIP_EXE_PARTS)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: score_exe(p, root), reverse=True)
    return candidates[0]


def scan_mods(root: Path) -> dict[str, Any]:
    names = {
        "dlss_sr": "nvngx_dlss.dll",
        "dlss_fg": "nvngx_dlssg.dll",
        "dlss_rr": "nvngx_dlssd.dll",
        "dlss_nr": "nvngx_dlssnr.dll",
        "streamline": "sl.interposer.dll",
        "optiscaler": "OptiScaler.ini",
        "optiscaler_dll": "OptiScaler.dll",
        "reshade": "ReShade.ini",
        "sm86": "dlssg_sm86.dll",
    }
    found: dict[str, Any] = {}
    for key, name in names.items():
        matches = []
        try:
            for p in root.rglob(name):
                if p.is_file():
                    matches.append(str(p))
                    if len(matches) >= 5:
                        break
        except OSError:
            pass
        found[key] = matches
    ac = []
    for pattern in ("EasyAntiCheat", "BattlEye", "start_protected_game.exe", "EACLauncher.exe",
                    "OnlineFix*", "onlinefix*"):
        try:
            ac.extend(str(p) for p in root.rglob(pattern) if p.exists())
        except OSError:
            pass
    found["anticheat"] = ac[:5]
    return found


def portable_id(root: Path) -> str:
    resolved = root.resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "game"
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:8]
    return f"portable-{slug[:40]}-{digest}"


def normalize_prefix(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value).expanduser()
    if (p / "drive_c").is_dir():
        return p
    if (p / "pfx" / "drive_c").is_dir():
        return p / "pfx"
    return p


def resolve_game(query: str, exe_override: str | None = None,
                 prefix_override: str | None = None) -> Game:
    games = appmanifest_games()
    q = query.strip()
    chosen: Game | None = None
    if q.isdigit():
        chosen = next((g for g in games if g.appid == q), None)
    else:
        p = Path(q).expanduser()
        if p.exists():
            for g in games:
                try:
                    p.relative_to(g.path)
                    chosen = g
                    break
                except ValueError:
                    continue
            if chosen is None:
                if p.is_file() and p.suffix.lower() == ".exe":
                    root = p.parent
                    explicit_exe = p
                elif p.is_dir():
                    root = p
                    explicit_exe = None
                else:
                    raise SkillError(f"Path is not a game directory or .exe: {p}")
                chosen = Game(portable_id(root), root.name, root.parent, root,
                              None, explicit_exe, portable=True)
            elif p.is_file() and p.suffix.lower() == ".exe":
                chosen.exe = p
        if chosen is None:
            matches = [g for g in games if q.lower() in g.name.lower()]
            if len(matches) == 1:
                chosen = matches[0]
            elif len(matches) > 1:
                log("Multiple games match:")
                for g in matches[:20]:
                    log(f"  {g.appid}  {g.name}")
                raise SkillError("Use an appid or a more specific name.")
    if chosen is None:
        raise SkillError(f"Game not found: {query}")

    prefix = normalize_prefix(prefix_override)
    if prefix is None and chosen.portable:
        env_prefix = os.environ.get("WINEPREFIX")
        if env_prefix:
            prefix = normalize_prefix(env_prefix)
        elif (Path.home() / ".wine" / "drive_c").is_dir():
            prefix = Path.home() / ".wine"
    if prefix is not None:
        chosen.prefix = prefix

    if exe_override:
        exe = Path(exe_override).expanduser()
        if not exe.is_absolute():
            exe = chosen.path / exe
        if not exe.exists():
            raise SkillError(f"Executable not found: {exe}")
        chosen.exe = exe
    elif not chosen.exe:
        chosen.exe = find_exe(chosen.path)
    if chosen.exe:
        chosen.api = detect_api(chosen.exe)
        chosen.arch = pe_arch(chosen.exe)
    return chosen


def choose_proxy(exe_dir: Path, api: str) -> str:
    order = PROXY_ORDER_VK if api == "vulkan" else PROXY_ORDER_DX
    source_size = (OPTISCALER_SRC / "OptiScaler.dll").stat().st_size if (OPTISCALER_SRC / "OptiScaler.dll").exists() else -1
    for name in order:
        p = exe_dir / name
        if not p.exists():
            return name
        try:
            if source_size > 0 and p.stat().st_size == source_size:
                return name
        except OSError:
            pass
    raise SkillError("No free proxy slot next to the executable.")


def decide_route(game: Game, requested: str, mods: dict[str, Any]) -> str:
    if requested != "auto":
        return requested
    if mods.get("anticheat"):
        raise SkillError("Anti-cheat detected; refusing to install.")
    if game.exe and game.exe.suffix.lower() != ".exe":
        return "vulkan" if game.api == "vulkan" else "reshade"
    if game.api == "dx12":
        return "optiscaler"
    if game.api == "vulkan":
        return "optiscaler"
    if game.api in ("dx11", "dx9"):
        return "reshade"
    return "reshade"


def make_plan(game: Game, route: str, fg: str, fg_mode: str, nr: str) -> Plan:
    mods = scan_mods(game.path)
    route = decide_route(game, route, mods)
    warnings: list[str] = []
    if mods.get("anticheat"):
        raise SkillError("Anti-cheat files found; this skill only handles single-player games.")
    if game.api == "unknown":
        warnings.append("Graphics API not detected; verify the executable before installing.")
    if game.portable:
        if not game.prefix:
            warnings.append("Portable game: no Wine/Proton prefix. Pass --prefix <pfx> or launch once with Proton-CachyOS/umu-run.")
        elif not (game.prefix / "drive_c").is_dir():
            warnings.append("Prefix path has no drive_c; pass the actual Wine/Proton prefix directory.")
        else:
            sys32 = game.prefix / "drive_c" / "windows" / "system32"
            if not (sys32 / "nvngx.dll").exists():
                warnings.append("Prefix lacks nvngx.dll; use Proton-CachyOS/umu-run or install DXVK-NVAPI and the NVIDIA Wine NGX runtime.")
            if not (sys32 / "nvapi64.dll").exists():
                warnings.append("Prefix lacks nvapi64.dll; DXVK-NVAPI is not initialized in this prefix.")
    elif not game.prefix and game.exe and game.exe.suffix.lower() == ".exe":
        warnings.append("Proton prefix not found; launch the game once with Proton before installing.")
    if route == "native" and not mods.get("dlss_sr"):
        warnings.append("No nvngx_dlss.dll found; native route has nothing to refresh. Use optiscaler or reshade.")
    if route == "native" and nr == "on":
        warnings.append("Native route cannot add Neural Rendering; use optiscaler or reshade.")
    if route == "optiscaler" and game.api == "dx9":
        warnings.append("DX9 is not an OptiScaler target; use the reshade route.")
    if route == "reshade" and fg != "off":
        warnings.append("ReShade addons do not add in-game FG on RTX 30; use optiscaler for FG.")
    if route == "vulkan":
        if fg != "off":
            warnings.append("DLSS5VKLayer is NR-only; it does not add FG.")
        if not which("dlssnr-helper"):
            warnings.append("dlssnr-helper is not installed; install DLSS5VKLayer first.")
    if fg == "6x":
        warnings.append("6x uses the experimental FSR FG Combo path and needs dlss-enabler-headless.dll (not in the 0.9.4 installer); "
                        "the standalone dlssg_sm86 0.4.0 route is manual and not mixed with OptiScaler FG.")
    if fg != "off" and game.arch == "x86":
        warnings.append("32-bit game: FG/NR addons need the host64 side-by-side layout.")
    if nr == "on":
        warnings.append("NR: start at 1080p/1440p, Passes=1, and watch the 8 GB VRAM budget.")
    if route == "optiscaler" and game.api == "dx11":
        warnings.append("DX11 NR needs Dx11Upscaler=dlss_12.")
    proxy = choose_proxy(game.exe.parent, game.api) if route == "optiscaler" and game.exe else None

    launch: list[str] = []
    if route == "optiscaler":
        launch.append('DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" MANGOHUD=1 %command%')
        if proxy and proxy != "dxgi.dll":
            launch.append(f'# if the proxy does not load: WINEDLLOVERRIDES="{proxy}=n,b" %command%')
    elif route == "vulkan":
        launch.append("VKLayer_DLSS5=1 MANGOHUD=1 %command%")
    elif route == "reshade":
        launch.append("MANGOHUD=1 %command%")
    elif route == "native":
        launch.append('DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" %command%')

    if game.portable and game.exe and game.exe.suffix.lower() == ".exe":
        env = ""
        if route in ("optiscaler", "native"):
            env = 'DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS="DLSSIndicator=1024,DLSSGIndicator=2" '
        if route == "vulkan":
            env = "VKLayer_DLSS5=1 "
        launch = []
        if game.prefix:
            launch.append(f'{env}WINEPREFIX="{game.prefix}" wine "{game.exe}"')
            launch.append("# or add the .exe as a non-Steam game and force Proton-CachyOS")
        else:
            launch.append(f'{env}GAMEID=0 PROTONPATH="<proton-cachyos-dir>" umu-run "{game.exe}"')
            launch.append("# or add the .exe as a non-Steam game and force Proton-CachyOS")
        if proxy and proxy != "dxgi.dll":
            launch.append(f'# if the proxy does not load: WINEDLLOVERRIDES="{proxy}=n,b"')

    game_data = asdict(game)
    for key in ("library", "path", "prefix", "exe"):
        if game_data.get(key) is not None:
            game_data[key] = str(game_data[key])
    return Plan(game_data, route, game.api, proxy, fg, fg_mode, nr, launch, warnings, mods)


def print_plan(plan: Plan) -> None:
    g = plan.game
    log(f"Game:     {g['name']} ({g['appid']})")
    log(f"Path:     {g['path']}")
    log(f"Portable: {'yes' if g.get('portable') else 'no'}")
    log(f"Prefix:   {g['prefix'] or 'not found'}")
    log(f"Exe:      {g['exe'] or 'not found'}  [{g['api']}, {g['arch']}]")
    log(f"Route:    {plan.route}")
    if plan.proxy:
        log(f"Proxy:    {plan.proxy}")
    log(f"NR:       {plan.nr}   FG: {plan.fg} ({plan.fg_mode})")
    log("Launch options:")
    for line in plan.launch_options:
        log(f"  {line}")
    if plan.warnings:
        log("Warnings:")
        for w in plan.warnings:
            log(f"  - {w}")


class Tracker:
    def __init__(self, game: Game, route: str):
        self.game = game
        self.route = route
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.backup_dir = BACKUP_ROOT / game.appid / stamp
        self.manifest_path = MANIFEST_ROOT / game.appid / f"{stamp}.json"
        self.files: list[dict[str, Any]] = []
        self.dirs: list[str] = []
        self._seen: set[str] = set()
        self.created = stamp

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.game.path))
        except ValueError:
            return "_external" / path.name

    def ensure_dir(self, path: Path) -> None:
        missing: list[Path] = []
        probe = path
        while not probe.exists() and probe != probe.parent:
            missing.append(probe)
            probe = probe.parent
        for created in reversed(missing):
            if str(created) not in self.dirs:
                self.dirs.append(str(created))
        path.mkdir(parents=True, exist_ok=True)

    def record(self, path: Path) -> dict[str, Any]:
        key = str(path)
        if key in self._seen:
            return next(f for f in self.files if f["path"] == key)
        self._seen.add(key)
        entry: dict[str, Any] = {"path": key, "existed": False, "backup": None, "sha256": None}
        if path.exists() or path.is_symlink():
            rel = self._rel(path)
            backup = self.backup_dir / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                entry["link"] = os.readlink(path)
                entry["existed"] = True
                entry["backup"] = None
            else:
                shutil.copy2(path, backup)
                entry["existed"] = True
                entry["backup"] = str(backup)
                entry["sha256"] = sha256(path)
        self.files.append(entry)
        return entry

    def copy(self, src: Path, dst: Path) -> None:
        self.ensure_dir(dst.parent)
        entry = self.record(dst)
        shutil.copy2(src, dst)
        entry["sha256_new"] = sha256(dst)

    def move(self, src: Path, dst: Path) -> None:
        self.ensure_dir(dst.parent)
        entry = self.record(dst)
        shutil.move(str(src), str(dst))
        entry["sha256_new"] = sha256(dst) if dst.exists() else None

    def write_text(self, dst: Path, text: str) -> None:
        self.ensure_dir(dst.parent)
        entry = self.record(dst)
        dst.write_text(text, encoding="utf-8")
        entry["sha256_new"] = sha256(dst)

    def copy_tree(self, src_root: Path, dst_root: Path, exclude_dirs: Iterable[str] = ()) -> int:
        excluded = {x.lower() for x in exclude_dirs}
        count = 0
        for src in sorted(src_root.rglob("*")):
            if src.is_dir():
                continue
            rel = src.relative_to(src_root)
            if any(part.lower() in excluded for part in rel.parts):
                continue
            dst = dst_root / rel
            self.copy(src, dst)
            count += 1
        return count

    def save(self, plan: Plan, notes: list[str] | None = None) -> Path:
        payload = {
            "version": 1,
            "appid": self.game.appid,
            "name": self.game.name,
            "game_path": str(self.game.path),
            "exe": str(self.game.exe) if self.game.exe else None,
            "prefix": str(self.game.prefix) if self.game.prefix else None,
            "route": self.route,
            "api": self.game.api,
            "arch": self.game.arch,
            "proxy": plan.proxy,
            "fg": plan.fg,
            "fg_mode": plan.fg_mode,
            "nr": plan.nr,
            "created": self.created,
            "files": self.files,
            "dirs": self.dirs,
            "launch_options": plan.launch_options,
            "warnings": plan.warnings,
            "notes": notes or [],
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        latest = MANIFEST_ROOT / self.game.appid / "latest.json"
        latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.manifest_path


def patch_ini(path: Path, updates: dict[str, dict[str, str]], tracker: Tracker | None = None) -> None:
    text = path.read_text(errors="replace") if path.exists() else ""
    lines = text.splitlines()
    section_re = re.compile(r"^\s*\[([^\]]+)\]\s*$")
    key_re = lambda k: re.compile(r"^\s*" + re.escape(k) + r"\s*=", re.IGNORECASE)

    wanted: dict[str, tuple[str, dict[str, tuple[str, str]]]] = {}
    for section, values in updates.items():
        wanted[section.lower()] = (
            section,
            {k.lower(): (k, v) for k, v in values.items()},
        )

    def apply(body: list[str], values: dict[str, tuple[str, str]]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for line in body:
            match = next((k for k in values if key_re(values[k][0]).match(line)), None)
            if match is None:
                result.append(line)
                continue
            if match not in seen:
                key, value = values[match]
                result.append(f"{key}={value}")
                seen.add(match)
        for key, (original, value) in values.items():
            if key not in seen:
                result.append(f"{original}={value}")
        return result

    out: list[str] = []
    seen_sections: set[str] = set()
    i = 0
    while i < len(lines):
        header = section_re.match(lines[i])
        if not header:
            out.append(lines[i])
            i += 1
            continue
        name = header.group(1).strip()
        key = name.lower()
        out.append(lines[i])
        i += 1
        body: list[str] = []
        while i < len(lines) and not section_re.match(lines[i]):
            body.append(lines[i])
            i += 1
        if key in wanted:
            seen_sections.add(key)
            body = apply(body, wanted[key][1])
        out.extend(body)

    for key, (original, values) in wanted.items():
        if key in seen_sections:
            continue
        out.extend(["", f"[{original}]"])
        for _, value in values.values():
            out.append(f"{value[0]}={value[1]}")

    new_text = "\n".join(out).rstrip() + "\n"
    if tracker:
        tracker.write_text(path, new_text)
    else:
        path.write_text(new_text, encoding="utf-8")


def install_native(game: Game, plan: Plan, tracker: Tracker) -> list[str]:
    assert game.exe
    exe_dir = game.exe.parent
    notes: list[str] = []
    if game.prefix and not (game.prefix / "drive_c/windows/system32/nvngx.dll").exists():
        plan.warnings.append("Prefix lacks nvngx.dll; DLSS may not load. Fix Proton/NVAPI first.")
    sr_targets = list(exe_dir.rglob("nvngx_dlss.dll"))
    if not sr_targets:
        raise SkillError("No native nvngx_dlss.dll found. Use --route optiscaler or reshade.")
    for target in sr_targets:
        tracker.copy(DLSS_SRC / "nvngx_dlss.dll", target)
        notes.append(f"updated {target}")
    for target in exe_dir.rglob("nvngx_dlssg.dll"):
        tracker.copy(DLSS_SRC / "nvngx_dlssg.dll", target)
        notes.append(f"updated {target}")
    if list(exe_dir.rglob("nvngx_dlssd.dll")):
        notes.append("Ray Reconstruction DLL detected but not bundled; update it with DLSS Swapper or keep the game copy")
    if plan.fg != "off":
        notes.append("native route refreshed existing FG DLLs; it does not add FG to a game without DLSS-G")
    if plan.nr == "on":
        notes.append("native route cannot add NR; no nvngx_dlssnr.dll was deployed")
    return notes


def install_optiscaler(game: Game, plan: Plan, tracker: Tracker) -> list[str]:
    assert game.exe
    exe_dir = game.exe.parent
    if not (OPTISCALER_SRC / "OptiScaler.dll").exists():
        raise SkillError(f"OptiScaler payload missing: {OPTISCALER_SRC}")
    if not NR_DLL.exists():
        raise SkillError(f"DLSS 5 NR runtime missing: {NR_DLL}")
    if not plan.proxy:
        raise SkillError("No proxy slot available.")
    notes: list[str] = []
    tracker.ensure_dir(exe_dir / "OptiScaler")
    count = tracker.copy_tree(OPTISCALER_SRC / "OptiScaler", exe_dir / "OptiScaler",
                              exclude_dirs=("docs", "tests", ".git"))
    notes.append(f"copied {count} OptiScaler runtime files")

    ini = exe_dir / "OptiScaler.ini"
    if not ini.exists():
        tracker.copy(OPTISCALER_SRC / "OptiScaler.ini", ini)
    tracker.copy(OPTISCALER_SRC / "OptiScaler.dll", exe_dir / plan.proxy)
    tracker.copy(OPTISCALER_SRC / "nvngx.dll_dlssnr.dll", exe_dir / "nvngx.dll_dlssnr.dll")
    tracker.copy(NR_DLL, exe_dir / "nvngx_dlssnr.dll")
    if (DLSS_SRC / "nvngx_dlss.dll").exists():
        tracker.copy(DLSS_SRC / "nvngx_dlss.dll", exe_dir / "nvngx_dlss.dll")
    if (DLSS_SRC / "nvngx_dlssg.dll").exists():
        tracker.copy(DLSS_SRC / "nvngx_dlssg.dll", exe_dir / "nvngx_dlssg.dll")

    if plan.fg == "6x":
        enabler = exe_dir / "dlss-enabler-headless.dll"
        if not enabler.exists():
            enabler = STATE_ROOT / "vendor" / "dlss-enabler-headless.dll"
        if not enabler.exists():
            raise SkillError(
                "FSR FG Combo needs dlss-enabler-headless.dll. Use a DLSS Enabler build that ships dlss-enabler.asi and rename it, or use standalone dlssg_for_sm86 0.4.0. "
                f"Put the DLL in {exe_dir} or {STATE_ROOT / 'vendor'} and retry."
            )
        dst = exe_dir / "dlss-enabler-headless.dll"
        if enabler.resolve() != dst.resolve():
            tracker.copy(enabler, dst)

    streamline_dst = exe_dir / "OptiScaler" / "streamline"
    tracker.ensure_dir(streamline_dst)
    for name in ("sl.interposer.dll", "sl.common.dll", "sl.dlss.dll", "sl.dlss_g.dll",
                 "sl.reflex.dll", "sl.pcl.dll", "sl.nis.dll", "sl.nvperf.dll"):
        src = STREAMLINE_SRC / name
        if src.exists():
            tracker.copy(src, streamline_dst / name)
    for name in ("nvngx_dlss.dll", "nvngx_dlssg.dll"):
        src = DLSS_SRC / name
        if src.exists():
            tracker.copy(src, streamline_dst / name)
    notes.append(f"streamline -> {streamline_dst}")

    updates: dict[str, dict[str, str]] = {
        "Upscalers": {
            "Dx12Upscaler": "dlss",
            "Dx11Upscaler": "dlss_12" if game.api == "dx11" else "auto",
            "VulkanUpscaler": "dlss" if game.api == "vulkan" else "auto",
        },
        "DlssNr": {
            "Enabled": "true" if plan.nr == "on" else "false",
            "Precision": "0",
            "Passes": "1",
            "WorkingScale": "1.0",
            "FinishedPicture": "false",
            "DeferredDLSS": "auto",
            "UnlockPasses": "false",
            "AutoCapture": "true" if plan.nr == "on" else "false",
        },
        "FrameGen": {
            "Enabled": "false",
            "External": "false",
            "FGInput": "dlssg" if plan.mods.get("dlss_fg") else "upscaler",
            "FGOutput": "dlssg",
            "FGNvngxReplacement": "None",
        },
        "DLSSG": {
            "AmpereMfgUnlock": "false",
            "AmpereMfgMaxFrames": "3",
            "AmpereMfgKernelImage": "ptx",
            "InterpolationCount": "auto",
            "UseGamesReflexMarkers": "auto",
        },
        "fakenvapi": {"ForceReflex": "auto"},
    }
    if plan.fg in ("2x", "3x", "4x"):
        updates["FrameGen"]["External"] = "false"
        updates["FrameGen"]["FGOutput"] = "dlssg"
        updates["DLSSG"].update({
            "AmpereMfgUnlock": "true",
            "AmpereMfgMaxFrames": "3",
            "AmpereMfgKernelImage": "ptx",
            "InterpolationCount": {"2x": "1", "3x": "2", "4x": "3"}[plan.fg],
        })
    elif plan.fg == "6x":
        updates["FrameGen"].update({
            "External": "false",
            "FGInput": "upscaler",
            "FGOutput": "fsrfg",
            "FGNvngxReplacement": "Combo",
        })
        updates["DLSSG"].update({
            "AmpereMfgUnlock": "false",
            "InterpolationCount": "5",
        })
    patch_ini(ini, updates, tracker)
    notes.append(f"patched {ini}")
    if plan.fg == "off":
        notes.append("first launch: NR on, FG off")
    else:
        notes.append(f"FG {plan.fg} configured but disabled; after a clean first launch set [FrameGen] Enabled=true")
    return notes


def wine_path(p: Path) -> str:
    return "Z:" + str(p).replace("/", "\\")


def install_reshade(game: Game, plan: Plan, tracker: Tracker) -> list[str]:
    assert game.exe
    exe_dir = game.exe.parent
    api = {"dx12": "dx12", "dx11": "dx11", "dx9": "dx9", "vulkan": "vulkan"}.get(game.api, "dx12")
    notes: list[str] = []
    if not RESHADE_SETUP.exists():
        raise SkillError(f"ReShade setup missing: {RESHADE_SETUP}")
    wine = which("wine")
    installed = (exe_dir / "ReShade.ini").exists()
    if not installed and wine and game.prefix:
        env = os.environ.copy()
        env["WINEPREFIX"] = str(game.prefix)
        env["WINEDEBUG"] = "-all"
        cmd = [wine, str(RESHADE_SETUP), wine_path(game.exe), "--api", api, "--headless"]
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=180, env=env)
            installed = proc.returncode == 0 or (exe_dir / f"{api}.dll").exists() or (exe_dir / "ReShade.ini").exists()
            if not installed:
                warn(f"ReShade setup exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}")
        except Exception as exc:
            warn(f"ReShade setup failed: {exc}")
    elif not installed:
        warn("ReShade runtime not installed: wine or prefix missing. Addons were still deployed.")
    if api == "dx9" and (exe_dir / "d3d9.dll").exists() and not (exe_dir / "dxgi.dll").exists():
        tracker.move(exe_dir / "d3d9.dll", exe_dir / "dxgi.dll")
        dx9 = MOD_ROOT / "if dx9"
        for name in ("D3D9.dll", "dgVoodoo.conf", "dgVoodooCpl.exe"):
            src = dx9 / name
            if src.exists():
                tracker.copy(src, exe_dir / name)
        notes.append("DX9: ReShade moved to dxgi.dll; dgVoodoo installed as d3d9.dll")

    addon = MOD_ROOT / ("renodx-dlss5.addon64" if plan.nr == "on" else "renodx-dlss.addon64")
    if addon.exists():
        tracker.copy(addon, exe_dir / addon.name)
    feed = MOD_ROOT / ("dlss5-feed.addon32" if game.arch == "x86" else "dlss5-feed.addon64")
    if feed.exists():
        tracker.copy(feed, exe_dir / feed.name)
    if NR_DLL.exists():
        tracker.copy(NR_DLL, exe_dir / "nvngx_dlssnr.dll")
    shaders_src = RESHADE_SRC
    if shaders_src.exists():
        count = tracker.copy_tree(shaders_src, exe_dir / "reshade-shaders")
        notes.append(f"copied {count} ReShade shader files")
    ini = exe_dir / "ReShade.ini"
    if ini.exists():
        patch_ini(ini, {"GENERAL": {
            "EffectSearchPaths": r".\reshade-shaders\Shaders\**",
            "TextureSearchPaths": r".\reshade-shaders\Textures\**",
            "AddonSearchPaths": ".\\",
        }}, tracker)
        notes.append(f"patched {ini}")
    notes.append(f"ReShade API: {api}; NR addon: {addon.name}")
    return notes


def install_vulkan(game: Game, plan: Plan, tracker: Tracker) -> list[str]:
    helper = which("dlssnr-helper")
    notes: list[str] = []
    if not helper:
        raise SkillError(
            "dlssnr-helper is not installed. Install DLSS5VKLayer first:\n"
            "  tar -xzf dlssnr-0.3.2-1-linux-x86_64.tar.gz\n"
            "  cd dlssnr-0.3.2-1 && ./install.sh --user\n"
            "  # log out/in, then: dlssnr-helper init"
        )
    if not NR_SRC.exists():
        raise SkillError(f"NR runtime directory missing: {NR_SRC}")
    commands = [
        [helper, "init"],
        [helper, "import-binaries", str(NR_SRC)],
        [helper, "doctor"],
        [helper, "start"],
    ]
    for cmd in commands:
        proc = run(cmd, timeout=180)
        log(f"$ {' '.join(cmd)}")
        if proc.stdout.strip():
            log(proc.stdout.strip()[-1200:])
        if proc.returncode != 0:
            warn(f"command failed ({proc.returncode}): {(proc.stderr or proc.stdout)[-600:]}")
            break
        notes.append(" ".join(cmd))
    return notes


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append((name, status, detail))

    add("Python", "PASS" if sys.version_info >= (3, 9) else "FAIL", sys.version.split()[0])
    add("Asset root", "PASS" if ASSET_ROOT.is_dir() else "FAIL", str(ASSET_ROOT))
    add("DLSS5 Manager payload", "PASS" if OPTISCALER_SRC.is_dir() else "FAIL", str(OPTISCALER_SRC))
    add("OptiScaler.dll", "PASS" if (OPTISCALER_SRC / "OptiScaler.dll").exists() else "FAIL",
        human_bytes((OPTISCALER_SRC / "OptiScaler.dll").stat().st_size if (OPTISCALER_SRC / "OptiScaler.dll").exists() else None))
    add("DLSS 5 NR runtime", "PASS" if NR_DLL.exists() else "FAIL", human_bytes(NR_DLL.stat().st_size if NR_DLL.exists() else None))
    add("DLSS SR runtime", "PASS" if (DLSS_SRC / "nvngx_dlss.dll").exists() else "FAIL",
        human_bytes((DLSS_SRC / "nvngx_dlss.dll").stat().st_size if (DLSS_SRC / "nvngx_dlss.dll").exists() else None))
    add("DLSS-G runtime", "PASS" if (DLSS_SRC / "nvngx_dlssg.dll").exists() else "WARN",
        human_bytes((DLSS_SRC / "nvngx_dlssg.dll").stat().st_size if (DLSS_SRC / "nvngx_dlssg.dll").exists() else None))
    add("Streamline", "PASS" if (STREAMLINE_SRC / "sl.interposer.dll").exists() else "WARN", str(STREAMLINE_SRC))
    add("ReShade setup", "PASS" if RESHADE_SETUP.exists() else "WARN", human_bytes(RESHADE_SETUP.stat().st_size if RESHADE_SETUP.exists() else None))
    add("ReShade shaders", "PASS" if RESHADE_SRC.is_dir() else "WARN", str(RESHADE_SRC))
    enabler = STATE_ROOT / "vendor" / "dlss-enabler-headless.dll"
    add("6x Combo enabler", "PASS" if enabler.exists() else "WARN",
        str(enabler) if enabler.exists() else "not installed; only needed for --fg 6x")

    gpu = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]) if which("nvidia-smi") else None
    if gpu and gpu.returncode == 0 and gpu.stdout.strip():
        add("GPU", "PASS", gpu.stdout.strip().splitlines()[0])
    else:
        add("GPU", "FAIL", "nvidia-smi unavailable")
    drv = Path("/usr/lib/nvidia/wine/nvngx.dll")
    add("Driver NGX (Wine)", "PASS" if drv.exists() else "FAIL", human_bytes(drv.stat().st_size if drv.exists() else None))
    add("Wine", "PASS" if which("wine") else "WARN", which("wine") or "not found")
    add("protontricks", "PASS" if which("protontricks") else "WARN", which("protontricks") or "not found")
    add("dlssnr-helper", "PASS" if which("dlssnr-helper") else "WARN", which("dlssnr-helper") or "not installed")
    add("objdump", "PASS" if which("objdump") else "WARN", which("objdump") or "missing (raw PE scan fallback)")
    libs = steam_libraries()
    add("Steam libraries", "PASS" if libs else "WARN", f"{len(libs)} found")
    for lib in libs[:6]:
        add(f"  library", "INFO", str(lib))

    if args.json:
        print(json.dumps([{"check": n, "status": s, "detail": d} for n, s, d in checks], indent=2))
    else:
        width = max(len(n) for n, _, _ in checks) + 2
        for n, s, d in checks:
            log(f"{s:5}  {n:<{width}} {d}")
    return 1 if any(s == "FAIL" for _, s, _ in checks) else 0


def cmd_scan(args: argparse.Namespace) -> int:
    games = appmanifest_games()
    if args.filter:
        games = [g for g in games if args.filter.lower() in g.name.lower() or args.filter == g.appid]
    rows = []
    for g in games:
        g.exe = find_exe(g.path) if not args.no_exe else None
        if g.exe:
            g.api = detect_api(g.exe)
            g.arch = pe_arch(g.exe)
        mods = scan_mods(g.path) if not args.no_mods else {}
        rows.append({
            "appid": g.appid, "name": g.name, "path": str(g.path),
            "prefix": str(g.prefix) if g.prefix else None,
            "exe": str(g.exe) if g.exe else None, "api": g.api, "arch": g.arch,
            "dlss_sr": bool(mods.get("dlss_sr")), "dlss_fg": bool(mods.get("dlss_fg")),
            "dlss_rr": bool(mods.get("dlss_rr")), "nr": bool(mods.get("dlss_nr")),
            "optiscaler": bool(mods.get("optiscaler")), "reshade": bool(mods.get("reshade")),
            "anticheat": bool(mods.get("anticheat")),
        })
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        log("No Steam games found.")
        return 0
    log(f"{'appid':>10}  {'api':<8} {'arch':<4} {'DLSS':<4} {'FG':<3} {'RR':<3} {'NR':<3}  name")
    for r in rows:
        log(f"{r['appid']:>10}  {r['api']:<8} {r['arch']:<4} "
            f"{'yes' if r['dlss_sr'] else '-':<4} {'yes' if r['dlss_fg'] else '-':<3} "
            f"{'yes' if r['dlss_rr'] else '-':<3} {'yes' if r['nr'] else '-':<3}  {r['name']}")
    return 0


def build_plan_from_args(args: argparse.Namespace) -> tuple[Game, Plan]:
    game = resolve_game(args.game, getattr(args, "exe", None), getattr(args, "prefix", None))
    fg = getattr(args, "fg", None)
    nr = getattr(args, "nr", None)
    if getattr(args, "profile", None) == "full":
        fg = fg or "4x"
        nr = nr or "on"
    fg = fg or "off"
    nr = nr or "off"
    fg_mode = getattr(args, "fg_mode", None)
    if not fg_mode or fg_mode == "auto":
        fg_mode = "combo" if fg == "6x" else "native"
    return game, make_plan(game, getattr(args, "route", "auto"), fg, fg_mode, nr)


def cmd_plan(args: argparse.Namespace) -> int:
    preflight_updates(args)
    game, plan = build_plan_from_args(args)
    if args.json:
        print(json.dumps(asdict(plan), indent=2))
    else:
        print_plan(plan)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    preflight_updates(args)
    game, plan = build_plan_from_args(args)
    print_plan(plan)
    if args.dry_run:
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            raise SkillError("Refusing to install without --yes in a non-interactive session.")
        answer = input("Proceed with these changes? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            log("Aborted.")
            return 1
    tracker = Tracker(game, plan.route)
    notes: list[str] = []
    try:
        if plan.route == "native":
            notes = install_native(game, plan, tracker)
        elif plan.route == "optiscaler":
            notes = install_optiscaler(game, plan, tracker)
        elif plan.route == "reshade":
            notes = install_reshade(game, plan, tracker)
        elif plan.route == "vulkan":
            notes = install_vulkan(game, plan, tracker)
        else:
            raise SkillError(f"Unknown route: {plan.route}")
    except Exception:
        manifest = tracker.save(plan, notes + ["installation interrupted"])
        warn(f"Partial install manifest: {manifest}")
        warn(f"Roll back with: {sys.argv[0]} rollback {game.appid}")
        raise
    manifest = tracker.save(plan, notes)
    log("")
    log(f"Installed {plan.route} for {game.name}.")
    log(f"Manifest: {manifest}")
    log(f"Backup:   {tracker.backup_dir}")
    log("Launch options:")
    for line in plan.launch_options:
        log(f"  {line}")
    if plan.route == "optiscaler" and plan.fg != "off":
        log(f"FG {plan.fg} is configured but disabled; after a clean first launch set [FrameGen] Enabled=true in OptiScaler.ini.")
    return 0


def load_manifest(appid: str) -> dict[str, Any]:
    latest = MANIFEST_ROOT / appid / "latest.json"
    if not latest.exists():
        raise SkillError(f"No manifest for {appid}. Nothing to verify or roll back.")
    return json.loads(latest.read_text())


def cmd_verify(args: argparse.Namespace) -> int:
    game = resolve_game(args.game)
    manifest = load_manifest(game.appid)
    results: list[dict[str, Any]] = []
    for entry in manifest.get("files", []):
        p = Path(entry["path"])
        exists = p.exists()
        status = "PASS"
        detail = "present"
        if not exists:
            status, detail = "FAIL", "missing"
        elif entry.get("sha256_new") and p.is_file():
            current = sha256(p)
            if current != entry["sha256_new"]:
                status, detail = "WARN", "hash differs from install"
        results.append({"path": str(p), "status": status, "detail": detail})
    prefix = Path(manifest["prefix"]) if manifest.get("prefix") else None
    if prefix:
        ngx = prefix / "drive_c/windows/system32/nvngx.dll"
        results.append({"path": str(ngx), "status": "PASS" if ngx.exists() else "WARN",
                        "detail": "prefix NGX core" if ngx.exists() else "missing nvngx.dll"})
    if manifest.get("route") == "vulkan":
        helper = which("dlssnr-helper")
        if helper:
            proc = run([helper, "status"], timeout=20)
            ok = proc.returncode == 0
            results.append({"path": "dlssnr-helper", "status": "PASS" if ok else "WARN",
                            "detail": (proc.stdout or proc.stderr).strip()[:200]})
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            log(f"{r['status']:5}  {r['path']}  ({r['detail']})")
    return 1 if any(r["status"] == "FAIL" for r in results) else 0


def cmd_rollback(args: argparse.Namespace) -> int:
    game = resolve_game(args.game)
    manifest = load_manifest(game.appid)
    if not args.yes and sys.stdin.isatty():
        if input(f"Roll back {manifest.get('name')}? [y/N] ").strip().lower() not in ("y", "yes"):
            return 1
    for entry in reversed(manifest.get("files", [])):
        p = Path(entry["path"])
        if entry.get("existed"):
            backup = Path(entry["backup"]) if entry.get("backup") else None
            if backup and backup.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, p)
                log(f"restored {p}")
            elif entry.get("link"):
                if p.exists() or p.is_symlink():
                    p.unlink()
                p.symlink_to(entry["link"])
                log(f"restored symlink {p}")
        else:
            if p.exists() or p.is_symlink():
                p.unlink()
                log(f"removed {p}")
    for d in reversed(manifest.get("dirs", [])):
        dp = Path(d)
        try:
            if dp.is_dir() and not any(dp.iterdir()):
                dp.rmdir()
                log(f"removed empty dir {dp}")
        except OSError:
            pass
    latest = MANIFEST_ROOT / game.appid / "latest.json"
    if latest.exists():
        rolled = latest.with_name(f"rolledback-{time.strftime('%Y%m%d-%H%M%S')}.json")
        latest.replace(rolled)
    log("Rollback complete.")
    return 0


REPOS = [
    ("DLSS Swapper", "beeradmoore/dlss-swapper", "v1.2.7.0"),
    ("NVIDIA Profile Inspector", "Orbmu2k/nvidiaProfileInspector", "v3.0.2.3"),
    ("DLSS5 Manager", "NODIX-TECH/DLSS-5-MANAGER", "1.3.8"),
    ("DLSS5VKLayer", "bmitch87/DLSS5VKLayer", "not installed"),
    ("Streamline", "NVIDIA-RTX/Streamline", "2.14.1"),
    ("dlssg_for_sm86", "sdli1995/dlssg_for_sm86", "0.3.5 liveflow / 0.2.3 OptiScaler"),
    ("OptiScaler upstream", "optiscaler/OptiScaler", "0.7.7 neural fork"),
    ("RTX40MFG-Unlock", "dashdogy/RTX40MFG-Unlock", "not bundled"),
    ("DLSS Enabler", "artur-graniszewski/DLSS-Enabler", "not bundled"),
    ("DXVK-NVAPI", "jp7677/dxvk-nvapi", "via Proton"),
]


def github_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "nvidia-stack/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


UPDATE_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "nvidia-stack" / "update-check.json"
UPDATE_TTL = 3600


def fetch_update_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    helper = which("dlssnr-helper")
    layer_manifest = Path.home() / ".local/share/vulkan/implicit_layer.d/VK_LAYER_NV_dlssnr.x86_64.json"
    dlssnr_local = "not installed"
    if layer_manifest.exists():
        dlssnr_local = "installed (layer manifest present)"
    elif helper:
        dlssnr_local = "helper present; layer manifest missing"
    for name, repo, local in REPOS:
        if name == "DLSS5VKLayer":
            local = dlssnr_local
        latest = "?"
        published = "?"
        try:
            if name == "NVIDIA Profile Inspector":
                releases = github_json(f"https://api.github.com/repos/{repo}/releases?per_page=5")
                stable = next((r for r in releases if not r.get("prerelease")), None)
                pre = next((r for r in releases if r.get("prerelease")), None)
                latest = f"{stable.get('tag_name') if stable else '?'} (stable) / {pre.get('tag_name') if pre else '?'} (pre)"
                published = pre.get("published_at", "?") if pre else (stable.get("published_at", "?") if stable else "?")
            else:
                rel = github_json(f"https://api.github.com/repos/{repo}/releases/latest")
                latest = rel.get("tag_name", "?")
                published = rel.get("published_at", "?")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            latest = f"error: {exc}"
        rows.append({"name": name, "repo": repo, "local": local, "latest": latest, "published": published})
    return rows


def collect_updates(force: bool = False) -> list[dict[str, str]]:
    if not force:
        try:
            cached = json.loads(UPDATE_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(cached.get("checked_at", 0)) < UPDATE_TTL:
                rows = cached.get("rows")
                if isinstance(rows, list):
                    return rows
        except (OSError, ValueError, TypeError):
            pass
    rows = fetch_update_rows()
    try:
        UPDATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_CACHE.write_text(json.dumps({"checked_at": time.time(), "rows": rows}, indent=2),
                               encoding="utf-8")
    except OSError:
        pass
    return rows


def preflight_updates(args: argparse.Namespace) -> None:
    if getattr(args, "no_update_check", False):
        return
    try:
        rows = collect_updates(force=getattr(args, "refresh", False))
    except Exception as exc:  # network is best-effort; never block a plan
        print(f"Upstream check failed: {exc}", file=sys.stderr)
        return
    if not rows:
        return
    changed = []
    for r in rows:
        latest = r.get("latest", "?")
        local = r.get("local", "?")
        if latest == "?" or latest.startswith("error:") or latest == local:
            continue
        changed.append(f"  {r['name']}: local {local} | latest {latest}")
    if changed:
        print("Upstream check (cache 1h; use --refresh to force):", file=sys.stderr)
        print("\n".join(changed), file=sys.stderr)
    else:
        print(f"Upstream check: {len(rows)} repos checked; no update needed.", file=sys.stderr)


def cmd_update_check(args: argparse.Namespace) -> int:
    rows = collect_updates(force=getattr(args, "refresh", False))
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        log(f"{r['name']}: local {r['local']} | latest {r['latest']} | {r['published']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="NVIDIA game stack helper for Linux/Proton")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="list Steam games and detected APIs")
    scan.add_argument("--filter", help="filter by name or appid")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--no-exe", action="store_true", help="skip executable discovery")
    scan.add_argument("--no-mods", action="store_true", help="skip mod detection")
    scan.set_defaults(func=cmd_scan)

    doctor = sub.add_parser("doctor", help="check environment and payloads")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    plan = sub.add_parser("plan", help="show the install plan without writing")
    plan.add_argument("game", help="appid, name, or path")
    plan.add_argument("--route", choices=["auto", "native", "optiscaler", "reshade", "vulkan"], default="auto")
    plan.add_argument("--fg", choices=["off", "2x", "3x", "4x", "6x"])
    plan.add_argument("--fg-mode", choices=["auto", "combo"])
    plan.add_argument("--nr", choices=["on", "off"])
    plan.add_argument("--profile", choices=["safe", "full"])
    plan.add_argument("--exe", help="override executable path")
    plan.add_argument("--prefix", help="Wine/Proton prefix (pfx dir or WINEPREFIX)")
    plan.add_argument("--no-update-check", action="store_true", help="skip upstream preflight")
    plan.add_argument("--refresh", action="store_true", help="force upstream preflight")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=cmd_plan)

    install = sub.add_parser("install", help="back up and install a route")
    install.add_argument("game", help="appid, name, or path")
    install.add_argument("--route", choices=["auto", "native", "optiscaler", "reshade", "vulkan"], default="auto")
    install.add_argument("--fg", choices=["off", "2x", "3x", "4x", "6x"])
    install.add_argument("--fg-mode", choices=["auto", "combo"])
    install.add_argument("--nr", choices=["on", "off"])
    install.add_argument("--profile", choices=["safe", "full"])
    install.add_argument("--exe", help="override executable path")
    install.add_argument("--prefix", help="Wine/Proton prefix (pfx dir or WINEPREFIX)")
    install.add_argument("--no-update-check", action="store_true", help="skip upstream preflight")
    install.add_argument("--refresh", action="store_true", help="force upstream preflight")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--yes", action="store_true")
    install.set_defaults(func=cmd_install)

    verify = sub.add_parser("verify", help="verify files against the install manifest")
    verify.add_argument("game")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=cmd_verify)

    rollback = sub.add_parser("rollback", help="restore files from the install manifest")
    rollback.add_argument("game")
    rollback.add_argument("--yes", action="store_true")
    rollback.set_defaults(func=cmd_rollback)

    update = sub.add_parser("update-check", help="check upstream release tags")
    update.add_argument("--refresh", action="store_true")
    update.add_argument("--json", action="store_true")
    update.set_defaults(func=cmd_update_check)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SkillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
