# Elemental Prefix

[English](README.md) | **Polski**

Jeden wspólny prefiks Protona z Visual C++, DirectX 9 i innymi popularnymi bibliotekami dla gier
i programów spoza Steama na **Steam Decku** (SteamOS, tryb pulpitu).

Stare gry i programy z Windowsa dodane do Steama jako gry spoza Steama często się nie uruchamiają,
bo świeży prefiks Protona nie ma tych bibliotek. Zamiast instalować je przez Protontricks w każdej
grze osobno, Elemental Prefix raz przygotowuje jeden prefiks. Każda gra spoza Steama korzysta z niego
dzięki jednej linijce w Opcjach uruchamiania:

```
STEAM_COMPAT_DATA_PATH=/home/deck/Games/shared-prefix %command%
```

## Wymagania

- Steam Deck w trybie pulpitu.
- **Protontricks** z Discover. Elemental Prefix korzysta z jego winetricks.
- Co najmniej jeden Proton zainstalowany w Steamie albo własny, np. GE-Proton.

Nic więcej do instalowania, bez `sudo`.

## Instalacja

W trybie pulpitu otwórz Konsole i uruchom:

```bash
curl -fsSL https://raw.githubusercontent.com/Koutasora/Elemental-Prefix/main/install.sh | bash
```

To samo polecenie uruchomione ponownie aktualizuje aplikację.

## Użycie

1. Otwórz **Elemental Prefix** z menu aplikacji.
2. Wybierz Protona. Domyślny Proton Steama jest już zaznaczony – z nim gry nie wymagają żadnych
   ustawień w Zgodności.
3. Zaznacz składniki. Najczęściej potrzebne są już zaznaczone.
4. Zaczekaj na instalację. Okno pokazuje każdy krok; duże składniki mogą trwać kilka minut.
5. Linijka do Opcji uruchamiania trafia do schowka. W Steamie otwórz grę:
   **Właściwości → Ogólne → Opcje uruchamiania** i wklej ją.

Jeśli gra ma w Właściwości → Zgodność ustawiony inny Proton, ustaw ten sam co prefiks. Różne wersje
Protona na jednym prefiksie go psują.

### Składniki

| Składnik | polecenie winetricks | Domyślnie zaznaczony |
|---|---|---|
| Visual C++ 2015–2022 | `vcrun2022` | tak |
| Visual C++ 2013 | `vcrun2013` | |
| Visual C++ 2012 | `vcrun2012` | |
| Visual C++ 2010 | `vcrun2010` | tak |
| Visual C++ 2008 | `vcrun2008` | tak |
| Visual C++ 2005 | `vcrun2005` | |
| DirectX 9 (d3dx9) | `d3dx9` | tak |
| Dźwięk XAudio / XACT | `xact` | tak |
| Kompilator shaderów dla gier DX11 | `d3dcompiler_47` | |
| Czcionki Windows | `corefonts` | tak |
| .NET Framework 4.8 (duży, wolny) | `dotnet48` | |
| PhysX | `physx` | |
| Filmy w starych grach | `quartz` | |

Aplikacja ma angielski interfejs, więc w okienkach składniki mają angielskie nazwy.

### Późniejsze zmiany

- **Nowe wersje Protona** (np. nowy GE-Proton) pojawiają się na liście same. Prefiks zostaje na swoim
  Protonie, dopóki nie wybierzesz innego. Nie usuwaj Protona, na którym stoi prefiks – gry z prefiksu
  przestaną się uruchamiać, dopóki go nie przebudujesz.
- **Dodanie składników** instaluje tylko nowe.
- **Usunięcie składników albo zmiana Protona** buduje nowy prefiks. winetricks nie umie
  odinstalowywać, a zmiana Protona na istniejącym prefiksie go psuje. Stary prefiks zostaje jako
  `~/Games/shared-prefix.backup-<data>`. Zapisy i ustawienia gier (folder użytkownika Windows) są
  kopiowane do nowego prefiksu. Kopię usuń sam, gdy gry działają.

## Odinstalowanie

Kliknij prawym przyciskiem **Elemental Prefix** w menu aplikacji i wybierz
**Uninstall Elemental Prefix**. Aplikacja zapyta, czy usunąć też wspólny prefiks; domyślnie zostaje.

## Pliki

| Co | Gdzie |
|---|---|
| Program i log instalacji | `~/.local/share/elemental-prefix/` |
| Ustawienia | `~/.config/elemental-prefix.conf` |
| Pozycja w menu | `~/.local/share/applications/elemental-prefix.desktop` |
| Wspólny prefiks | `~/Games/shared-prefix` |

Aplikacja nigdy nie edytuje plików Steama.

## Wiersz poleceń

To samo działa z Konsole:

```bash
EP=~/.local/share/elemental-prefix/elemental-prefix.py
python3 $EP protons            # zainstalowane Protony (* = wybrany)
python3 $EP components         # składniki (* = wybrane)
python3 $EP status             # prefiks, Proton, składniki, trwająca instalacja
python3 $EP apply --proton GE-Proton11-11-x86_64 --components vcrun2022,d3dx9
python3 $EP apply --yes        # zgoda na przebudowę prefiksu
python3 $EP line               # skopiuj linijkę do Opcji uruchamiania
python3 $EP uninstall          # z --delete-prefix usuwa też prefiks
```

## Ograniczenia

- Jeden wspólny prefiks. Gry wymagające sprzecznych ustawień powinny zostać na własnym prefiksie.
- Tylko tryb pulpitu. W trybie gry gry działają normalnie; pulpitu potrzebuje tylko sama aplikacja.
- Opcje uruchamiania ustawia się ręcznie. Aplikacja nie zmienia skrótów Steama.

## Licencja

MIT – zobacz [LICENSE](LICENSE).
