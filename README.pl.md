# Elemental Prefix

[English](README.md) | **Polski**

Wspólne prefiksy Protona z Visual C++, DirectX 9 i innymi popularnymi bibliotekami dla gier
i programów spoza Steama na **Steam Decku** (SteamOS, tryb pulpitu) oraz sprawdzanie, czego gra
potrzebuje.

Stare gry z Windowsa dodane do Steama jako gry spoza Steama często się nie uruchamiają, bo świeży
prefiks Protona nie ma tych bibliotek. Zamiast instalować je przez Protontricks w każdej grze
osobno, Elemental Prefix raz przygotowuje prefiks. Każda gra spoza Steama korzysta z niego dzięki
jednej linijce w Opcjach uruchamiania:

```
STEAM_COMPAT_DATA_PATH=/home/deck/.local/share/elemental-prefix/shared-prefix PROTON_LOG=1 WINEDEBUG=fixme-all %command%
```

<table>
  <tr>
    <td><img src="docs/screenshots/menu.png" width="380" alt="Wybór prefiksu"></td>
    <td><img src="docs/screenshots/check.png" width="380" alt="Set up with Elemental Prefix"></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/progress.png" width="380" alt="Budowa prefiksu"></td>
    <td><img src="docs/screenshots/line.png" width="380" alt="Linijka do Opcji uruchamiania"></td>
  </tr>
</table>

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

## Prefiksy

| Prefiks | Składniki | Dla |
|---|---|---|
| **Shared** | Visual C++ 2005–2022, DirectX 9, kompilator shaderów, XAudio / XACT, PhysX, czcionki Windows | większości gier |
| **Legacy** | Shared + odtwarzanie filmów (`quartz`) + .NET Framework 4.8 | starych gier z czarnymi filmikami, gier .NET |
| **Custom** | te, które zaznaczysz | gier potrzebujących czegoś innego |

Biblioteki, których gra nie używa, nie przeszkadzają jej, więc jeden stały zestaw wystarcza
większości gier. Legacy jest osobno, bo jego odtwarzanie filmów może zepsuć filmiki w grach, które
odtwarzały je dobrze, a .NET 4.8 jest duży i instaluje się około 10 minut. Każdy prefiks powstaje
przy pierwszym wyborze.

## Użycie

1. Otwórz **Elemental Prefix** z menu aplikacji i wybierz prefiks. Za pierwszym razem aplikacja
   pyta o Protona (domyślny Proton Steama jest zaznaczony) i buduje prefiks; to trwa kilka minut.
2. Linijka do Opcji uruchamiania trafia do schowka. W Steamie otwórz grę:
   **Właściwości → Ogólne → Opcje uruchamiania** i wklej ją.
3. W **Właściwości → Zgodność** ustaw tego samego Protona co w pozostałych grach na tym prefiksie
   (przy domyślnym Protonie Steama nic nie trzeba ustawiać).

### Set up with Elemental Prefix

W Dolphinie kliknij prawym przyciskiem `.exe` gry i wybierz **Set up with Elemental Prefix** (albo
kliknij prawym Elemental Prefix w menu aplikacji). Sprawdzanie tylko czyta pliki:

- biblioteki, których używają programy gry, i czy gra ma je przy sobie;
- programy .NET, filmy Bink, stare pliki wideo, instalatory w folderze gry;
- `dxgi.dll`, `d3d11.dll` i podobne obok `.exe` (ReShade i inne mody): linijka dostaje potrzebne
  im `WINEDLLOVERRIDES`;
- log Protona z ostatniego uruchomienia (dzięki `PROTON_LOG=1` w linijce): biblioteki, których nie
  znaleziono;
- klucze rejestru, które gra prawdopodobnie czyta, a których brakuje w prefiksie;
- którego prefiksu gra używa teraz i czy ma innego Protona niż pozostałe gry na nim.

Potem zaleca prefiks i kopiuje linijkę. Jeśli gra ma już Opcje uruchamiania (inne zmienne,
`~/lsfg`, argumenty gry), linijka jest z nimi składana: wklej ją w miejsce całej starej linijki.
Grę, której nie ma jeszcze w Steamie, można dodać z tego samego okna.

### Rejestr

Niektóre stare gry pudełkowe czytają z rejestru ścieżkę instalacji albo klucz CD, a zapisuje je
tam tylko ich instalator. Wyeksportuj klucz programem `regedit` na PC (**Plik → Eksportuj**),
skopiuj plik `.reg` na Decka, kliknij go prawym w Dolphinie i wybierz **Import to Elemental Prefix**.

