# app.py – Obowiązkowe wyposażenie auta w krajach Europy
# Wersja 2.0: wybór kraju z podpowiedziami + kafelki z ikonami + lista pod spodem.
# Nasze teksty są oznaczone translate="no", żeby tłumacz przeglądarki ich nie psuł.

import base64
import html
import io
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# 1. USTAWIENIA
# ---------------------------------------------------------------------------

# Plik z danymi leży w tym samym folderze co app.py.
PLIK_DANYCH = Path(__file__).parent / "wyposazenie.csv"

# Jedyne wartości, jakie mogą stać w komórkach z wyposażeniem.
DOZWOLONE_WARTOSCI = {"", "+", "++", "zalecane", "zalecana"}

# Polski alfabet – potrzebny, żeby "Łotwa" stała po "Litwie", a nie na końcu listy.
POLSKI_ALFABET = "aąbcćdeęfghijklłmnńoóprsśtuvwxyzźż"

# Folder z ikonami i przypisanie: nazwa kolumny w CSV → plik ikony.
FOLDER_IKON = Path(__file__).parent / "ikony"
IKONY = {
    "Opony zimowe": "opony-zimowe.svg",
    "Apteczka": "apteczka.svg",
    "Kamizelka odblaskowa": "kamizelka-odblaskowa.svg",
    "Trójkąt ostrzegawczy": "trojkat-ostrzegawczy.svg",
    "Gaśnica": "gasnica.svg",
    "Koło zapasowe (klucz + podnośnik)": "kolo-zapasowe.svg",
    "Zapasowe żarówki i bezpieczniki": "zapasowe-zarowki-bezpieczniki.svg",
    "Kliny pod koła": "kliny-pod-kola.svg",
    "Zabezpieczenie antywłamaniowe": "zabezpieczenie-antywlamaniowe.svg",
    "Lina holownicza": "lina-holownicza.svg",
    "Dodatkowe okulary korekcyjne": "okulary-korekcyjne.svg",
    "Rękawice gumowe": "rekawice-gumowe.svg",
}

# Kolory kafelków (wariant B): (tło kółka, kolor ikony, obwódka kółka).
KOLORY_OBOWIAZKOWE = ("#dc2626", "#ffffff", "#dc2626")  # czerwone kółko, biała ikona
KOLORY_ZALECANE = ("#facc15", "#1f2937", "#ca8a04")     # żółte kółko, ciemna ikona


# ---------------------------------------------------------------------------
# 2. FUNKCJE POMOCNICZE
# ---------------------------------------------------------------------------

def klucz_polski(tekst):
    """Zamienia napis na listę numerów liter wg polskiego alfabetu (do sortowania)."""
    return [POLSKI_ALFABET.find(litera) for litera in tekst.lower()]


def wczytaj_dane(sciezka):
    """Wczytuje plik CSV i zwraca tabelę (DataFrame)."""
    # Kodowanie znaków: najpierw UTF-8, a jeśli się nie da – starszy format z Excela.
    try:
        tekst = sciezka.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        tekst = sciezka.read_text(encoding="cp1250")

    # Separator: polski Excel zapisuje średnik (;), inne programy często przecinek (,).
    naglowek = tekst.splitlines()[0]
    separator = ";" if naglowek.count(";") >= naglowek.count(",") else ","

    dane = pd.read_csv(io.StringIO(tekst), sep=separator, dtype=str, keep_default_na=False)

    # Usuwamy przypadkowe spacje z nagłówków i z komórek.
    dane.columns = [kolumna.strip() for kolumna in dane.columns]
    dane = dane.map(str.strip)
    return dane


def kolumny_wyposazenia(dane):
    """Wszystkie kolumny poza 'Kraj' i 'Uwagi' to rodzaje wyposażenia."""
    return [kolumna for kolumna in dane.columns if kolumna not in ("Kraj", "Uwagi")]


