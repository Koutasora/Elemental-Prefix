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

0. **Ekran startowy** (tylko gdy prefiks istnieje) – pokazuje jego Protona i składniki i daje dwa
   wybory: skopiowanie linijki do Opcji uruchamiania albo zmianę Protona lub składników (kroki 1–4).
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
   składniki. Okno postępu pokazuje bieżący krok, a co 30 s czas, który na nim upłynął; pełny zapis
   trafia do `~/.local/share/elemental-prefix/install.log`. Na koniec pojawia się powiadomienie.
   Aplikacja nie startuje, gdy na prefiksie działa gra albo trwa inna instalacja.
4. **Gotowe** – pokazuje linijkę do Opcji uruchamiania (już skopiowaną do schowka) i przypomnienie:
   gry korzystające z prefiksu muszą mieć ten sam Proton w Właściwości → Zgodność (nic do ustawiania,
   gdy to domyślny Proton Steama).

Okienka: stałe rozmiary (`--geometry`), pogrubiony nagłówek i krótki tekst łamany ręcznie po ok. 60
znakach, bo kdialog zamiast zawijać rozciąga okno do najdłuższej linii. Pozycje list mają do ok. 45
znaków. Okno postępu ignoruje `--geometry`, więc jego tekst to blok `<table>` o stałej szerokości
i tej samej liczbie linii w każdym kroku.

Ponowne uruchomienie:

- **Dodanie składników** – instaluje tylko nowo zaznaczone.
- **Usunięcie składników albo zmiana Protona** – winetricks nie umie odinstalowywać, a skakanie
  między wersjami Protona psuje prefiksy. Aplikacja buduje prefiks od nowa, a stary najpierw
  przemianowuje na `shared-prefix.backup-<data>`. Folder użytkownika Windows (`drive_c/users/steamuser`:
  Dokumenty, AppData, Saved Games – tam gry trzymają zapisy) jest kopiowany do nowego prefiksu; składniki
  leżą w `drive_c/windows`, więc przebudowa i tak je usuwa.

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
1. Skrypt bez okienek: wykrywanie Protona, tworzenie prefiksu, instalacja składników. **Gotowe.**
2. Okienka (`kdialog`): lista Protonów, lista składników, postęp, ekran końcowy, schowek. **Gotowe.**
3. Instalator (`curl … install.sh | bash`), pozycja w menu z akcją odinstalowania, README (EN + PL),
   licencja MIT. **Gotowe.**

## Wersja 2 (plan z 2026-10-27)

Wersja 1 pyta, które składniki zainstalować. Wersja 2 rezygnuje z większości tego wyboru: biblioteki
leżące obok siebie nie przeszkadzają grom, które z nich nie korzystają, więc stały bezpieczny zestaw
wystarcza prawie każdej grze. W zamian aplikacja uczy się rozpoznawać, czego gra potrzebuje. Gry
trafiają na Decka jako gotowe foldery (zainstalowane na PC); aplikacja nie instaluje gier.

### Prefiksy

Wszystkie w `~/.local/share/elemental-prefix/` na dysku wewnętrznym (nigdy na karcie SD: wyjęcie karty
zepsułoby wszystkie gry na prefiksie):

| Prefiks | Składniki | Kto wybiera |
|---|---|---|
| `shared-prefix` | bezpieczny zestaw: `vcrun2005`, `vcrun2008`, `vcrun2010`, `vcrun2012`, `vcrun2013`, `vcrun2022`, `d3dx9`, `d3dcompiler_47`, `xact`, `physx`, `corefonts` | stały |
| `shared-prefix-legacy` | bezpieczny zestaw + `quartz` + `dotnet48` | stały |
| `shared-prefix-custom` | dowolne z listy z wersji 1 | użytkownik |

- `quartz` podmienia wbudowane odtwarzanie wideo Protona i może zepsuć filmiki w grach, które
  odtwarzały je dobrze, więc jest tylko w legacy. `dotnet48` jest duży, wolny i najczęściej się
  wywala, więc też tam. Filmiki Bink (`binkw32.dll`) i Smacker gra przynosi ze sobą, nic nie trzeba.
