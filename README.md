# Elemental Prefix

**English** | [Polski](README.pl.md)

One shared Proton prefix with Visual C++, DirectX 9 and other common libraries for non-Steam
games and apps on the **Steam Deck** (SteamOS, Desktop Mode).

Old Windows games and programs added to Steam as non-Steam games often fail to start because a
fresh Proton prefix has none of these libraries. Instead of installing them with Protontricks for
every game, Elemental Prefix prepares one prefix once. Any non-Steam game can then use it with one
line in its Launch Options:

```
STEAM_COMPAT_DATA_PATH=/home/deck/Games/shared-prefix %command%
```

## Requirements

- Steam Deck in Desktop Mode.
- **Protontricks** from Discover. Elemental Prefix uses its winetricks.
- At least one Proton installed in Steam, or a custom one such as GE-Proton.

Nothing else to install, no `sudo`.

## Install

In Desktop Mode open Konsole and run:

```bash
curl -fsSL https://raw.githubusercontent.com/Koutasora/Elemental-Prefix/main/install.sh | bash
```

Run the same command again to update.

## Use

1. Open **Elemental Prefix** from the application menu.
2. Choose the Proton. Steam's default one is preselected - with it the games need nothing set in
   Compatibility.
3. Tick the components. The usual ones are already ticked.
4. Wait for the installation. The window shows each step; large components can take several minutes.
5. The Launch Options line is copied to the clipboard. In Steam open the game's
   **Properties → General → Launch Options** and paste it.

If the game is set to a different Proton in Properties → Compatibility, set it to the same one as
the prefix. Mixing Proton versions on one prefix breaks it.

### Components

| Component | winetricks verb | Ticked by default |
|---|---|---|
| Visual C++ 2015–2022 | `vcrun2022` | yes |
| Visual C++ 2013 | `vcrun2013` | |
| Visual C++ 2012 | `vcrun2012` | |
| Visual C++ 2010 | `vcrun2010` | yes |
| Visual C++ 2008 | `vcrun2008` | yes |
| Visual C++ 2005 | `vcrun2005` | |
| DirectX 9 (d3dx9) | `d3dx9` | yes |
| XAudio / XACT sound | `xact` | yes |
| Shader compiler for DX11 games | `d3dcompiler_47` | |
| Windows fonts | `corefonts` | yes |
| .NET Framework 4.8 (large, slow) | `dotnet48` | |
| PhysX | `physx` | |
| Videos in old games | `quartz` | |

### Changing the prefix later

- **Adding components** installs only the new ones.
- **Removing components or changing Proton** builds a new prefix. winetricks cannot uninstall, and
  switching Proton on an existing prefix breaks it. The old prefix is kept as
  `~/Games/shared-prefix.backup-<date>`, including any game saves stored inside it. Delete it
  yourself once you no longer need it.

## Uninstall

Right-click **Elemental Prefix** in the application menu and choose **Uninstall Elemental Prefix**.
It asks whether to delete the shared prefix as well; the default is to keep it.

## Files

| What | Where |
|---|---|
| Program and install log | `~/.local/share/elemental-prefix/` |
| Settings | `~/.config/elemental-prefix.conf` |
| Menu entry | `~/.local/share/applications/elemental-prefix.desktop` |
| Shared prefix | `~/Games/shared-prefix` |

The app never edits Steam's files.

## Command line

The same works from Konsole:

```bash
EP=~/.local/share/elemental-prefix/elemental-prefix.py
python3 $EP protons            # installed Proton versions (* = selected)
python3 $EP components         # components (* = selected)
python3 $EP status             # prefix, Proton, components, running installation
python3 $EP apply --proton GE-Proton11-11-x86_64 --components vcrun2022,d3dx9
python3 $EP apply --yes        # allow rebuilding the prefix
python3 $EP line               # copy the Launch Options line
python3 $EP uninstall          # add --delete-prefix to remove the prefix too
```

## Limits

- One shared prefix. Games that need conflicting settings should keep their own prefix.
- Desktop Mode only. In Game Mode the games run normally; only the app itself needs the desktop.
- Launch Options are set by hand. The app does not change Steam shortcuts.

## License

MIT - see [LICENSE](LICENSE).