def sprawdz_dane(dane):
    """Szuka błędów w pliku. Zwraca listę opisów błędów (pusta lista = wszystko OK)."""
    if "Kraj" not in dane.columns:
        return ["Brak kolumny „Kraj” w pierwszym wierszu pliku."]

    bledy = []
    for numer, wiersz in dane.iterrows():
        kraj = wiersz["Kraj"]
        if kraj == "":
            bledy.append(f"Wiersz {numer + 2}: brak nazwy kraju.")
        for kolumna in kolumny_wyposazenia(dane):
            wartosc = wiersz[kolumna]
            if wartosc.lower() not in DOZWOLONE_WARTOSCI:
                bledy.append(
                    f"{kraj} → {kolumna}: „{wartosc}” "
                    "(dozwolone: +, ++, zalecane lub puste pole)"
                )

    for kraj in dane.loc[dane["Kraj"].duplicated(), "Kraj"]:
        bledy.append(f"Kraj „{kraj}” występuje w pliku więcej niż raz.")
    return bledy


def wyposazenie_dla(wiersz, kolumny):
    """Dzieli wyposażenie jednego kraju na dwie listy: obowiązkowe i zalecane.

    Każdy element to para (nazwa sprzętu, napis do wyświetlenia),
    np. ("Trójkąt ostrzegawczy", "Trójkąt ostrzegawczy (2 szt.)").
    Nazwa jest potrzebna do znalezienia ikony, a napis – do pokazania na ekranie.
    """
    obowiazkowe = []
    zalecane = []
    for sprzet in kolumny:
        wartosc = wiersz[sprzet].lower()
        if wartosc == "+":
            obowiazkowe.append((sprzet, sprzet))
        elif wartosc == "++":
            obowiazkowe.append((sprzet, f"{sprzet} (2\u00a0szt.)"))  # \u00a0 = spacja nierozdzielająca
        elif wartosc in ("zalecane", "zalecana"):
            zalecane.append((sprzet, sprzet))
    return obowiazkowe, zalecane


def ikona_base64(sprzet, kolor):
    """Wczytuje ikonę SVG, koloruje ją i zamienia na tekst, który można wkleić do HTML.

    Zwraca None, jeśli dla tego sprzętu nie ma ikony (np. nowa kolumna w CSV).
    """
    if sprzet not in IKONY:
        return None
    plik = FOLDER_IKON / IKONY[sprzet]
    if not plik.exists():
        return None
    svg = plik.read_text(encoding="utf-8").replace("currentColor", kolor)
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def kafelek(sprzet, napis, kolory):
    """Buduje jeden kafelek: kolorowe kółko z ikoną, a pod nim nazwa."""
    tlo, kolor_ikony, obwodka = kolory
    kod = ikona_base64(sprzet, kolor_ikony)
    if kod:
        srodek = (
            f'<img src="data:image/svg+xml;base64,{kod}" width="40" height="40" alt="" '
            'style="display: block; margin: 0;">'
        )
    else:
        # Brak ikony: w kółku pokazujemy pierwszą literę nazwy.
        srodek = (
            f'<span style="font-size: 1.6rem; font-weight: bold; color: {kolor_ikony};">'
            f"{html.escape(sprzet[:1])}</span>"
        )
    return (
        '<div style="border: 1px solid rgba(128, 128, 128, 0.35); border-radius: 10px; '
        'padding: 12px 6px; text-align: center; font-size: 0.85rem; line-height: 1.25;">'
        f'<div style="width: 60px; height: 60px; border-radius: 50%; background: {tlo}; '
        f"box-shadow: 0 0 0 2px {obwodka}; margin: 0 auto 8px; display: flex; "
        f'align-items: center; justify-content: center;">{srodek}</div>'
        f"<div>{html.escape(napis)}</div></div>"
    )


def siatka(elementy, kolory, tekst_gdy_pusto):
    """Układa kafelki w siatkę, która sama dopasowuje liczbę kolumn do szerokości ekranu."""
    if not elementy:
        return f"<p>{html.escape(tekst_gdy_pusto)}</p>"
    kafelki = "".join(kafelek(sprzet, napis, kolory) for sprzet, napis in elementy)
    return (
        '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); '
        f'gap: 10px; margin-bottom: 1rem;">{kafelki}</div>'
    )


def pokaz_html(tresc):
    """Wyświetla fragment HTML oznaczony jako „nie tłumacz” (translate="no")."""
    st.markdown(f'<div translate="no">{tresc}</div>', unsafe_allow_html=True)


