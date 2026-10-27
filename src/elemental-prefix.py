#!/usr/bin/env python3
"""Elemental Prefix - shared Proton prefixes for non-Steam games.

Three prefixes: shared (a fixed safe set), legacy (safe set + video playback + .NET 4.8)
and custom (components picked by the user).

Without arguments it shows KDE dialogs (kdialog). The commands do the same from a terminal:

  elemental-prefix.py                                    dialogs
  elemental-prefix.py protons                            list installed Proton versions
  elemental-prefix.py components                         list components (custom prefix)
  elemental-prefix.py status                             show the prefixes
  elemental-prefix.py apply PREFIX [--proton NAME] [--components a,b,c] [--yes]
                                                         build a prefix or add missing components
  elemental-prefix.py reset shared|legacy [--proton NAME] --yes   rebuild a prefix
  elemental-prefix.py migrate [--proton NAME]            move from version 1 (~/Games/shared-prefix)
  elemental-prefix.py line PREFIX                        copy the Launch Options line
  elemental-prefix.py check GAME.exe [--gui]             check what a game needs
  elemental-prefix.py setup                              write the menu entries (used by install.sh)
  elemental-prefix.py uninstall [--delete-prefixes]      remove the app (prefixes stay by default)
"""
import argparse
import datetime
import mmap
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import textwrap
import time
from html import escape as _escape

HOME = os.path.expanduser("~")
STEAM = os.path.join(HOME, ".local/share/Steam")
BASE = os.path.join(HOME, ".local/share/elemental-prefix")  # program, log and the prefixes
BACKUPS = os.path.join(BASE, "backups")
OLD_PREFIX = os.path.join(HOME, "Games/shared-prefix")  # version 1
CONF = os.path.join(HOME, ".config/elemental-prefix.conf")
APP = os.path.join(BASE, "elemental-prefix.py")
LOG = os.path.join(BASE, "install.log")
STATE = os.path.join(BASE, "running")  # pid, start time, current step
DESKTOP = os.path.join(HOME, ".local/share/applications/elemental-prefix.desktop")
SERVICE_MENU = os.path.join(HOME, ".local/share/kio/servicemenus/elemental-prefix.desktop")
VERSION = "2.0.0"
FLATPAK_APP = "com.github.Matoking.protontricks"

# (winetricks verb, label, preselected for custom) - install order follows this list
COMPONENTS = [
    ("vcrun2022", "Visual C++ 2015-2022", True),
    ("vcrun2013", "Visual C++ 2013", False),
    ("vcrun2012", "Visual C++ 2012", False),
    ("vcrun2010", "Visual C++ 2010", True),
    ("vcrun2008", "Visual C++ 2008", True),
    ("vcrun2005", "Visual C++ 2005", False),
    ("d3dx9", "DirectX 9 (d3dx9)", True),
    ("xact", "XAudio / XACT sound", True),
    ("d3dcompiler_47", "Shader compiler for DX11 games", False),
    ("corefonts", "Windows fonts", True),
    ("dotnet48", ".NET Framework 4.8 (large, slow)", False),
    ("physx", "PhysX", False),
    ("quartz", "Videos in old games", False),
]
VERBS = [c[0] for c in COMPONENTS]
LABEL = {c[0]: c[1] for c in COMPONENTS}
SAFE = [v for v in VERBS if v not in ("dotnet48", "quartz")]

# name -> (folder, fixed components or None for custom, short description)
PREFIXES = {
    "shared": (os.path.join(BASE, "shared-prefix"), SAFE, "safe set"),
    "legacy": (os.path.join(BASE, "shared-prefix-legacy"), VERBS, "also videos, .NET 4.8"),
    "custom": (os.path.join(BASE, "shared-prefix-custom"), None, "your own list"),
}
FIXED = ("shared", "legacy")


def pdir(name):
    return PREFIXES[name][0]


def exists(name):
    return os.path.isdir(os.path.join(pdir(name), "pfx"))


def line(name, env=""):
    """Launch Options line; env: extra variables from the check (e.g. WINEDLLOVERRIDES)."""
    return f"STEAM_COMPAT_DATA_PATH={pdir(name)} PROTON_LOG=1 WINEDEBUG=fixme-all {env + ' ' if env else ''}%command%"


class Error(Exception):
    pass


# ---------- Steam files ----------

def parse_vdf(text):
    """Text VDF (libraryfolders.vdf, config.vdf, compatibilitytool.vdf) to nested dicts."""
    root = {}
    stack = [root]
    key = None
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*', text):
        s, brace = m.group(1), m.group(2)
        if brace == "{":
            d = {}
            stack[-1][key if key is not None else ""] = d
            stack.append(d)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif s is not None:
            s = s.replace('\\"', '"').replace("\\\\", "\\")
            if key is None:
                key = s
            else:
                stack[-1][key] = s
                key = None
    return root