### Zmiana Protona, Reset prefix

- Shared i legacy buduje się raz. Nowszy Proton sam je aktualizuje przy następnym starcie gry,
  więc wystarczy ustawić nowszego Protona w Zgodności gier.
- **Reset prefix** (w menu) przebudowuje shared albo legacy, gdy prefiks się zepsuje albo trzeba
  wrócić do starszego Protona.
- W custom dodanie składników je instaluje; usunięcie któregoś albo zmiana Protona przebudowuje
  prefiks.

Przebudowa przenosi stary prefiks do `~/.local/share/elemental-prefix/backups/` i kopiuje do nowego
zapisy i ustawienia gier (folder użytkownika Windows). Przed startem aplikacja pokazuje listę gier,
które używają prefiksu.

## Warto wiedzieć

- **Wszystkie gry na jednym prefiksie powinny mieć tego samego Protona.** Każde uruchomienie
  przestawia prefiks na Protona, który go uruchamia. Sprawdzanie i okno prefiksu ostrzegają, gdy
  gra ma innego.
- **Pierwsze uruchomienie w nowym prefiksie może przez kilka minut pokazywać czarny ekran** (gry na
  Unreal Engine 5 budują shadery). Daj grze czas, zanim ją zamkniesz.
- **Gry z jednej serii mogą mieć wspólny folder zapisów.** Na jednym prefiksie mogą nadpisywać
  sobie zapisy; przenieś jedną z nich do custom.
- **Zapisy z własnego prefiksu Steama gry nie są przenoszone.** Zostają w
  `~/.local/share/Steam/steamapps/compatdata/<numer>`; skopiuj je do prefiksu ręcznie.
- Trzymaj każdą grę we własnym folderze. `.exe` leżący obok innych gier jest sprawdzany sam.
- Prefiksy uzupełniają brakujące biblioteki. Nie naprawiają zabezpieczeń przed oszustwami,
  zabezpieczeń przed kopiowaniem ani błędów Protona.
- Elemental Prefix jest przeznaczony do gier, które masz legalnie (GOG, inne sklepy, stare płyty).
  Zgłoszenia dotyczące pirackich kopii są zamykane.

## Przejście z wersji 1

Pierwsze uruchomienie wersji 2 proponuje przeniesienie: wspólny prefiks powstaje w nowym miejscu
z bezpiecznym zestawem, zapisy gier są kopiowane z `~/Games/shared-prefix`, a aplikacja pokazuje
listę gier, które mają jeszcze starą linijkę. Wklej im nową. Stary folder zostaje jako kopia; usuń
go, gdy gry działają.

## Odinstalowanie

Kliknij prawym przyciskiem **Elemental Prefix** w menu aplikacji i wybierz
**Uninstall Elemental Prefix**. Aplikacja zapyta, czy usunąć też prefiksy; domyślnie zostają.

## Pliki

| Co | Gdzie |
|---|---|
| Program, log instalacji, prefiksy, kopie | `~/.local/share/elemental-prefix/` |
| Ustawienia | `~/.config/elemental-prefix.conf` |
| Pozycja w menu | `~/.local/share/applications/elemental-prefix.desktop` |
| Pozycje w Dolphinie | `~/.local/share/kio/servicemenus/elemental-prefix*.desktop` |
| Logi Protona | `~/steam-<numer>.log` |

Aplikacja tylko czyta pliki Steama; nigdy ich nie zmienia.

## Wiersz poleceń

```bash
EP=~/.local/share/elemental-prefix/elemental-prefix.py
python3 $EP status                       # prefiksy, ich gry, ostrzeżenia o Protonie
python3 $EP apply shared                 # zbuduj shared (także legacy, custom)
python3 $EP apply custom --components vcrun2022,d3dx9 --yes
python3 $EP reset legacy --proton GE-Proton11-11-x86_64 --yes
python3 $EP check "/ścieżka/do/Gra.exe"  # czego gra potrzebuje, ze składaną linijką
python3 $EP import-reg gra.reg --prefix shared
python3 $EP line shared                  # skopiuj linijkę do Opcji uruchamiania
python3 $EP protons                      # zainstalowane Protony
python3 $EP uninstall                    # z --delete-prefixes usuwa też prefiksy
```

## Licencja

MIT – zobacz [LICENSE](LICENSE).