def lista_html(elementy, tekst_gdy_pusto):
    """Buduje listę punktowaną w HTML albo zdanie, że lista jest pusta."""
    if not elementy:
        return f"<p>{html.escape(tekst_gdy_pusto)}</p>"
    punkty = "".join(f"<li>{html.escape(element)}</li>" for element in elementy)
    return f"<ul>{punkty}</ul>"


def ramka(tresc, kolor):
    """Kolorowa ramka z tekstem (np. żółta na uwagi, niebieska na podpowiedzi)."""
    return (
        f'<div style="border-left: 4px solid {kolor}; background: {kolor}22; '
        f'padding: 0.75rem 1rem; border-radius: 0.5rem; margin: 0.5rem 0 1rem;">'
        f"{tresc}</div>"
    )


def maly_tekst(tresc):
    """Mały, szary tekst – jak podpis pod polem."""
    return f'<p style="font-size: 0.875rem; opacity: 0.6;">{tresc}</p>'


# ---------------------------------------------------------------------------
# 3. WYGLĄD APLIKACJI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Wyposażenie auta w Europie", page_icon="🚗")
pokaz_html("<h1>🚗 Obowiązkowe wyposażenie auta w Europie</h1>")

# --- Wczytanie i sprawdzenie danych ---
if not PLIK_DANYCH.exists():
    st.error(f"Nie znaleziono pliku z danymi: {PLIK_DANYCH.name}")
    st.stop()

dane = wczytaj_dane(PLIK_DANYCH)
bledy = sprawdz_dane(dane)
if bledy:
    st.error("W pliku z danymi są błędy:\n\n" + "\n".join(f"- {b}" for b in bledy))
    st.stop()

# --- Wybór kraju (pole z podpowiedziami) ---
kraje = sorted(dane["Kraj"], key=klucz_polski)
kraj = st.selectbox(
    "Wybierz kraj",
    kraje,
    index=None,
    placeholder="Zacznij wpisywać nazwę kraju, np. Niemcy",
)
pokaz_html(maly_tekst("Nie ma kraju na liście? Na razie nie mamy dla niego danych."))

if kraj is None:
    pokaz_html(ramka("Wybierz kraj, aby zobaczyć wymagane wyposażenie.", "#1c83e1"))
    st.stop()

# --- Wyniki dla wybranego kraju ---
wiersz = dane[dane["Kraj"] == kraj].iloc[0]
obowiazkowe, zalecane = wyposazenie_dla(wiersz, kolumny_wyposazenia(dane))

uwagi = wiersz.get("Uwagi", "")

# Same napisy (bez nazw do ikon) – do zwykłej listy.
napisy_obowiazkowe = [napis for sprzet, napis in obowiazkowe]
napisy_zalecane = [napis for sprzet, napis in zalecane]

# Cały wynik budujemy jako jeden blok HTML, wyświetlany za jednym razem.
wynik = f"<h2>{html.escape(kraj)}</h2>"

# Część 1: kafelki z ikonami
wynik += "<h3>✅ Obowiązkowe</h3>"
wynik += siatka(obowiazkowe, KOLORY_OBOWIAZKOWE, "Brak obowiązkowego wyposażenia w naszych danych.")
wynik += "<h3>💡 Zalecane</h3>"
wynik += siatka(zalecane, KOLORY_ZALECANE, "Brak zaleceń.")
if uwagi:
    wynik += ramka(f"<b>Uwaga:</b> {html.escape(uwagi)}", "#f0a020")

# Część 2: zwykła lista pod kafelkami
wynik += "<h3>📋 Lista</h3>"
wynik += "<p><b>Obowiązkowe:</b></p>"
wynik += lista_html(napisy_obowiazkowe, "Brak.")
wynik += "<p><b>Zalecane:</b></p>"
wynik += lista_html(napisy_zalecane, "Brak.")
pokaz_html(wynik)

st.divider()
pokaz_html(maly_tekst("Informacje orientacyjne. Przed wyjazdem sprawdź aktualne przepisy kraju docelowego."))
