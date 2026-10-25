#!/usr/bin/env python3
"""Elemental Prefix - one shared Proton prefix for non-Steam games.

Stage 1: command line only. The kdialog front end (stage 2) calls the same functions.

  elemental-prefix.py protons                      list installed Proton versions
  elemental-prefix.py components                   list components (* = default)
  elemental-prefix.py status                       show the prefix and its settings
  elemental-prefix.py apply [--proton NAME] [--components a,b,c] [--yes]
  elemental-prefix.py line                         copy the Launch Options line
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
STEAM = os.path.join(HOME, ".local/share/Steam")
PREFIX = os.path.join(HOME, "Games/shared-prefix")
CONF = os.path.join(HOME, ".config/elemental-prefix.conf")
LOG = os.path.join(HOME, ".local/share/elemental-prefix/install.log")
STATE = os.path.join(HOME, ".local/share/elemental-prefix/running")  # pid, start time, current step
FLATPAK_APP = "com.github.Matoking.protontricks"
LINE = f"STEAM_COMPAT_DATA_PATH={PREFIX} %command%"

# (winetricks verb, label, preselected) - install order follows this list
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


# ---------- settings ----------

def load_conf():
    conf = {}
    try:
        with open(CONF, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and not k.startswith("#"):
                    conf[k.strip()] = v.strip()
    except OSError:
        pass
    conf["components"] = [c for c in conf.get("components", "").split() if c in VERBS]
    return conf


def save_conf(tool, components):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    with open(CONF, "w", encoding="utf-8") as f:
        f.write(f"proton={tool['key']}\nproton_name={tool['name']}\nproton_dir={tool['dir']}\n")
        f.write("components=" + " ".join(components) + "\n")


def current_tool(protons, conf):
    """Proton of the existing prefix, else Steam's default, else the newest-looking one."""
    if conf.get("proton"):
        for t in protons:
            if t["key"] == conf["proton"]:
                return t
    default = steam_default_tool()
    if default:
        for t in protons:
            if tool_matches(t, default):
                return t
    return protons[-1] if protons else None


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
    log(f"exit {p.returncode}")
    return p.returncode


def step(n, total, text):
    # One line per step, read by the progress dialog in stage 2.
    print(f"STEP {n}/{total}: {text}", flush=True)
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


def prefix_in_use():
    """True when a wineserver is running on the shared prefix (a game is open)."""
    target = os.path.join(PREFIX, "pfx")
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


def winetricks(tool, args):
    cmd = ["flatpak", "run", f"--filesystem={PREFIX}", f"--filesystem={tool['dir']}",
           f"--env=WINEPREFIX={PREFIX}/pfx",
           f"--env=WINE={wine_bin(tool['dir'], 'wine')}",
           f"--env=WINESERVER={wine_bin(tool['dir'], 'wineserver')}",
           "--command=winetricks", FLATPAK_APP] + args
    return cmd


def installed_verbs(tool):
    if not os.path.isdir(os.path.join(PREFIX, "pfx")):
        return []
    r = subprocess.run(winetricks(tool, ["list-installed"]), capture_output=True, text=True)
    return [v for v in r.stdout.split() if v in VERBS]


def create_prefix(tool):
    os.makedirs(PREFIX, exist_ok=True)
    env = dict(os.environ, STEAM_COMPAT_DATA_PATH=PREFIX, STEAM_COMPAT_CLIENT_INSTALL_PATH=STEAM)
    if run_logged([os.path.join(tool["dir"], "proton"), "run", "wineboot", "-u"], env) != 0 \
            or not os.path.isdir(os.path.join(PREFIX, "pfx/drive_c")):
        raise Error(f"Creating the prefix failed. Details: {LOG}")


def backup_prefix():
    dest = f"{PREFIX}.backup-{datetime.datetime.now():%Y-%m-%d-%H%M}"
    os.rename(PREFIX, dest)
    log(f"old prefix moved to {dest}")
    return dest


def plan(tool, components, conf):
    """What apply would do: 'create', 'add' or 'rebuild', plus the verbs to install."""
    if not os.path.isdir(os.path.join(PREFIX, "pfx")):
        return "create", components
    if conf.get("proton") and conf["proton"] != tool["key"]:
        return "rebuild", components
    have = installed_verbs(tool)
    if any(v in have and v not in components for v in VERBS):
        return "rebuild", components
    return "add", [v for v in components if v not in have]