- Tylko jeden custom. Kilka nazwanych zrobiłoby z aplikacji Bottles.
- Kopie z przebudowy: `~/.local/share/elemental-prefix/backups/`.
- Pliki gier nigdy nie trafiają do folderu prefiksu. Gry zainstalowane ręcznie do `Program Files`
  prefiksu giną przy przebudowie; użytkownik instaluje je ponownie.

### Zmiana Protona, przebudowa

- Shared i legacy buduje się raz i potem się ich nie dotyka. Nowszy Proton sam aktualizuje
  istniejący prefiks przy pierwszym starcie gry, więc aplikacja pyta o Protona tylko przy ich
  budowie; Protona, na którym działa gra, ustawia się w Steamie (Właściwości → Zgodność).
- **Reset prefix (advanced)** przebudowuje shared albo legacy tylko, gdy się zepsuje, albo dla
  starszego Protona. Ta sama kopia zapasowa i przenoszenie zapisów co w wersji 1.
- Custom działa jak wersja 1: dodanie składników je instaluje, usunięcie któregokolwiek przebudowuje.
- Przed resetem albo przebudową custom aplikacja wypisuje gry, które używają tego prefiksu.

### Przejście z wersji 1

Jednorazowo: prefiks powstaje w nowym miejscu, `drive_c/users/steamuser` zostaje skopiowany, stary
`~/Games/shared-prefix` zostaje jako kopia. Aplikacja wypisuje gry, których Opcje uruchamiania wciąż
wskazują starą ścieżkę; użytkownik wkleja każdej nową linijkę.

### Linijka w Opcjach uruchamiania

```
STEAM_COMPAT_DATA_PATH=/home/deck/.local/share/elemental-prefix/shared-prefix PROTON_LOG=1 WINEDEBUG=fixme-all %command%
```

- `PROTON_LOG=1` każe Protonowi zapisywać log, który czyta sprawdzanie. Sam zapisuje o wiele za
  dużo (353 MB w 10 minut gry); z `WINEDEBUG=fixme-all` zostają tylko błędy (831 KB).
- Inne narzędzia dopisują się do tej samej linijki: zmienne (np. `PROTON_FSR4_UPGRADE=1`), wrappery
  przed `%command%` (np. `~/lsfg` z Decky LSFG-VK), argumenty gry po nim. Zmienna postawiona za
  wrapperem albo za `%command%` nie działa.
- Kopiowana linijka jest **składana**: aplikacja czyta obecne Opcje uruchamiania gry z
  `shortcuts.vdf` (tylko odczyt), dzieli je na zmienne / wrappery / `%command%` / argumenty, usuwa
  stary wpis Elemental Prefix, swoje zmienne stawia na samym początku, a resztę zostawia w kolejności
  użytkownika. Użytkownik wkleja ją w miejsce całej starej linijki.
- Sprawdzanie ostrzega, gdy `STEAM_COMPAT_DATA_PATH` stoi za wrapperem albo `%command%`, gdy
  `%command%` występuje dwa razy albo gdy linijki brakuje (pewnie nadpisało ją inne narzędzie).
- **Proton w grze:** Proton przy każdym starcie przestawia prefiks na swoją wersję, więc wszystkie
  gry na jednym prefiksie powinny mieć tego samego Protona. Aplikacja czyta narzędzie zgodności
  każdej gry z `config/config.vdf` Steama (`CompatToolMapping`, klucz = `appid` skrótu; tylko
  odczyt) i ostrzega, gdy gra na jednym z jej prefiksów ma innego Protona niż prefiks (np. „Fantasy
  Life runs on Proton Experimental – set GE-Proton11-11”). Pokazywane obok listy gier przy wyborze
  prefiksu i w Set up with Elemental Prefix.

### Set up with Elemental Prefix

Prawy klik na `.exe` gry w Dolphinie (service menu) albo ta sama akcja w pozycji aplikacji w menu.
Działa bez Steama: czyta pliki gry.

