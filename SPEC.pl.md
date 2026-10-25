# Elemental Prefix – specyfikacja

[English](SPEC.md) | **Polski**

## Cel

Stare gry i programy z Windowsa dodane do Steama jako gry spoza Steama często się nie
uruchamiają, bo świeży prefiks Protona nie ma bibliotek Visual C++, DirectX 9 i podobnych.
Dziś trzeba je instalować przez Protontricks dla każdej gry osobno.

Elemental Prefix raz przygotowuje **jeden wspólny prefiks** z wybranymi bibliotekami. Każda gra
spoza Steama korzysta z niego dzięki jednej linijce w Opcjach uruchamiania:

```
STEAM_COMPAT_DATA_PATH=/home/deck/Games/shared-prefix %command%
```

## Decyzje

- Jeden wspólny prefiks: `~/Games/shared-prefix`.
- Aplikacja w trybie pulpitu z prostymi okienkami KDE (`kdialog`, jest już na Decku). Nic dodatkowego do instalowania.
- Wszystko w katalogu domowym, bez `sudo`.
- Angielskie nazwy i interfejs. Dokumentacja po angielsku i po polsku.
- Linijka do Opcji uruchamiania trafia tylko do schowka. Aplikacja nigdy nie edytuje plików Steama.
- Biblioteki instaluje winetricks z Flatpaka Protontricks (większość użytkowników Decka go ma).
  Bez Protontricks aplikacja mówi, jak go zainstalować z Discover. Flatpak nie widzi `~/Games`
  ani karty SD, więc każde wywołanie dostaje `--filesystem=` dla prefiksu i folderu wybranego
  Protona (bez trwałej zmiany uprawnień).
- Schowek przez Klippera: `qdbus6` (albo `qdbus`) `org.kde.klipper /klipper setClipboardContents`.
  Pulpit działa na Waylandzie i nie ma `wl-copy` ani `xclip`.

## Przebieg

1. **Proton** – lista zainstalowanych wersji: Protony Steama (`steamapps/common/Proton*`,
   we wszystkich bibliotekach Steama, także na karcie SD) i własne (`compatibilitytools.d`, np. GE-Proton).
   Domyślnie zaznaczony: Proton istniejącego prefiksu, a bez prefiksu domyślne narzędzie zgodności
   Steama (wpis `0` w `CompatToolMapping` w `config/config.vdf`). Przy domyślnym Protonie Steama gra
   nie wymaga ustawień w Zgodności, wystarczy linijka w Opcjach uruchamiania.
   Własne narzędzia są pokazywane pod `display_name` z `compatibilitytool.vdf`, a nie nazwą folderu
   (paczki GE-Protona mają teraz końcówkę `-x86_64`).
2. **Składniki** – lista do zaznaczenia. Domyślnie zaznaczone oznaczone ✓:

   | Składnik | polecenie winetricks | Domyślnie |
   |---|---|---|
   | Visual C++ 2015–2022 | `vcrun2022` | ✓ |
   | Visual C++ 2013 | `vcrun2013` | |
   | Visual C++ 2012 | `vcrun2012` | |
   | Visual C++ 2010 | `vcrun2010` | ✓ |
   | Visual C++ 2008 | `vcrun2008` | ✓ |
   | Visual C++ 2005 | `vcrun2005` | |
   | DirectX 9 (d3dx9) | `d3dx9` | ✓ |
   | Dźwięk XAudio / XACT | `xact` | ✓ |
   | Kompilator shaderów dla gier DX11 | `d3dcompiler_47` | |
   | Czcionki Windows | `corefonts` | ✓ |
   | .NET Framework 4.8 (duży, wolny) | `dotnet48` | |
   | PhysX | `physx` | |
   | Filmy w starych grach | `quartz` | |

   Wszystkie polecenia istnieją w winetricks 20260125 z Protontricks 1.15.0 (sprawdzone na etapie 0).
3. **Instalacja** – tworzy prefiks wybranym Protonem (`proton run wineboot`), potem instaluje
   składniki. Okno postępu pokazuje bieżący krok; pełny zapis trafia do
   `~/.local/share/elemental-prefix/install.log`.
4. **Gotowe** – pokazuje linijkę do Opcji uruchamiania (już skopiowaną do schowka) i przypomnienie:
   gry korzystające z prefiksu muszą mieć ten sam Proton w Właściwości → Zgodność (nic do ustawiania,
   gdy to domyślny Proton Steama).

Ponowne uruchomienie:

- **Dodanie składników** – instaluje tylko nowo zaznaczone.
- **Usunięcie składników albo zmiana Protona** – winetricks nie umie odinstalowywać, a skakanie
  między wersjami Protona psuje prefiksy. Aplikacja buduje prefiks od nowa, a stary najpierw
  przemianowuje na `shared-prefix.backup-<data>` (zapisy gier trzymane w prefiksie zostają w nim).

## Pliki

- Program: `~/.local/share/elemental-prefix/`
- Ustawienia (wybrany Proton, składniki): `~/.config/elemental-prefix.conf`
- Pozycja w menu: `~/.local/share/applications/elemental-prefix.desktop` („Elemental Prefix”)
- Prefiks: `~/Games/shared-prefix`

## Etapy

0. **Sprawdzenie ręcznie na Decku** (polecenia wysyłane DeckKeys): utworzenie prefiksu Protonem poza
   Steamem, uruchomienie na nim winetricks z Flatpaka Protontricks, start gry spoza Steama z linijką
   w Opcjach uruchamiania. Nic nie budujemy, dopóki to nie działa.
   **Zaliczony 2026-10-25** (SteamOS 3.9.5): prefiks z Protona 11.0 i GE-Proton11-11 przez
   `proton run wineboot -u`, `vcrun2010` z Flatpaka, gra spoza Steama (Atelier Yumia) działała na wspólnym
   prefiksie z GE-Proton11-11 w SteamLinuxRuntime_4, schowek przez Klippera.
1. Skrypt bez okienek: wykrywanie Protona, tworzenie prefiksu, instalacja składników.
2. Okienka (`kdialog`): lista Protonów, lista składników, postęp, ekran końcowy, schowek.
3. Instalator, pozycja w menu, odinstalowanie, README (EN + PL).

## Poza planem

- Automatyczna edycja skrótów albo Opcji uruchamiania w Steamie.
- Kilka prefiksów.
- Interfejs w trybie gry (panel Decky).
