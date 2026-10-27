# Elemental Prefix – specification

**English** | [Polski](SPEC.pl.md)

## Goal

Old Windows games and programs added to Steam as non-Steam games often fail because a fresh
Proton prefix has no Visual C++, DirectX 9 or similar libraries. Today they have to be
installed with Protontricks for every game separately.

Elemental Prefix prepares **one shared prefix** with the chosen libraries once. Any non-Steam
game then uses it with one line in its Launch Options:

```
STEAM_COMPAT_DATA_PATH=/home/deck/Games/shared-prefix %command%
```

## Decisions

- One shared prefix: `~/Games/shared-prefix`.
- Desktop Mode app with plain KDE dialogs (`kdialog`, already on the Deck). Nothing extra to install.
- Everything lives in the home folder, no `sudo`.
- English names and UI. Documentation in English and Polish.
- The Launch Options line is only copied to the clipboard. The app never edits Steam's files.
- Libraries are installed with winetricks from the Protontricks Flatpak (most Deck users have it).
  Without Protontricks the app says how to get it from Discover. The Flatpak cannot see
  `~/Games` or the SD card, so every call passes `--filesystem=` for the prefix and for the folder
  of the chosen Proton (no permanent override).
- Clipboard through Klipper: `qdbus6` (or `qdbus`) `org.kde.klipper /klipper setClipboardContents`.
  Desktop Mode runs on Wayland and has no `wl-copy` or `xclip`.

## Flow

0. **Start screen** (only when the prefix exists) – shows its Proton and components, with two
   choices: copy the Launch Options line, or change Proton or components (steps 1–4).
1. **Proton** – a list of installed Proton versions: Steam's own (`steamapps/common/Proton*`,
   in every Steam library, including the SD card) and custom ones (`compatibilitytools.d`, e.g. GE-Proton).
   Preselected: the Proton of the existing prefix, otherwise Steam's default compatibility tool
   (`CompatToolMapping` entry `0` in `config/config.vdf`). With Steam's default the game needs
   nothing set in Compatibility, only the Launch Options line.
   Custom tools are listed by `display_name` from `compatibilitytool.vdf`, not the folder name
   (GE-Proton archives now end in `-x86_64`).
2. **Components** – a checklist. Preselected marked with ✓:

   | Component | winetricks verb | Default |
   |---|---|---|
   | Visual C++ 2015–2022 | `vcrun2022` | ✓ |
   | Visual C++ 2013 | `vcrun2013` | |
   | Visual C++ 2012 | `vcrun2012` | |
   | Visual C++ 2010 | `vcrun2010` | ✓ |
   | Visual C++ 2008 | `vcrun2008` | ✓ |
   | Visual C++ 2005 | `vcrun2005` | |
   | DirectX 9 (d3dx9) | `d3dx9` | ✓ |
   | XAudio / XACT sound | `xact` | ✓ |
   | Shader compiler for DX11 games | `d3dcompiler_47` | |
   | Windows fonts | `corefonts` | ✓ |
   | .NET Framework 4.8 (large, slow) | `dotnet48` | |
   | PhysX | `physx` | |
   | Videos in old games | `quartz` | |

   All verbs exist in winetricks 20260125 from Protontricks 1.15.0 (checked in stage 0).
3. **Install** – creates the prefix with the chosen Proton (`proton run wineboot`), then installs
   the components. A progress dialog shows the current step and, every 30 s, the time spent on it;
   the full output goes to `~/.local/share/elemental-prefix/install.log`. A notification appears when
   it ends. The app refuses to start while a game runs on the prefix or another installation runs.
