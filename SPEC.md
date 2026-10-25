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

## Not planned

- Editing Steam's shortcuts or Launch Options automatically.
- Several prefixes.
- Game Mode UI (Decky panel).