def read_vdf(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return parse_vdf(f.read())
    except OSError:
        return {}


def parse_binary_vdf(b, i=0):
    """Binary VDF (shortcuts.vdf): 0 = map, 1 = string, 2 = int32, 8 = end of map."""
    d = {}
    while i < len(b):
        t = b[i]
        i += 1
        if t == 8:
            return d, i
        e = b.index(0, i)
        k = b[i:e].decode(errors="replace")
        i = e + 1
        if t == 0:
            d[k], i = parse_binary_vdf(b, i)
        elif t == 1:
            e = b.index(0, i)
            d[k] = b[i:e].decode(errors="replace")
            i = e + 1
        elif t == 2:
            d[k] = struct.unpack("<I", b[i:i + 4])[0]
            i += 4
        else:
            raise ValueError(f"unknown type {t}")
    return d, i


def find_key(d, name):
    """First value under a key named `name` (any depth, case-insensitive)."""
    if not isinstance(d, dict):
        return None
    for k, v in d.items():
        if k.lower() == name.lower():
            return v
    for v in d.values():
        r = find_key(v, name)
        if r is not None:
            return r
    return None


def steam_libraries():
    libs = [STEAM]
    folders = find_key(read_vdf(os.path.join(STEAM, "steamapps/libraryfolders.vdf")), "libraryfolders") or {}
    for entry in folders.values():
        p = entry.get("path") if isinstance(entry, dict) else None
        if p and os.path.realpath(p) not in map(os.path.realpath, libs):
            libs.append(p)
    return libs


def find_protons():
    """Installed Proton versions: dicts with name (as shown), key (Steam's tool name or folder) and dir."""
    tools = []
    for lib in steam_libraries():
        common = os.path.join(lib, "steamapps/common")
        try:
            names = sorted(os.listdir(common))
        except OSError:
            continue
        for n in names:
            d = os.path.join(common, n)
            if n.startswith("Proton") and os.path.isfile(os.path.join(d, "proton")):
                tools.append({"name": n, "key": n, "dir": d, "valve": True})
    ctd = os.path.join(STEAM, "compatibilitytools.d")
    try:
        names = sorted(os.listdir(ctd))
    except OSError:
        names = []
    for n in names:
        base = os.path.join(ctd, n)
        compat = find_key(read_vdf(os.path.join(base, "compatibilitytool.vdf")), "compat_tools") or {}
        for internal, info in compat.items():
            if not isinstance(info, dict):
                continue
            d = os.path.normpath(os.path.join(base, info.get("install_path", ".")))
            if os.path.isfile(os.path.join(d, "proton")):
                tools.append({"name": info.get("display_name", internal), "key": internal, "dir": d, "valve": False})
    return tools


def steam_default_tool():
    """Steam's default compatibility tool name (CompatToolMapping entry 0), or None."""
    mapping = find_key(read_vdf(os.path.join(STEAM, "config/config.vdf")), "CompatToolMapping") or {}
    entry = mapping.get("0")
    return entry.get("name") if isinstance(entry, dict) and entry.get("name") else None


def tool_matches(tool, steam_name):
    """Match a tool against Steam's internal name (GE-Proton11-11-x86_64, proton_experimental, proton_11...)."""
    if tool["key"] == steam_name:
        return True
    if not tool["valve"]:
        return False
    if steam_name == "proton_experimental":
        return tool["name"] == "Proton - Experimental"
    if steam_name == "proton_hotfix":
        return tool["name"] == "Proton Hotfix"
    m = re.fullmatch(r"proton_(\d+)", steam_name)
    v = re.match(r"Proton (\d+)\.(\d+)", tool["name"])
    return bool(m and v and m.group(1) in (v.group(1), v.group(1) + v.group(2)))


def wine_bin(tool_dir, exe):
    for sub in ("files/bin", "dist/bin"):
        p = os.path.join(tool_dir, sub, exe)
        if os.path.isfile(p):
            return p
    raise Error(f"no {exe} in {tool_dir}")


def shortcuts():
    """Non-Steam games from every user's shortcuts.vdf: dicts with name, opts, exe, appid. Read only."""
    games = []
    try:
        users = os.listdir(os.path.join(STEAM, "userdata"))
    except OSError:
        return games
    for u in users:
        try:
            with open(os.path.join(STEAM, "userdata", u, "config/shortcuts.vdf"), "rb") as f:
                d, _ = parse_binary_vdf(f.read())
        except (OSError, ValueError, IndexError, struct.error):
            continue
        for s in (find_key(d, "shortcuts") or {}).values():
            if isinstance(s, dict):
                g = {k.lower(): v for k, v in s.items()}
                games.append({"name": str(g.get("appname", "?")), "opts": str(g.get("launchoptions", "")),
                              "exe": str(g.get("exe", "")).strip().strip('"'), "appid": g.get("appid")})
    return games


def compat_path(opts):
    """STEAM_COMPAT_DATA_PATH from a Launch Options line, normalised, or None."""
    m = re.search(r"STEAM_COMPAT_DATA_PATH=(?:\"([^\"]*)\"|'([^']*)'|(\S+))", opts)
    if not m:
        return None
    return os.path.normpath(os.path.expanduser(next(x for x in m.groups() if x is not None)))


def games_on(folder):
    """Non-Steam games whose Launch Options point STEAM_COMPAT_DATA_PATH at `folder`."""
    target = os.path.normpath(folder)
    return [g for g in shortcuts() if compat_path(g["opts"]) == target]


def games_using(folder):
    return [g["name"] for g in games_on(folder)]


def games_text(folder):
    names = games_using(folder)
    return "Games using it: " + ", ".join(names) + "." if names else "No non-Steam game uses it yet."


def game_tool(appid):
    """Steam's compatibility tool for a game (its own setting, else Steam's default), or None."""
    mapping = find_key(read_vdf(os.path.join(STEAM, "config/config.vdf")), "CompatToolMapping") or {}
    entry = mapping.get(str(appid))
    name = entry.get("name") if isinstance(entry, dict) else None
    return name or steam_default_tool()


def proton_warnings(name, game=None):
    """Games on one prefix should run on one Proton: Proton rewrites the prefix to its own version
    on every start. Warn about games whose Proton differs from what most games on the prefix use
    (or, with a tie, from the Proton the prefix was built with). game: only this game (a shortcut),
    counted as on the prefix even before its line is pasted."""
    games = games_on(pdir(name))
    if game and game["appid"] not in [g["appid"] for g in games]:
        games.append(game)
    tools = {g["name"]: game_tool(g["appid"]) for g in games if g["appid"] is not None}
    if not tools:
        return []
    protons = find_protons()
    built = current_tool(protons, load_conf(), name)
    count = {}
    for t in tools.values():
        if t:
            count[t] = count.get(t, 0) + 1
    best = max(count.values(), default=0)
    top = [t for t, n in count.items() if n == best]
    target = top[0] if len(top) == 1 and best > 1 else None
    shown = lambda key: next((t["name"] for t in protons if tool_matches(t, key)), key)
    out = []
    for g, t in tools.items():
        if (game and g != game["name"]) or not t:
            continue
        if target is not None:
            if t != target:
                out.append(f"{g} runs on {shown(t)} - set {shown(target)} in Properties > Compatibility.")
        elif built and len(tools) > 1 and not tool_matches(built, t):  # one game alone may run a newer one
            out.append(f"{g} runs on {shown(t)}, the prefix was built with {built['name']} - "
                       "keep all its games on one Proton.")
    return out


# ---------- Launch Options ----------

ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
OUR_VARS = ("STEAM_COMPAT_DATA_PATH", "PROTON_LOG")


def split_opts(opts):
    """Launch Options -> (variables, wrappers, arguments, problems). %command% is the game; text
    before it runs first (variables, then wrappers like ~/lsfg), text after it goes to the game.
    Raises ValueError on unbalanced quotes."""
    toks = shlex.split(opts)
    problems = []
    if toks.count("%command%") > 1:
        problems.append("%command% appears more than once in the Launch Options.")
    if "%command%" not in toks:
        # Steam passes text without %command% to the game as arguments
        if any(ASSIGN.match(t) for t in toks):
            problems.append("The Launch Options have no %command%, so their variables do nothing.")
        n = 0
        while n < len(toks) and ASSIGN.match(toks[n]):
            n += 1
        return toks[:n], [], toks[n:], problems
    cut = toks.index("%command%")
    before, args = toks[:cut], [t for t in toks[cut + 1:] if t != "%command%"]
    n = 0
    while n < len(before) and ASSIGN.match(before[n]):
        n += 1
    variables, wrappers = before[:n], before[n:]
    late = [t for t in wrappers + args if t.startswith("STEAM_COMPAT_DATA_PATH=")]
    if late:
        problems.append("STEAM_COMPAT_DATA_PATH stands after a wrapper or %command%, where it does nothing.")
    return variables, [t for t in wrappers if t not in late], [t for t in args if t not in late], problems


def quote(tok):
    """Quote a token for Launch Options; ~/path stays bare so the shell still expands it."""
    if not re.search(r"[\s'\"\\$`;&|<>()]", tok):
        return tok
    m = ASSIGN.match(tok)
    if m:
        v = tok[m.end():]
        return m.group(0) + '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return shlex.quote(tok)


def merged_line(opts, name, env=""):
    """Our line merged into a game's current Launch Options: our variables first, the user's
    variables, wrappers and arguments kept in order. Returns (line, problems with the old line)."""
    try:
        variables, wrappers, args, problems = split_opts(opts)
    except ValueError:
        return line(name, env), ["The old Launch Options have unbalanced quotes - replace the whole line."]
    keep = [v for v in variables if v.split("=", 1)[0] not in OUR_VARS and v != "WINEDEBUG=fixme-all"]
    ours = [f"STEAM_COMPAT_DATA_PATH={pdir(name)}", "PROTON_LOG=1"]
    if not any(v.startswith("WINEDEBUG=") for v in keep):
        ours.append("WINEDEBUG=fixme-all")
    for e in shlex.split(env):
        k, _, v = e.partition("=")
        old = next((x for x in keep if x.startswith(k + "=")), None)
        if old:  # merge DLL overrides with the user's own
            have = old.split("=", 1)[1].split(";")
            keep[keep.index(old)] = k + "=" + ";".join(have + [x for x in v.split(";") if x not in have])
        else:
            ours.append(e)
    return " ".join(quote(t) for t in ours + keep + wrappers + ["%command%"] + args), problems


# ---------- settings ----------

def load_conf():
    """{'shared': {...}, 'legacy': {...}, 'custom': {...}, 'v1': {...}, 'migrated': '1'}.
    Prefix keys are written as shared.proton=...; version 1 keys have no prefix."""
    conf = {n: {} for n in (*PREFIXES, "v1")}
    try:
        with open(CONF, encoding="utf-8") as f:
            for raw in f:
                k, sep, v = raw.strip().partition("=")
                k, v = k.strip(), v.strip()
                if not sep or k.startswith("#"):
                    continue
                section, dot, key = k.partition(".")
                if dot and section in PREFIXES:
                    conf[section][key] = v
                elif k in ("proton", "proton_name", "proton_dir", "components"):
                    conf["v1"][k] = v
                else:
                    conf[k] = v
    except OSError:
        pass
    for n in (*PREFIXES, "v1"):
        conf[n]["components"] = [c for c in conf[n].get("components", "").split() if c in VERBS]
    return conf


def save_conf(conf):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    with open(CONF, "w", encoding="utf-8") as f:
        for k, v in conf.items():
            if isinstance(v, str):
                f.write(f"{k}={v}\n")
        for n in PREFIXES:
            for k, v in conf[n].items():
                f.write(f"{n}.{k}={' '.join(v) if isinstance(v, list) else v}\n")
        if conf.get("migrated") != "1":
            for k, v in conf["v1"].items():
                f.write(f"{k}={' '.join(v) if isinstance(v, list) else v}\n")


def set_prefix_conf(name, tool, components):
    conf = load_conf()
    conf[name] = {"proton": tool["key"], "proton_name": tool["name"], "proton_dir": tool["dir"],
                  "components": [v for v in VERBS if v in components]}
    save_conf(conf)


def current_tool(protons, conf, name):
    """Proton the prefix was built with, else Steam's default, else the newest-looking one."""
    key = conf[name].get("proton")
    for t in protons:
        if key and t["key"] == key:
            return t
    default = steam_default_tool()
    if default:
        for t in protons:
            if tool_matches(t, default):
                return t
    return protons[-1] if protons else None


def proton_version(name):
    """Proton that last ran on the prefix (Proton writes it to the 'version' file)."""
    try:
        with open(os.path.join(pdir(name), "version"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


# ---------- running things ----------

def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def elapsed(since):
    s = int(time.time() - since)
    return f"{s // 60}:{s % 60:02d}"


def run_logged(cmd, env=None):
    log(f"$ {' '.join(cmd)}")
    start = time.time()
    with open(LOG, "a", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        while True:
            try:
                p.wait(timeout=30)
                break
            except subprocess.TimeoutExpired:
                print(f"  still working ({elapsed(start)})", flush=True)
                if progress_hook:
                    progress_hook(None, None, f"still working ({elapsed(start)})")
    log(f"exit {p.returncode}")
    return p.returncode


progress_hook = None  # set by the dialogs: called as (step, total, text); step None = still working


def step(n, total, text):
    print(f"STEP {n}/{total}: {text}", flush=True)
    if progress_hook:
        progress_hook(n, total, text)
    log(f"== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} {text}")
    with open(STATE, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()}\n{time.time()}\nStep {n}/{total}: {text}\n")


def running_install():
    """(step text, time since the step started) of an apply in progress, or None."""
    try:
        with open(STATE, encoding="utf-8") as f:
            pid, started, text = f.read().splitlines()[:3]
        os.kill(int(pid), 0)
        return text, elapsed(float(started))
    except (OSError, ValueError):
        return None


def clear_state():
    """Remove the progress file, but only our own (another apply may own it)."""
    try:
        with open(STATE, encoding="utf-8") as f:
            mine = f.readline().strip() == str(os.getpid())
        if mine:
            os.remove(STATE)
    except OSError:
        pass


def notify(text):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Elemental Prefix", "Elemental Prefix", text], capture_output=True)


def check_protontricks():
    if shutil.which("flatpak") is None or subprocess.run(
            ["flatpak", "info", FLATPAK_APP], capture_output=True).returncode != 0:
        raise Error("Protontricks is not installed. Install it from Discover (search: Protontricks), "
                    "then run Elemental Prefix again.")


def in_use(folder):
    """True when a wineserver is running on the prefix in `folder` (a game is open)."""
    target = os.path.join(folder, "pfx")
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm") as f:
                if f.read().strip() != "wineserver":
                    continue
            with open(f"/proc/{pid}/environ", "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        for e in env:
            if e.startswith(b"WINEPREFIX=") and os.path.normpath(e[11:].decode(errors="replace")) == target:
                return True
    return False


def winetricks(folder, tool, args):
    cmd = ["flatpak", "run", f"--filesystem={folder}", f"--filesystem={tool['dir']}",
           f"--env=WINEPREFIX={folder}/pfx",
           f"--env=WINE={wine_bin(tool['dir'], 'wine')}",
           f"--env=WINESERVER={wine_bin(tool['dir'], 'wineserver')}",
           "--command=winetricks", FLATPAK_APP] + args
    return cmd


def installed_verbs(name, tool):
    if not exists(name):
        return []
    r = subprocess.run(winetricks(pdir(name), tool, ["list-installed"]), capture_output=True, text=True)
    return [v for v in r.stdout.split() if v in VERBS]


def create_prefix(folder, tool):
    os.makedirs(folder, exist_ok=True)
    env = dict(os.environ, STEAM_COMPAT_DATA_PATH=folder, STEAM_COMPAT_CLIENT_INSTALL_PATH=STEAM)
    if run_logged([os.path.join(tool["dir"], "proton"), "run", "wineboot", "-u"], env) != 0 \
            or not os.path.isdir(os.path.join(folder, "pfx/drive_c")):
        raise Error(f"Creating the prefix failed. Details: {LOG}")


def backup_prefix(name):
    os.makedirs(BACKUPS, exist_ok=True)
    dest = os.path.join(BACKUPS, f"{os.path.basename(pdir(name))}-{datetime.datetime.now():%Y-%m-%d-%H%M}")
    os.rename(pdir(name), dest)
    log(f"old prefix moved to {dest}")
    return dest


USER_DIR = "pfx/drive_c/users/steamuser"  # Documents, AppData, Saved Games - where games keep saves


def copy_user_folder(src_prefix, folder):
    """Copy the Windows user folder into the new prefix. Components live in drive_c/windows,
    so a rebuild still drops them; the backup keeps everything as it was."""
    src = os.path.join(src_prefix, USER_DIR)
    if os.path.isdir(src):
        # cp -a: the folder holds symlinks that also exist in the new prefix (copytree fails on them)
        if run_logged(["cp", "-a", "--remove-destination", src + "/.", os.path.join(folder, USER_DIR)]) != 0:
            raise Error(f"Copying game saves failed. They are still in {src_prefix}. Details: {LOG}")


def plan(name, tool, components, conf, reset=False):
    """What apply would do: 'create', 'add' or 'rebuild', plus the verbs to install.
    Shared and legacy are only rebuilt on reset: a newer Proton upgrades them by itself."""
    if not exists(name):
        return "create", components
    if reset:
        return "rebuild", components
    if name == "custom" and conf["custom"].get("proton") and conf["custom"]["proton"] != tool["key"]:
        return "rebuild", components
    have = installed_verbs(name, tool)
    if name == "custom" and any(v in have and v not in components for v in VERBS):
        return "rebuild", components
    return "add", [v for v in components if v not in have]


def step_count(action, todo, copying):
    return len(todo) + (0 if action == "add" else 1) + (1 if action == "rebuild" or copying else 0)


def apply(name, tool, components, yes=False, reset=False, copy_from=None):
    """Build, extend or rebuild a prefix. copy_from: copy game saves from this prefix after creating."""
    if running_install():
        raise Error("Another installation is running. See: elemental-prefix.py status")
    check_protontricks()
    if in_use(pdir(name)) or (copy_from and in_use(copy_from)):
        raise Error("A game is using the prefix. Close it and try again.")
    conf = load_conf()
    components = [v for v in VERBS if v in components]
    action, todo = plan(name, tool, components, conf, reset)
    if action == "rebuild" and not yes:
        raise Error("This rebuilds the prefix (the old one is moved to "
                    f"{BACKUPS}). Run again with --yes.")
    log(f"\n##### {datetime.datetime.now():%Y-%m-%d %H:%M:%S} {name} {action}: {tool['name']} {' '.join(components)}")
    total = step_count(action, todo, copy_from)
    n = 0
    if action == "rebuild":
        copy_from = backup_prefix(name)
        print("Old prefix kept as " + copy_from, flush=True)
    if action != "add":
        n += 1
        step(n, total, f"Creating the {name} prefix with {tool['name']}")
        create_prefix(pdir(name), tool)
    if copy_from:
        n += 1
        step(n, total, "Copying game saves and settings")
        copy_user_folder(copy_from, pdir(name))
    done = [v for v in components if v not in todo]
    set_prefix_conf(name, tool, done)
    failed = []
    for v in todo:
        n += 1
        step(n, total, f"Installing {LABEL[v]}")
        if run_logged(winetricks(pdir(name), tool, ["-q", v])) == 0:
            done.append(v)
        else:
            failed.append(v)
        set_prefix_conf(name, tool, done)
    if failed:
        raise Error("Not installed: " + ", ".join(LABEL[v] for v in failed) + f". Details: {LOG}")
    return action


def needs_migration(conf):
    return os.path.isdir(os.path.join(OLD_PREFIX, "pfx")) and not exists("shared") and conf.get("migrated") != "1"


def migrate(tool):
    """Version 1 -> 2: build shared in the new place with the old prefix's saves. The old one stays."""
    if exists("shared"):
        raise Error(f"The shared prefix already exists: {pdir('shared')}")
    if not os.path.isdir(os.path.join(OLD_PREFIX, "pfx")):
        raise Error(f"No version 1 prefix in {OLD_PREFIX}")
    run_apply("shared", tool, SAFE, copy_from=OLD_PREFIX)
    conf = load_conf()
    conf["migrated"] = "1"
    save_conf(conf)


def copy_line(text):
    for q in ("qdbus6", "qdbus"):
        if shutil.which(q) and subprocess.run(
                [q, "org.kde.klipper", "/klipper", "setClipboardContents", text], capture_output=True).returncode == 0:
            return True
    return False


def run_apply(name, tool, components, yes=False, reset=False, copy_from=None):
    """apply() with the end-of-install notification and progress file cleanup."""
    try:
        apply(name, tool, components, yes, reset, copy_from)
    except Error as e:
        notify(f"Installation failed: {e}")
        raise
    finally:
        clear_state()
    notify(f"The {name} prefix is ready.")


def done_text(name, tool):
    default = tool_matches(tool, steam_default_tool() or "")
    which = tool["name"] if name == "custom" else f"{tool['name']} or newer"
    return (f"Games using it need {which} in Properties > Compatibility"
            + (" (Steam's default - nothing to set)." if default else "."))


# ---------- checking a game ----------

# Imported DLL (lower case, no .dll) -> component. A DLL shipped in the game folder needs nothing.
DLL_VERBS = [
    (r"msvc[rp]80|mfc80u?|vcomp", "vcrun2005"),
    (r"msvc[rp]90|mfc90u?|vcomp90", "vcrun2008"),
    (r"msvc[rp]100|mfc100u?|vcomp100", "vcrun2010"),
    (r"msvc[rp]110|mfc110u?|vcomp110|vccorlib110", "vcrun2012"),
    (r"msvc[rp]120|mfc120u?|vcomp120|vccorlib120", "vcrun2013"),
    (r"vcruntime140(_1)?|msvcp140(_\w+)?|concrt140|vcomp140|vccorlib140|mfc140u?|vcamp140", "vcrun2022"),
    (r"d3dx9_\d+", "d3dx9"),
    (r"d3dcompiler_47", "d3dcompiler_47"),
    (r"xactengine\d_\d+|x3daudio1_\d+|xaudio2_[0-7]|xapofx1_\d+", "xact"),
    (r"physxloader|physxcore|physxcooking|nxcooking", "physx"),
]
REDIST_DIRS = ("_commonredist", "redist", "redistributables", "directx", "__installer", "support", "dotnetfx")
REDIST_FILES = r"(vc_?redist|vcredist|dxsetup|dxwebsetup|dotnetfx|ndp\d|oalinst|physx.*setup|unins\d+|unitycrashhandler)"
MOD_DLLS = ("dxgi", "d3d9", "d3d11", "d3d12", "dinput8", "version", "winmm")  # ReShade, ASI loaders
OLD_VIDEO = (".wmv", ".mpg", ".mpeg", ".avi", ".asf")
BINK = (".bik", ".bk2", ".smk")


def pe_info(path):
    """Read a PE file's headers: {'bits', 'imports', 'delay' (delay-loaded; lower, no .dll),
    'clr' (runtime version), 'xna'}.
    Only the headers and import tables are touched (mmap), so large files are fine. None if not PE."""
    try:
        with open(path, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    except (OSError, ValueError):
        return None
    try:
        u16 = lambda o: struct.unpack_from("<H", mm, o)[0]
        u32 = lambda o: struct.unpack_from("<I", mm, o)[0]
        if mm[:2] != b"MZ":
            return None
        pe = u32(0x3C)
        if mm[pe:pe + 4] != b"PE\0\0":
            return None
        machine, nsec, optsize = u16(pe + 4), u16(pe + 6), u16(pe + 20)
        opt = pe + 24
        pe32 = u16(opt) == 0x10B
        base = u32(opt + 28) if pe32 else struct.unpack_from("<Q", mm, opt + 24)[0]
        ndd = u32(opt + (92 if pe32 else 108))
        dd = opt + (96 if pe32 else 112)
        sections = []
        for i in range(nsec):
            s = opt + optsize + 40 * i
            sections.append((u32(s + 12), max(u32(s + 8), u32(s + 16)), u32(s + 20)))

        def off(rva):
            for va, size, raw in sections:
                if va <= rva < va + size:
                    return rva - va + raw
            raise ValueError("rva outside sections")

        def cstr(rva):
            o = off(rva)
            return mm[o:mm.find(b"\0", o, o + 260)].decode("ascii", "replace")

        def dll(name):
            n = name.lower()
            return n[:-4] if n.endswith(".dll") else n

        imports, delay = set(), set()
        if ndd > 1 and u32(dd + 8):
            o = off(u32(dd + 8))
            for _ in range(2000):
                name_rva = u32(o + 12)
                if not name_rva:
                    break
                imports.add(dll(cstr(name_rva)))
                o += 20
        if ndd > 13 and u32(dd + 13 * 8):
            o = off(u32(dd + 13 * 8))
            for _ in range(2000):
                attrs, name = u32(o), u32(o + 4)
                if not name:
                    break
                delay.add(dll(cstr(name if attrs & 1 else name - base)))
                o += 32
        clr = None
        if ndd > 14 and u32(dd + 14 * 8):
            m = off(u32(off(u32(dd + 14 * 8)) + 8))
            clr = "?"
            if mm[m:m + 4] == b"BSJB":
                clr = mm[m + 16:m + 16 + u32(m + 12)].split(b"\0")[0].decode("ascii", "replace")
        return {"bits": 64 if machine == 0x8664 else 32, "imports": imports, "delay": delay, "clr": clr,
                "xna": bool(clr) and mm.find(b"Microsoft.Xna.Framework") != -1}
    except (struct.error, ValueError, IndexError):
        return None
    finally:
        mm.close()


def game_root(exe):
    """Folder to scan: the .exe's folder, or above an Unreal Engine project (X/Binaries/Win64)."""
    d = os.path.dirname(os.path.abspath(exe))
    parts = d.split(os.sep)
    if len(parts) > 3 and parts[-2].lower() == "binaries" and parts[-1].lower() in ("win64", "win32"):
        return os.sep.join(parts[:-3])
    return d


def shared_folder(d):
    """True for a folder that holds many games, not one: a drive, a Steam library, the home folder."""
    d = os.path.abspath(d)
    return (os.path.ismount(d) or d == HOME or os.path.dirname(d) in ("/run/media", f"/run/media/{os.path.basename(HOME)}")
            or os.path.isdir(os.path.join(d, "steamapps")) or os.path.isdir(os.path.join(d, "compatdata")))


def game_prefix(exe, root):
    """(state, shortcut or None): which prefix the game's Steam shortcut points to."""
    exe_n = os.path.normcase(os.path.abspath(exe))
    games = [g for g in shortcuts() if g["exe"].strip('"')]
    norm = lambda g: os.path.normcase(os.path.abspath(g["exe"].strip('"')))
    hit = next((g for g in games if norm(g) == exe_n), None)
    if hit is None:
        root_n = os.path.normcase(root) + os.sep
        hit = next((g for g in games if norm(g).startswith(root_n)), None)
    if hit is None:
        return "not in Steam", None
    p = compat_path(hit["opts"])
    for n in PREFIXES:
        if p == os.path.normpath(pdir(n)):
            return n, hit
    if p:
        return "other prefix: " + p, hit
    if hit["appid"] is not None and os.path.isdir(os.path.join(STEAM, "steamapps/compatdata", str(hit["appid"]))):
        return "its own Steam prefix", hit
    return "not started yet", hit


def check_game(exe):
    """Look at a game's files and tell which prefix it needs. Read only."""
    exe = os.path.abspath(exe)
    root = game_root(exe)
    report = {"exe": exe, "root": root, "needs": {}, "missing": {}, "hints": [], "env": "", "notes": []}
    files, pe_files = {}, []
    alone = shared_folder(root)
    if alone:
        root = os.path.dirname(exe)
        report["notes"].append("The .exe is not in a folder of its own, so only the files next to it were read. "
                               "Keep each game in its own folder.")
    for dirpath, dirs, names in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        redist_dir = any(p.lower() in REDIST_DIRS for p in dirpath[len(root):].split(os.sep))
        dirs[:] = [] if alone or depth >= 6 else [x for x in dirs if x.lower() not in ("steamapps", "compatdata")]
        for n in names:
            low = n.lower()
            files.setdefault(low, os.path.join(dirpath, n))
            if low.endswith((".exe", ".dll")) and not redist_dir and not re.match(REDIST_FILES, low):
                pe_files.append(os.path.join(dirpath, n))
        if len(pe_files) > 3000:
            report["notes"].append("Large folder: only the first 3000 programs and libraries were read.")
            break
    shipped = {n[:-4] for n in files if n.endswith(".dll")}
    sysdirs = {}
    for n in PREFIXES:
        if exists(n):
            win = os.path.join(pdir(n), "pfx/drive_c/windows")
            for bits, sub in ((64, "system32"), (32, "syswow64")):
                try:
                    sysdirs[bits] = {x.lower()[:-4] for x in os.listdir(os.path.join(win, sub)) if x.lower().endswith(".dll")}
                except OSError:
                    pass
            break

    main = pe_info(exe)
    exe_dir_n = os.path.normcase(os.path.dirname(exe))
    for path in pe_files:
        info = main if os.path.normcase(path) == os.path.normcase(exe) else pe_info(path)
        if info is None or (info["clr"] and path.lower().endswith(".dll")):
            continue  # not a program, or a .NET library (Unity's Managed folder and the like)
        who = os.path.relpath(path, root)
        for imp in info["imports"] | info["delay"]:
            verb = next((v for rx, v in DLL_VERBS if re.fullmatch(rx, imp)), None)
            if verb == "physx" and imp == "physxloader" and "physxcore" not in shipped:
                report["needs"].setdefault(verb, who)
            elif imp in shipped or imp.startswith(("api-ms-", "ext-ms-")) or imp == "mscoree":
                continue
            elif verb:
                report["needs"].setdefault(verb, who)
            elif (imp in info["imports"] and os.path.normcase(os.path.dirname(path)) == exe_dir_n
                  and info["bits"] in sysdirs and imp not in sysdirs[info["bits"]]):
                # only what stops the game from starting: normal imports of the .exe and DLLs next to it
                report["missing"].setdefault(imp + ".dll", who)

    if main and main["clr"]:
        if main["clr"].startswith("v4"):
            report["needs"]["dotnet48"] = os.path.basename(exe)
            report["notes"].append(".NET 4 program. Proton's Wine Mono runs many of them; "
                                   "the legacy prefix has the real .NET 4.8.")
        else:
            report["notes"].append(f".NET {main['clr']} program: not in Elemental Prefix. "
                                   "Proton's Wine Mono may run it.")
        if main["xna"]:
            report["notes"].append("Uses XNA (winetricks xna40): not in Elemental Prefix.")

    names = set(files)
    redist = sorted({os.path.relpath(os.path.dirname(p), root) or "." for n, p in files.items()
                     if re.match(REDIST_FILES, n) and not n.startswith(("unins", "unitycrash"))})
    if redist:
        report["hints"].append("Installers in the game folder (" + ", ".join(redist[:3]) + "): "
                               "no need to run them, the check reads what the game itself uses.")
    if "oalinst.exe" in names:
        report["notes"].append("OpenAL installer found (winetricks openal): not in Elemental Prefix.")
    exe_dir = os.path.dirname(exe)
    mods = [m for m in MOD_DLLS if os.path.isfile(os.path.join(exe_dir, m + ".dll"))]
    if mods:
        report["env"] = 'WINEDLLOVERRIDES="' + ";".join(f"{m}=n,b" for m in mods) + '"'
        report["hints"].append(", ".join(m + ".dll" for m in mods) + " next to the game (ReShade or a mod): "
                               f"the line gets {report['env']} so it loads.")
    if any(n.endswith(BINK) or n.startswith(("binkw", "bink2w", "smackw")) for n in names):
        report["hints"].append("Bink or Smacker videos: they ship with the game and need nothing.")
    if any(n.endswith(OLD_VIDEO) for n in names):
        report["hints"].append("Old video files (.wmv, .mpg, .avi): if videos stay black, use the legacy prefix.")

    need = set(report["needs"])
    report["prefix"] = "legacy" if need - set(SAFE) else "shared"
    report["uses"], report["shortcut"] = game_prefix(exe, root)
    return report


def report_lines(r, custom_components):
    """Report as short paragraphs (for the dialog and the terminal)."""
    out = []
    out.append(f"Recommended: the {r['prefix']} prefix.")
    if r["needs"]:
        out.append("Needs: " + ", ".join(LABEL[v] for v in VERBS if v in r["needs"]) + ".")
    else:
        out.append("Needs none of the components (the game ships what it uses).")
    if r["missing"]:
        items = list(r["missing"].items())
        out.append("Not found in the game or the prefix: " + ", ".join(
            f"{d} (used by {w})" for d, w in items[:4]) + (f" and {len(items) - 4} more" if len(items) > 4 else "") + ".")
    out += r["hints"] + r["notes"]
    uses = r["uses"]
    out.append("Uses now: " + (f"the {uses} prefix" if uses in PREFIXES else uses) + ".")
    game = r["shortcut"]
    if game:
        try:
            out += split_opts(game["opts"])[3]
        except ValueError:
            out.append("The Launch Options have unbalanced quotes.")
        if uses in PREFIXES:
            out += proton_warnings(uses, game)
    elif shutil.which("steamos-add-to-steam"):
        out.append("Not in Steam yet: it can be added from here.")
    if exists("custom"):
        add = [v for v in VERBS if v in r["needs"] and v not in custom_components]
        if add:
            out.append("The custom prefix lacks: " + ", ".join(LABEL[v] for v in add) + ".")
    return out


# ---------- dialogs (kdialog) ----------

TITLE = f"Elemental Prefix {VERSION}"

# Short list labels: kdialog does not wrap list items, so they stay under ~45 characters.
GUI_LABELS = {
    "vcrun2022": "Visual C++ 2015-2022 (games from 2015)",
    "vcrun2013": "Visual C++ 2013 (games 2013-2015)",
    "vcrun2012": "Visual C++ 2012 (games 2012-2014)",
    "vcrun2010": "Visual C++ 2010 (games 2010-2012)",
    "vcrun2008": "Visual C++ 2008 (games 2008-2010)",
    "vcrun2005": "Visual C++ 2005 (games 2005-2008)",
    "d3dx9": "DirectX 9 (older games)",
    "xact": "XAudio / XACT (no sound in game)",
    "d3dcompiler_47": "Shader compiler (DirectX 11 games)",
    "corefonts": "Windows fonts (missing text)",
    "dotnet48": ".NET 4.8 (launchers, slow: ~10 min)",
    "physx": "PhysX (NVIDIA physics)",
    "quartz": "Video playback (black cutscenes)",
}


def escape(s):
    return _escape(s, quote=False)


def html(title, *paras):
    """Heading plus paragraphs, wrapped by hand: kdialog grows the window to fit long lines."""
    out = f"<h2>{escape(title)}</h2>"
    for p in paras:
        if isinstance(p, tuple):  # ("code", text): bold, broken only at spaces (the clipboard has it whole)
            out += "<p><b>" + "<br>".join(escape(x) for x in textwrap.wrap(p[1], 70, break_long_words=False)) + "</b></p>"
        else:
            out += "<p>" + "<br>".join(escape(x) for x in textwrap.wrap(p, 60)) + "</p>"
    return out


def kdialog(*args, size=None):
    """Run kdialog; returns stdout, or None when the user pressed Cancel / closed the window."""
    cmd = ["kdialog", "--title", TITLE] + (["--geometry", size] if size else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.isdir(BASE):  # not after uninstall removed it
        log(f"kdialog {[a[:60] for a in args[:4]]} -> exit {r.returncode} {r.stderr.strip()[-300:]}")
    if r.returncode not in (0, 1):
        raise Error(f"kdialog failed (exit {r.returncode}). Details: {LOG}")
    # With --geometry kdialog also prints "x: .. y: .. w: .. h: .." - drop it.
    out = "\n".join(l for l in r.stdout.splitlines() if not l.startswith("x: "))
    return out.strip() if r.returncode == 0 else None


class Progress:
    def __init__(self, total):
        self.q = shutil.which("qdbus6") or shutil.which("qdbus")
        self.text = ("Installing", "Checking the prefix...")
        out = kdialog("--progressbar", self.label(""), str(max(total, 1))) or ""
        self.ref = out.split()
        self.call("showCancelButton", "false")  # Cancel would only close the window, not stop winetricks

    def label(self, status):
        # The progress window sizes itself to the first label and ignores --geometry,
        # so every label is a fixed-width block with the same number of lines.
        body = html(*self.text, "Windows installers may flash on screen - don't worry, everything works correctly.", status or " ")
        return f'<table width="600"><tr><td>{body}</td></tr></table>'

    def call(self, *args):
        if self.q and len(self.ref) == 2:
            r = subprocess.run([self.q] + self.ref + list(args), capture_output=True, text=True)
            if r.returncode != 0:
                log(f"qdbus {args[0]} -> exit {r.returncode} {r.stderr.strip()[-200:]}")

    def __call__(self, n, total, text):
        if n is None:
            self.call("setLabelText", self.label(text))
        else:
            self.text = (f"Step {n} of {total}", text)
            self.call("setLabelText", self.label(""))
            self.call("Set", "", "value", str(n - 1))

    def close(self):
        self.call("close")


def with_progress(total, fn, *args, **kw):
    global progress_hook
    prog = Progress(total)
    progress_hook = prog
    try:
        fn(*args, **kw)
    finally:
        prog.close()
        progress_hook = None


def gui():
    if shutil.which("kdialog") is None:
        raise Error("kdialog not found. Run Elemental Prefix in Desktop Mode.")
    try:
        gui_steps()
    except Error as e:
        kdialog("--error", html("Something went wrong", str(e)))


def show_line(title, name, tool, *extra, env="", game=None):
    """Copy the line and show it. With a game (shortcut), the line is merged into its Launch Options."""
    problems = []
    if game:
        text, problems = merged_line(game["opts"], name, env)
        where = f"Paste this line over the whole Launch Options of {game['name']} (Properties > General)."
        if game["opts"].strip():
            where += " Your other settings in it are kept."
    else:
        text = line(name, env)
        where = "Paste this line into the game's Launch Options (Steam > game > Properties > General)."
    copied = copy_line(text)
    kdialog("--msgbox", html(
        title,
        where + (" It is already in the clipboard:" if copied else ""),
        ("code", text),
        done_text(name, tool), *problems, *proton_warnings(name, game), *extra),
        size="760x480")


def pick_proton(protons, conf, name, title, *paras):
    default = steam_default_tool() or ""
    cur = current_tool(protons, conf, name)
    items = []
    for i, t in enumerate(protons):
        notes = [x for x, ok in (("Steam default", tool_matches(t, default)),
                                 ("used now", exists(name) and t["key"] == conf[name].get("proton"))) if ok]
        items += [str(i), t["name"] + (f"  ({', '.join(notes)})" if notes else ""), "on" if t is cur else "off"]
    choice = kdialog("--radiolist", html(title, *paras), *items, size="760x560")
    return None if choice is None else protons[int(choice)]


def gui_steps():
    busy = running_install()
    if busy:
        kdialog("--sorry", html("Installation running", f"{busy[0]} (for {busy[1]}).",
                                "Wait until it finishes."))
        return
    check_protontricks()
    protons = find_protons()
    if not protons:
        kdialog("--error", html("No Proton found", "Install a Proton in Steam first (Library > Tools)."))
        return
    conf = load_conf()

    if needs_migration(conf):
        gui_migrate(protons, conf)
        return

    items = []
    for n in PREFIXES:
        state = "ready" if exists(n) else "not built"
        items += [n, f"{n.capitalize()} - {PREFIXES[n][2]} ({state})"]
    pick = kdialog("--menu", html(
        "Choose a prefix",
        "Shared fits most games. Legacy adds video playback and .NET 4.8 for old games "
        "(it can break videos in newer ones). Custom has the components you pick."),
        *items, "reset", "Reset prefix (advanced)", size="760x520")
    if pick is None:
        return
    if pick == "reset":
        gui_reset(protons, conf)
    elif pick == "custom":
        gui_custom(protons, conf)
    else:
        gui_fixed(protons, conf, pick)


def gui_fixed(protons, conf, name, env="", game=None, *extra):
    if exists(name):
        tool = current_tool(protons, conf, name)
        action, todo = plan(name, tool, PREFIXES[name][1], conf)
        if todo:  # an earlier install failed on some components
            with_progress(step_count(action, todo, False), run_apply, name, tool, PREFIXES[name][1])
        show_line(f"{name.capitalize()} prefix", name, tool, *(extra or (games_text(pdir(name)),)), env=env, game=game)
        return
    tool = pick_proton(protons, conf, name, f"Proton for the {name} prefix",
                       "Games on this prefix must run on this Proton or a newer one.",
                       "Steam default needs no extra settings in Steam.")
    if tool is None:
        return
    components = PREFIXES[name][1]
    with_progress(step_count("create", components, False), run_apply, name, tool, components)
    show_line(f"{name.capitalize()} prefix is ready", name, tool, *extra, env=env, game=game)


def gui_custom(protons, conf):
    if exists("custom"):
        pick = kdialog("--menu", html(
            "Custom prefix",
            f"Proton: {conf['custom'].get('proton_name', '-')}",
            "Components: " + (", ".join(LABEL[v] for v in conf["custom"]["components"]) or "none"),
            "What do you want to do?"),
            "line", "Copy the Launch Options line",
            "change", "Change Proton or components", size="760x520")
        if pick is None:
            return
        if pick == "line":
            show_line("Custom prefix", "custom", current_tool(protons, conf, "custom"),
                      games_text(pdir("custom")))
            return

    tool = pick_proton(protons, conf, "custom", "Step 1 of 2: Proton",
                       "Games that use the custom prefix must run on the same Proton.",
                       "Steam default needs no extra settings in Steam.")
    if tool is None:
        return
    chosen = conf["custom"]["components"] or [c[0] for c in COMPONENTS if c[2]]
    items = []
    for verb, _, _ in COMPONENTS:
        items += [verb, GUI_LABELS[verb], "on" if verb in chosen else "off"]
    picked = kdialog("--separate-output", "--checklist", html(
        "Step 2 of 2: Components",
        "Libraries that old Windows games often need. Ticked: already installed or recommended.",
        "Unticking an installed one rebuilds the prefix."), *items, size="760x640")
    if picked is None:
        return
    components = picked.split()

    action, todo = plan("custom", tool, components, conf)
    if action == "rebuild" and not confirm_rebuild("custom", "Removing components or changing Proton "
                                                   "needs a new prefix. All ticked components will be "
                                                   "installed again, which takes a few minutes."):
        return
    if action != "add" or todo:
        with_progress(step_count(action, todo, False), run_apply, "custom", tool, components, yes=True)
    show_line("Custom prefix is ready" if action != "add" or todo else "Nothing to change", "custom", tool)


def confirm_rebuild(name, why):
    return kdialog("--continue-label", "Rebuild", "--warningcontinuecancel", html(
        f"The {name} prefix will be rebuilt",
        why,
        games_text(pdir(name)),
        "Game saves and settings (the Windows user folder) are copied to the new prefix. "
        f"The current prefix is moved to {BACKUPS} just in case.")) is not None


def gui_reset(protons, conf):
    built = [n for n in FIXED if exists(n)]
    if not built:
        kdialog("--msgbox", html("Nothing to reset", "Neither the shared nor the legacy prefix is built yet."))
        return
    if len(built) == 1:
        name = built[0]
    else:
        name = kdialog("--menu", html("Reset prefix", "Which prefix?"),
                       *[x for n in built for x in (n, n.capitalize())], size="760x420")
        if name is None:
            return
    tool = pick_proton(protons, conf, name, f"Reset the {name} prefix",
                       "Only when it is broken or to go back to an older Proton. "
                       "A newer Proton upgrades the prefix by itself.")
    if tool is None:
        return
    if not confirm_rebuild(name, "All its components will be installed again, which takes a few minutes."):
        return
    components = PREFIXES[name][1]
    with_progress(step_count("rebuild", components, False), run_apply, name, tool, components,
                  yes=True, reset=True)
    show_line(f"{name.capitalize()} prefix is ready", name, tool)


def gui_migrate(protons, conf):
    old_games = games_using(OLD_PREFIX)
    if kdialog("--continue-label", "Move", "--warningcontinuecancel", html(
            "Moving to version 2",
            f"Version 2 keeps its prefixes in {BASE}.",
            "The shared prefix is built there with the safe set of components, and game saves "
            f"are copied from {OLD_PREFIX}. The old folder stays as a backup.",
            "This takes a few minutes."), size="760x480") is None:
        return
    tool = None
    for t in protons:
        if conf["v1"].get("proton") == t["key"]:
            tool = t
    tool = tool or current_tool(protons, conf, "shared")
    with_progress(step_count("create", SAFE, True), migrate, tool)
    show_line("Shared prefix is ready", "shared", tool,
              ("Paste the new line into these games (they still use the old folder): "
               + ", ".join(old_games) + ".") if old_games else
              "No non-Steam game uses the old folder.")


def gui_check(path):
    """Check game dependencies: right-click on an .exe in Dolphin, or the menu entry's action."""
    if shutil.which("kdialog") is None:
        raise Error("kdialog not found. Run Elemental Prefix in Desktop Mode.")
    try:
        if not path:
            path = kdialog("--getopenfilename", HOME, "Windows programs (*.exe *.EXE)")
            if not path:
                return
        if not path.lower().endswith(".exe") or not os.path.isfile(path):
            kdialog("--sorry", html("Not a game", "Choose the game's .exe file."))
            return
        r = check_game(path)
        conf = load_conf()
        rec = r["prefix"]
        items = ["line", (f"Copy the line for the {rec} prefix" if exists(rec)
                          else f"Build the {rec} prefix (not built yet)")]
        add = [v for v in VERBS if v in r["needs"] and v not in conf["custom"]["components"]]
        items += ["custom", "Use the custom prefix" + (f" (adds {len(add)})" if add and exists("custom") else "")]
        if r["shortcut"] is None and shutil.which("steamos-add-to-steam"):
            items = ["steam", f"Add to Steam, then the {rec} prefix line"] + items
        pick = kdialog("--menu", html(f"Check: {os.path.basename(path)}", *report_lines(r, conf["custom"]["components"])),
                       *items, size="760x640")
        if pick is None:
            return
        busy = running_install()
        if busy:
            kdialog("--sorry", html("Installation running", f"{busy[0]} (for {busy[1]}).", "Wait until it finishes."))
            return
        check_protontricks()
        protons = find_protons()
        if not protons:
            kdialog("--error", html("No Proton found", "Install a Proton in Steam first (Library > Tools)."))
            return
        if pick == "steam":
            if subprocess.run(["steamos-add-to-steam", path], capture_output=True).returncode != 0:
                raise Error("Adding to Steam failed. Add it by hand: Steam > Games > Add a Non-Steam Game.")
            gui_fixed(protons, conf, rec, r["env"], None,
                      "Steam shows the game in its library in a few seconds. Paste the line there.")
            return
        if pick == "line":
            gui_fixed(protons, conf, rec, r["env"], r["shortcut"])
            return
        if exists("custom"):
            tool = current_tool(protons, conf, "custom")
        else:
            tool = pick_proton(protons, conf, "custom", "Proton for the custom prefix",
                               "Games that use the custom prefix must run on the same Proton.")
            if tool is None:
                return
        components = sorted(set(conf["custom"]["components"] or [c[0] for c in COMPONENTS if c[2]]) | set(r["needs"]),
                            key=VERBS.index)
        action, todo = plan("custom", tool, components, conf)
        if action != "add" or todo:
            with_progress(step_count(action, todo, False), run_apply, "custom", tool, components)
        show_line("Custom prefix is ready", "custom", tool, env=r["env"], game=r["shortcut"])
    except Error as e:
        kdialog("--error", html("Something went wrong", str(e)))


def setup():
    """Menu entry (with Check and Uninstall actions) and Dolphin's right-click entry on .exe files."""
    os.makedirs(os.path.dirname(DESKTOP), exist_ok=True)
    with open(DESKTOP, "w", encoding="utf-8") as f:
        f.write(f"""[Desktop Entry]
Type=Application
Name=Elemental Prefix
Comment=Shared Proton prefixes for non-Steam games and apps
Exec=python3 {APP}
Icon=applications-games
Categories=Game;Utility;
Terminal=false
Actions=check;uninstall;

[Desktop Action check]
Name=Check game dependencies
Exec=python3 {APP} check --gui

[Desktop Action uninstall]
Name=Uninstall Elemental Prefix
Exec=python3 {APP} uninstall --gui
""")
    os.makedirs(os.path.dirname(SERVICE_MENU), exist_ok=True)
    with open(SERVICE_MENU, "w", encoding="utf-8") as f:
        f.write(f"""[Desktop Entry]
Type=Service
MimeType=application/x-ms-dos-executable;application/x-msdownload;application/vnd.microsoft.portable-executable;application/x-ms-ne-executable;
Actions=check;
X-KDE-Priority=TopLevel

[Desktop Action check]
Name=Check game dependencies
Icon=applications-games
Exec=python3 {APP} check --gui %f
""")
    os.chmod(SERVICE_MENU, 0o755)  # Plasma 6 ignores service menus that are not executable
    if shutil.which("kbuildsycoca6"):
        subprocess.run(["kbuildsycoca6"], capture_output=True)


def uninstall(use_gui, delete_prefixes=False):
    """Remove the program, menu entry and settings. The prefixes stay unless asked (game saves)."""
    if running_install():
        raise Error("An installation is running. Wait until it finishes.")
    built = [pdir(n) for n in PREFIXES if os.path.isdir(pdir(n))]
    if use_gui:
        if kdialog("--yesno", html("Uninstall Elemental Prefix?",
                                   "Removes the app and its menu entry.")) is None:
            return
        if built:
            delete_prefixes = kdialog("--warningyesno", html(
                "Also delete the prefixes?",
                *built,
                "Games that use them will stop working, and game saves kept inside them will be lost. "
                "Choose No to keep them.")) is not None
    if delete_prefixes and any(in_use(p) for p in built):
        raise Error("A game is using a prefix. Close it and try again.")
    for p in (DESKTOP, SERVICE_MENU, CONF, APP, LOG, STATE):
        if os.path.exists(p):
            os.remove(p)
    if delete_prefixes:
        shutil.rmtree(BASE, ignore_errors=True)
    else:
        shutil.rmtree(os.path.join(BASE, "__pycache__"), ignore_errors=True)
    msg = "Elemental Prefix uninstalled."
    if built and not delete_prefixes:
        msg += f"\nThe prefixes stay in {BASE}."
    if use_gui:
        kdialog("--msgbox", html(*msg.split("\n")))
    else:
        print(msg)


# ---------- command line ----------

def find_tool(protons, name):
    for t in protons:
        if name.lower() in (t["name"].lower(), t["key"].lower()):
            return t
    raise Error(f"Proton not found: {name}. See: elemental-prefix.py protons")


def main():
    ap = argparse.ArgumentParser(prog="elemental-prefix.py", description="Shared Proton prefixes for non-Steam games.")
    ap.add_argument("--version", action="version", version=f"Elemental Prefix {VERSION}")
    sub = ap.add_subparsers(dest="cmd")  # no command: dialogs
    sub.add_parser("protons")
    sub.add_parser("components")
    sub.add_parser("status")
    a = sub.add_parser("apply")
    a.add_argument("prefix", choices=list(PREFIXES))
    a.add_argument("--proton")
    a.add_argument("--components", help="custom only: comma-separated winetricks verbs")
    a.add_argument("--yes", action="store_true", help="allow rebuilding the custom prefix")
    r = sub.add_parser("reset")
    r.add_argument("prefix", choices=list(FIXED))
    r.add_argument("--proton")
    r.add_argument("--yes", action="store_true")
    m = sub.add_parser("migrate")
    m.add_argument("--proton")
    ln = sub.add_parser("line")
    ln.add_argument("prefix", choices=list(PREFIXES))
    c = sub.add_parser("check")
    c.add_argument("exe", nargs="?")
    c.add_argument("--gui", action="store_true", help="show the result in a dialog (used by the menus)")
    sub.add_parser("setup")
    u = sub.add_parser("uninstall")
    u.add_argument("--gui", action="store_true", help="ask with dialogs (used by the menu entry)")
    u.add_argument("--delete-prefixes", action="store_true", help="also delete the prefixes and backups")
    args = ap.parse_args()
    if args.cmd is None:
        return gui()
    if args.cmd == "setup":
        return setup()
    if args.cmd == "check":
        if args.gui:
            return gui_check(args.exe)
        if not args.exe:
            raise Error("Give the game's .exe: elemental-prefix.py check GAME.exe")
        r = check_game(args.exe)
        print("\n".join(report_lines(r, load_conf()["custom"]["components"])))
        if r["shortcut"]:
            text, _ = merged_line(r["shortcut"]["opts"], r["prefix"], r["env"])
            print(f"\nLaunch Options line for {r['shortcut']['name']} (paste over the whole old line):\n  " + text)
        else:
            print("\nLaunch Options line:\n  " + line(r["prefix"], r["env"]))
        return
    if args.cmd == "uninstall":
        if args.gui:
            try:
                return uninstall(True)
            except Error as e:
                kdialog("--error", html("Something went wrong", str(e)))
                return
        return uninstall(False, args.delete_prefixes)

    protons = find_protons()
    conf = load_conf()

    def tool_for(name, explicit):
        tool = find_tool(protons, explicit) if explicit else current_tool(protons, conf, name)
        if tool is None:
            raise Error("No Proton found. Install one in Steam first.")
        return tool

    if args.cmd == "protons":
        cur = current_tool(protons, conf, "shared")
        for t in protons:
            print(f"{'*' if t is cur else ' '} {t['name']:28} {t['dir']}")
    elif args.cmd == "components":
        chosen = conf["custom"]["components"] or [c[0] for c in COMPONENTS if c[2]]
        for verb, label, _ in COMPONENTS:
            print(f"{'*' if verb in chosen else ' '} {verb:16} {label}"
                  + ("  (shared)" if verb in SAFE else "  (legacy)"))
    elif args.cmd == "status":
        for n in PREFIXES:
            c = conf[n]
            print(f"{n}: {pdir(n)} ({'ready' if exists(n) else 'not built'})")
            if exists(n):
                print(f"  built with: {c.get('proton_name', '-')}, last run: {proton_version(n) or '-'}")
                print(f"  components: {' '.join(c['components']) or '-'}")
                print(f"  {games_text(pdir(n))}")
                for w in proton_warnings(n):
                    print(f"  warning: {w}")
        if os.path.isdir(OLD_PREFIX):
            print(f"version 1 prefix: {OLD_PREFIX} ({'moved' if conf.get('migrated') == '1' else 'not moved yet'})")
            old = games_using(OLD_PREFIX)
            if old:
                print("  still used by: " + ", ".join(old))
        busy = running_install()
        print(f"installing: {busy[0]} (for {busy[1]})" if busy else "installing: no")
    elif args.cmd in ("apply", "reset"):
        name = args.prefix
        if name in FIXED:
            if getattr(args, "components", None):
                raise Error(f"The {name} prefix has a fixed set of components.")
            if args.cmd == "apply" and exists(name) and args.proton:
                print("The prefix exists: a newer Proton upgrades it by itself. "
                      f"To build it again: elemental-prefix.py reset {name} --proton NAME --yes")
                args.proton = None
            components = PREFIXES[name][1]
        elif args.components is not None:
            components = [c.strip() for c in args.components.split(",") if c.strip()]
            bad = [c for c in components if c not in VERBS]
            if bad:
                raise Error("Unknown component: " + ", ".join(bad))
        else:
            components = conf["custom"]["components"] or [c[0] for c in COMPONENTS if c[2]]
        if args.cmd == "reset" and not exists(name):
            raise Error(f"The {name} prefix is not built yet. Use: elemental-prefix.py apply {name}")
        tool = tool_for(name, args.proton)
        run_apply(name, tool, components, args.yes, reset=args.cmd == "reset")
        copied = copy_line(line(name))
        print("\nDone. Launch Options line" + (" (copied to the clipboard)" if copied else "") + ":")
        print(f"  {line(name)}")
        print(done_text(name, tool))
    elif args.cmd == "migrate":
        old_games = games_using(OLD_PREFIX)
        tool = find_tool(protons, args.proton) if args.proton else next(
            (t for t in protons if t["key"] == conf["v1"].get("proton")), None) or tool_for("shared", None)
        migrate(tool)
        print(f"\nDone. New Launch Options line" + (" (copied to the clipboard)" if copy_line(line("shared")) else "") + ":")
        print(f"  {line('shared')}")
        print(f"{OLD_PREFIX} stays as a backup.")
        if old_games:
            print("Paste the new line into: " + ", ".join(old_games))
    elif args.cmd == "line":
        print(line(args.prefix) + ("\n(copied to the clipboard)" if copy_line(line(args.prefix)) else ""))


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