1. **Importy** – czyta tablice importów PE plików `.exe` i `.dll` w folderze gry i tłumaczy je na
   składniki (np. `MSVCR120.dll` → `vcrun2013`, `d3dx9_43.dll` → `d3dx9`). Tylko biblioteka
   standardowa Pythona. Rozpoznaje też pliki .NET (nagłówek CLR) i Bink.
2. **Folder gry** – foldery i pliki z bibliotekami do doinstalowania (`_CommonRedist`, `Redist`,
   `DirectX`, `vcredist*.exe`) jako wskazówki; `dxgi.dll`, `d3d11.dll`, `d3d12.dll` obok `.exe`
   (ReShade i podobne mody) → podpowiedź `WINEDLLOVERRIDES="dxgi=n,b"` (albo z pasującym DLL).
3. **Log Protona** – po nieudanym starcie czyta `~/steam-<id>.log`, gdzie `<id>` to
   `(appid << 32) | 0x02000000` z `appid` skrótu w `shortcuts.vdf`, i
   szuka linii `Library … not found` i podobnych. Linie, których nie rozpoznaje, pokazuje jako
   fragment, bez zgadywania.
4. **Rejestr** – ścieżki rejestru zapisane tekstem w `.exe` (`SOFTWARE\…`) i klucze ze spisu w
   `unins000.dat` (Inno Setup) porównuje z rejestrem prefiksu. Brakujące podaje jako „prawdopodobnie
   potrzebne”, z nazwą klucza do wyeksportowania na PC.

Wynik podaje prefiks do użycia (shared, legacy albo custom plus co do niego dodać), pokazuje, którego
prefiksu gra używa teraz (shared / legacy / custom / inny `STEAM_COMPAT_DATA_PATH` / własny
`compatdata/<appid>` / jeszcze nie uruchamiana), kopiuje składaną linijkę, a dla gry, której nie ma
w Steamie, proponuje wbudowane w SteamOS „Add to Steam”. Składniki instaluje tylko do własnych
prefiksów aplikacji, nigdy do własnego prefiksu gry.

### Import rejestru

Prawy klik na plik `.reg` → **Import to Elemental Prefix** → wybór prefiksu → `wine regedit`.
Stare gry pudełkowe czytają klucze instalacji (ścieżka, wersja, klucz CD), które zapisuje tylko ich
instalator; użytkownik eksportuje klucz `regedit` na PC. Sprawdzanie proponuje też import pliku
`.reg` znalezionego w folderze gry.

### Do dokumentacji

- Dwie gry z jednej serii mogą zapisywać do tego samego folderu w `AppData` we wspólnym prefiksie i
  nadpisywać sobie zapisy; jedną z nich przenieść na custom.
- Bez obietnic typu „99 % gier”. Prefiksy naprawiają brakujące biblioteki, nie anty-cheat, DRM ani
  błędy Protona.

### Etapy

4. **Sprawdzenie ręcznie na Decku:** Flatpak Protontricks z `--filesystem` w `~/.local/share`;
   aktualizacja prefiksu zbudowanego poza Steamem przez nowszego Protona; nazwa i miejsce logu z
   `PROTON_LOG=1` dla gry spoza Steama; jak szybko Steam zapisuje Opcje uruchamiania do
   `shortcuts.vdf`; service menu Dolphina na `.exe` i `.reg`; wywołanie „Add to Steam” z SteamOS
   ze skryptu.
5. Trzy prefiksy w nowym miejscu, bezpieczny zestaw, legacy, lista custom, Reset prefix, przejście
   z wersji 1. **Gotowe, sprawdzone na Decku 2026-10-27.**
6. Set up with Elemental Prefix: importy, .NET, Bink, folder gry, wybór prefiksu, doinstalowanie
   brakujących składników do custom. **Gotowe, sprawdzone na Decku 2026-10-27.** `.exe` w folderze
   wspólnym dla wielu gier (dysk, biblioteka Steama, katalog domowy) jest sprawdzany sam, bez
   podfolderów; „not found” pokazuje tylko zwykłe (nie opóźnione) importy `.exe` i DLL obok niego.
   Pozycję w Dolphinie i w menu zapisuje `elemental-prefix.py setup`, uruchamiane przez `install.sh`.