4. **Done** – shows the Launch Options line (already copied to the clipboard) and a reminder:
   games using the prefix must use the same Proton in Properties → Compatibility (nothing to set
   when it is Steam's default).

Dialogs: fixed sizes (`--geometry`), a bold heading and short text wrapped by hand at about 60
characters, because kdialog widens the window to the longest line instead of wrapping. List items
stay under about 45 characters. The progress window ignores `--geometry`, so its text is a
fixed-width `<table>` block with the same number of lines in every step.

Running the app again:

- **Add components** – installs only the newly checked ones.
- **Remove components or change Proton** – winetricks cannot uninstall, and switching Proton
  versions back and forth breaks prefixes. The app rebuilds the prefix and first renames the old
  one to `shared-prefix.backup-<date>`. The Windows user folder (`drive_c/users/steamuser`: Documents,
  AppData, Saved Games - where games keep saves) is copied into the new prefix; components live in
  `drive_c/windows`, so the rebuild still drops them.

## Files

- Program: `~/.local/share/elemental-prefix/`
- Settings (chosen Proton, components): `~/.config/elemental-prefix.conf`
- Menu entry: `~/.local/share/applications/elemental-prefix.desktop` (“Elemental Prefix”)
- Prefix: `~/Games/shared-prefix`

## Stages

0. **Check on the Deck by hand** (commands sent with DeckKeys): create a prefix with Proton outside
   Steam, run winetricks from the Protontricks Flatpak against it, start a non-Steam game with the
   Launch Options line. Nothing gets built before this works.
   **Passed 2026-10-25** (SteamOS 3.9.5): prefix from Proton 11.0 and GE-Proton11-11 with
   `proton run wineboot -u`, `vcrun2010` from the Flatpak, a non-Steam game (Atelier Yumia) ran on the
   shared prefix with GE-Proton11-11 inside SteamLinuxRuntime_4, clipboard through Klipper.
1. Script without dialogs: Proton detection, prefix creation, component installation. **Done.**
2. Dialogs (`kdialog`): Proton list, checklist, progress, final screen, clipboard. **Done.**
3. Installer (`curl … install.sh | bash`), menu entry with an Uninstall action, README (EN + PL),
   MIT license. **Done.**

## Version 2 (planned 2026-10-27)

Version 1 asks which components to install. Version 2 drops most of that choice: libraries side by
side do not hurt games that do not use them, so a fixed safe set covers almost every game. Instead
the app learns to tell what a game needs. Games are copied to the Deck as ready folders (installed
on a PC); the app does not install games.

### Prefixes

All in `~/.local/share/elemental-prefix/` on the internal drive (never the SD card: removing the card
would break every game on the prefix):

| Prefix | Components | Chosen by |
|---|---|---|
| `shared-prefix` | safe set: `vcrun2005`, `vcrun2008`, `vcrun2010`, `vcrun2012`, `vcrun2013`, `vcrun2022`, `d3dx9`, `d3dcompiler_47`, `xact`, `physx`, `corefonts` | fixed |
| `shared-prefix-legacy` | safe set + `quartz` + `dotnet48` | fixed |
| `shared-prefix-custom` | any from the version 1 checklist | the user |

- `quartz` replaces Proton's built-in video playback and can break videos in games that played them
  fine, so it is only in legacy. `dotnet48` is large, slow and the most likely to fail, so it is there
  too. Bink (`binkw32.dll`) and Smacker videos ship with the game and need nothing.
- Only one custom prefix. Several named ones would turn the app into Bottles.
- Backups from rebuilds: `~/.local/share/elemental-prefix/backups/`.
- Game files never go inside a prefix folder. Games installed into a prefix's `Program Files` by
  hand are lost on a rebuild; the user reinstalls them.

### Changing Proton, rebuilds

- Shared and legacy are built once and then left alone. A newer Proton upgrades an existing prefix
  by itself on the first game start, so the app asks for a Proton only when building them; the
  Proton a game runs on is set in Steam (Properties → Compatibility).
- **Reset prefix (advanced)** rebuilds shared or legacy only when it is broken or for an older
  Proton. Same backup and save copying as in version 1.
- Custom keeps the version 1 behaviour: adding components installs them, removing any rebuilds.
- Before a reset or a custom rebuild the app lists the games that use that prefix.

### Moving from version 1

One time: the prefix is built in the new place, `drive_c/users/steamuser` is copied over, the old
`~/Games/shared-prefix` stays as a backup. The app lists the games whose Launch Options still point to
the old path; the user pastes the new line into each.

### Launch Options line

```
STEAM_COMPAT_DATA_PATH=/home/deck/.local/share/elemental-prefix/shared-prefix PROTON_LOG=1 WINEDEBUG=fixme-all %command%
```

- `PROTON_LOG=1` makes Proton write a log the check can read. On its own it logs far too much
  (353 MB in 10 minutes of play); with `WINEDEBUG=fixme-all` it keeps errors only (831 KB).
- Other tools add to the same line: variables (e.g. `PROTON_FSR4_UPGRADE=1`), wrappers before
  `%command%` (e.g. `~/lsfg` from Decky LSFG-VK), game arguments after it. A variable placed after a
  wrapper or after `%command%` does not work.
- The copied line is **merged**: the app reads the game's current Launch Options from
  `shortcuts.vdf` (read only), splits them into variables / wrappers / `%command%` / arguments,
  drops an old Elemental Prefix entry, puts its own variables at the very start and keeps the rest
  in the user's order. The user pastes it over the whole old line.
- The check warns when `STEAM_COMPAT_DATA_PATH` stands after a wrapper or `%command%`, when
  `%command%` appears twice, or when the line is missing (probably overwritten by another tool).
- **Proton per game:** Proton rewrites the prefix to its own version on every start, so all games
  on one prefix should use the same Proton. The app reads each game's compatibility tool from
  Steam's `config/config.vdf` (`CompatToolMapping`, key = the shortcut's `appid`; read only) and
  warns when a game on one of its prefixes uses a different Proton than the prefix (e.g. "Fantasy
  Life runs on Proton Experimental – set GE-Proton11-11"). Shown next to the game list when a
  prefix is chosen and in Check game dependencies.

### Check game dependencies

Right-click a game's `.exe` in Dolphin (service menu), or the same action in the app's menu entry.
Works without Steam: it reads the game files.

1. **Imports** – reads the PE import tables of the `.exe` and `.dll` files in the game folder and
   maps them to components (e.g. `MSVCR120.dll` → `vcrun2013`, `d3dx9_43.dll` → `d3dx9`). Python
   standard library only. Also detects .NET executables (CLR header) and Bink.
2. **Game folder** – redistributable folders and files (`_CommonRedist`, `Redist`, `DirectX`,
   `vcredist*.exe`) as hints; `dxgi.dll`, `d3d11.dll`, `d3d12.dll` next to the `.exe` (ReShade and
   similar mods) → suggests `WINEDLLOVERRIDES="dxgi=n,b"` (or the matching DLL).
3. **Proton log** – after a failed start, reads `~/steam-<id>.log`, where `<id>` is
   `(appid << 32) | 0x02000000` with the shortcut's `appid` from `shortcuts.vdf`, and
   looks for `Library … not found` and similar lines. Lines it does not recognise are shown as an
   excerpt, without guessing.
4. **Registry** – registry paths written as text in the `.exe` (`SOFTWARE\…`) and the keys listed in
   Inno Setup's `unins000.dat` are compared with the prefix registry. Missing ones are reported as
   "probably needed", with the key name to export on the PC.

The result names the prefix to use (shared, legacy, or custom plus what to add to it), shows which
prefix the game uses now (shared / legacy / custom / other `STEAM_COMPAT_DATA_PATH` / its own
`compatdata/<appid>` / not started yet), copies the merged line and, for a game not yet in Steam,
offers SteamOS's built-in "Add to Steam". Components are installed only into the app's own prefixes,
never into a game's own prefix.

### Registry import

Right-click a `.reg` file → **Import to Elemental Prefix** → choose the prefix → `wine regedit`.
Old boxed games read install keys (path, version, CD key) that only their installer writes; the user
exports the key with `regedit` on the PC. The check also offers to import a `.reg` file found in the
game folder.

### Documentation notes

- Two games of the same series can write saves to the same `AppData` folder in a shared prefix and
  overwrite each other; move one of them to custom.
- No promises like "99 % of games". The prefixes fix missing libraries, not anti-cheat, DRM or
  Proton bugs.

### Stages

4. **Check on the Deck by hand:** the Protontricks Flatpak with `--filesystem` under
   `~/.local/share`; a newer Proton upgrading a prefix built outside Steam; `PROTON_LOG=1` log name
   and place for a non-Steam game; how soon Steam writes Launch Options to `shortcuts.vdf`; a Dolphin
   service menu on `.exe` and `.reg`; calling SteamOS's "Add to Steam" from a script.
5. Three prefixes in the new place, safe set, legacy, custom checklist, Reset prefix, moving from
   version 1. **Done, passed on the Deck 2026-10-27.**
6. Check game dependencies: imports, .NET, Bink, game folder, prefix recommendation, installing
   missing components into custom. **Done, passed on the Deck 2026-10-27.** An `.exe` in a folder
   shared by many games (a drive, a Steam library, the home folder) is checked alone, without
   subfolders; "not found" lists only normal (not delay-loaded) imports of the `.exe` and the DLLs
   next to it. Dolphin's entry and the menu entry are written by `elemental-prefix.py setup`,
   which `install.sh` runs.
7. Launch Options: reading `shortcuts.vdf`, merged line, warnings, game lists in reset and move
   messages, Proton per game warning, "Add to Steam". **Done, passed on the Deck 2026-10-27.**
   Steam writes a changed Compatibility setting to `config.vdf` at once. The Proton warning compares a
   game with what most games on its prefix use (a tie: with the Proton the prefix was built with; a
   game alone on a prefix gets no warning, it may run a newer Proton). The "line is missing" warning
   was dropped: the app cannot know a game ever had its line. `steamos-add-to-steam` runs without
   captured output (the `steam` command can keep the pipe open) and a 30 s limit. Shortcuts without a
   full path (`flatpak` for Chiaki, Protontricks) are ignored when looking for a game.
8. Proton log reading. **Done, passed on the Deck 2026-10-27** (a game that runs: no false
   alarms). .NET is told only from the `.exe`: `err:mscoree` lines appear in most games' logs. Errors
   seen in logs of games that run fine (openxr, crypt certificates, hid, ntoskrnl, steamclient) are
   not shown.
9. Registry hints and `.reg` import.
10. README (EN + PL) and screenshots.

Nothing gets built before stage 4 passes.

**Stage 4 results (2026-10-27, passed):**

- The Protontricks Flatpak installs into a prefix under `~/.local/share/elemental-prefix` with
  `--filesystem` on the prefix and the Proton folder (vcrun2010 in 16 s).
- A prefix built with Proton 11.0 outside Steam was upgraded by GE-Proton11-11 on the first game
  start (`version` file `11.0-100` → `GE-Proton11-11`); the game ran.
- Steam writes a changed Launch Options line to `shortcuts.vdf` within seconds, no restart needed.
- Log: `~/steam-<id>.log`, `<id>` = `(appid << 32) | 0x02000000`. A test prefix with only
  vcrun2010 gave `err:module:import_dll Library mfc140u.dll (which is needed by …) not found` –
  the kind of line the log check reads.
- A service menu in `~/.local/share/kio/servicemenus/` (file made executable) shows on `.exe`
  (`application/x-msdownload`) and `.reg` (`text/x-ms-regedit`).
- "Add to Steam" is `/usr/bin/steamos-add-to-steam [-ui] <path>` (opens
  `steam://addnonsteamgame/…`); not run yet, tried in stage 7.

### Ideas to look into later

- protonfixes from the umu database: GE-Proton may apply per-game fixes to a non-Steam game given
  `UMU_ID`. Unchecked.

## Not planned

- Editing Steam's shortcuts or Launch Options automatically (writing `shortcuts.vdf`).
- Installing games from installers or archives; games are copied as folders.
- Logging registry access (`WINEDEBUG=+reg`).
- Several custom prefixes.
- Game Mode UI (Decky panel).
- Patched Proton builds for bypassing copy protection.