def apply(tool, components, yes=False):
    if running_install():
        raise Error("Another installation is running. See: elemental-prefix.py status")
    check_protontricks()
    if prefix_in_use():
        raise Error("A game is using the shared prefix. Close it and try again.")
    conf = load_conf()
    components = [v for v in VERBS if v in components]
    action, todo = plan(tool, components, conf)
    if action == "rebuild" and not yes:
        raise Error("Removing components or changing Proton rebuilds the prefix "
                    f"(the old one is kept as {os.path.basename(PREFIX)}.backup-<date>). Run again with --yes.")
    log(f"\n##### {datetime.datetime.now():%Y-%m-%d %H:%M:%S} apply {action}: {tool['name']} {' '.join(components)}")
    total = len(todo) + (1 if action != "add" else 0)
    n = 0
    if action == "rebuild":
        print("Old prefix kept as " + backup_prefix(), flush=True)
    if action != "add":
        n += 1
        step(n, total, f"Creating the prefix with {tool['name']}")
        create_prefix(tool)
    done = [v for v in components if v not in todo]
    save_conf(tool, done)
    label = dict((c[0], c[1]) for c in COMPONENTS)
    failed = []
    for v in todo:
        n += 1
        step(n, total, f"Installing {label[v]}")
        if run_logged(winetricks(tool, ["-q", v])) == 0:
            done.append(v)
        else:
            failed.append(v)
        save_conf(tool, [x for x in VERBS if x in done])
    if failed:
        raise Error("Not installed: " + ", ".join(label[v] for v in failed) + f". Details: {LOG}")
    return action


def copy_line():
    for q in ("qdbus6", "qdbus"):
        if shutil.which(q) and subprocess.run(
                [q, "org.kde.klipper", "/klipper", "setClipboardContents", LINE], capture_output=True).returncode == 0:
            return True
    return False


# ---------- command line ----------

def find_tool(protons, name):
    for t in protons:
        if name.lower() in (t["name"].lower(), t["key"].lower()):
            return t
    raise Error(f"Proton not found: {name}. See: elemental-prefix.py protons")


def main():
    ap = argparse.ArgumentParser(prog="elemental-prefix.py", description="One shared Proton prefix for non-Steam games.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("protons")
    sub.add_parser("components")
    sub.add_parser("status")
    a = sub.add_parser("apply")
    a.add_argument("--proton")
    a.add_argument("--components", help="comma-separated winetricks verbs; default: current or preselected")
    a.add_argument("--yes", action="store_true", help="allow rebuilding the prefix")
    sub.add_parser("line")
    args = ap.parse_args()

    protons = find_protons()
    conf = load_conf()
    if args.cmd == "protons":
        cur = current_tool(protons, conf)
        for t in protons:
            print(f"{'*' if t is cur else ' '} {t['name']:28} {t['dir']}")
    elif args.cmd == "components":
        chosen = conf["components"] or [c[0] for c in COMPONENTS if c[2]]
        for verb, label, _ in COMPONENTS:
            print(f"{'*' if verb in chosen else ' '} {verb:16} {label}")
    elif args.cmd == "status":
        exists = os.path.isdir(os.path.join(PREFIX, "pfx"))
        print(f"prefix:     {PREFIX} ({'ready' if exists else 'not created'})")
        print(f"proton:     {conf.get('proton_name', '-')}")
        print(f"components: {' '.join(conf['components']) or '-'}")
        print(f"launch:     {LINE}")
        busy = running_install()
        print(f"installing: {busy[0]} (for {busy[1]})" if busy else "installing: no")
    elif args.cmd == "apply":
        tool = find_tool(protons, args.proton) if args.proton else current_tool(protons, conf)
        if tool is None:
            raise Error("No Proton found. Install one in Steam first.")
        if args.components is not None:
            components = [c.strip() for c in args.components.split(",") if c.strip()]
            bad = [c for c in components if c not in VERBS]
            if bad:
                raise Error("Unknown component: " + ", ".join(bad))
        else:
            components = conf["components"] or [c[0] for c in COMPONENTS if c[2]]
        try:
            apply(tool, components, args.yes)
        except Error as e:
            notify(f"Installation failed: {e}")
            raise
        finally:
            clear_state()
        notify("Shared prefix ready.")
        copied = copy_line()
        print("\nDone. Launch Options line" + (" (copied to the clipboard)" if copied else "") + ":")
        print(f"  {LINE}")
        print(f"Games using it need {tool['name']} in Properties > Compatibility"
              + (" (Steam's default - nothing to set)." if tool_matches(tool, steam_default_tool() or "") else "."))
    elif args.cmd == "line":
        print(LINE + ("\n(copied to the clipboard)" if copy_line() else ""))


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