7. Opcje uruchamiania: odczyt `shortcuts.vdf`, składana linijka, ostrzeżenia, listy gier w
   komunikatach resetu i przejścia, ostrzeżenie o Protonie w grze, „Add to Steam”. **Gotowe, sprawdzone
   na Decku 2026-10-27.** Steam zapisuje zmianę Zgodności do `config.vdf` od razu. Ostrzeżenie o
   Protonie porównuje grę z tym, czego używa większość gier na jej prefiksie (remis: z Protonem budowy
   prefiksu; gra sama na prefiksie nie dostaje ostrzeżenia, bo może mieć nowszego Protona). Ostrzeżenie
   „brakuje linijki” wypadło: aplikacja nie wie, czy gra kiedykolwiek ją miała. `steamos-add-to-steam`
   działa bez przechwytywania wyjścia (polecenie `steam` potrafi trzymać je otwarte) i z limitem 30 s.
   Skróty bez pełnej ścieżki (`flatpak` dla Chiaki, Protontricks) są pomijane przy szukaniu gry.
8. Odczyt logu Protona. **Gotowe, sprawdzone na Decku 2026-10-27** (działająca gra: bez fałszywych
   alarmów). .NET rozpoznawany tylko z `.exe`: linie `err:mscoree` są w logach większości gier. Błędy
   widziane w logach działających gier (openxr, certyfikaty crypt, hid, ntoskrnl, steamclient) nie są
   pokazywane.
9. Wskazówki rejestru i import `.reg`. **Gotowe, sprawdzone na Decku 2026-10-27.** Import uruchamia
   `proton run regedit /S Z:\…` Protonem prefiksu; pozycja Dolphina na `.reg` to osobne service menu
   (`elemental-prefix-reg.desktop`). Klucze, które ma każdy system (Microsoft, sterowniki, Steam,
   silniki), nie są podpowiadane.
10. README (EN + PL) i zrzuty ekranu. **Gotowe 2026-10-27.** Menu mają wysokość dopasowaną do tekstu.

Nic nie budujemy, dopóki etap 4 nie przejdzie.

**Wyniki etapu 4 (2026-10-27, zaliczony):**

- Flatpak Protontricks instaluje do prefiksu w `~/.local/share/elemental-prefix` z `--filesystem`
  na prefiks i folder Protona (vcrun2010 w 16 s).
- Prefiks zbudowany Protonem 11.0 poza Steamem GE-Proton11-11 zaktualizował przy pierwszym starcie
  gry (plik `version` `11.0-100` → `GE-Proton11-11`); gra działała.
- Steam zapisuje zmienione Opcje uruchamiania do `shortcuts.vdf` w kilka sekund, bez restartu.
- Log: `~/steam-<id>.log`, `<id>` = `(appid << 32) | 0x02000000`. Prefiks testowy z samym
  vcrun2010 dał `err:module:import_dll Library mfc140u.dll (which is needed by …) not found` –
  właśnie takie linie czyta sprawdzanie logu.
- Service menu w `~/.local/share/kio/servicemenus/` (plik wykonywalny) pokazuje się na `.exe`
  (`application/x-msdownload`) i `.reg` (`text/x-ms-regedit`).
- „Add to Steam” to `/usr/bin/steamos-add-to-steam [-ui] <ścieżka>` (otwiera
  `steam://addnonsteamgame/…`); jeszcze nie uruchamiane, próba w etapie 7.

### Do zbadania kiedyś

- protonfixes z bazy umu: GE-Proton może stosować poprawki dla gry spoza Steama, gdy dostanie
  `UMU_ID`. Niesprawdzone.

## Poza planem

- Automatyczna edycja skrótów albo Opcji uruchamiania w Steamie (zapis `shortcuts.vdf`).
- Instalowanie gier z instalatorów i archiwów; gry kopiuje się jako foldery.
- Logowanie dostępu do rejestru (`WINEDEBUG=+reg`).
- Kilka prefiksów custom.
- Interfejs w trybie gry (panel Decky).
- Spatchowane wersje Protona do obchodzenia zabezpieczeń.
