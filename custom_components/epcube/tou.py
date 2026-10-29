"""Fasce orarie della Tariffazione (TOU): formato dell'API e testo per l'utente.

L'API vuole liste di "HH:MM_HH:MM_prezzo". In Home Assistant gli orari si
scrivono come testo, "08:00-13:00, 20:00-23:00", e il prezzo a parte: tutte le
fasce di un tipo hanno lo stesso prezzo. Qui vengono convertiti e controllati
come fa l'editor dell'app.
"""

import re

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import async_post_switch_mode
from .const import DOMAIN
from .payload import build_switch_mode_payload

# L'editor TOU dell'app accetta fino a 3 fasce per tipo
MAX_TOU_SLOTS = 3

_TOU_ENTRY = re.compile(r"^(\d{1,2}):(\d{2})_(\d{1,2}):(\d{2})(?:_(.*))?$")


def normalize_tou_list(name, entries):
    """Fasce "HH:MM_HH:MM_prezzo" nel formato dell'app.

    Come l'app: orari a due cifre, prezzo col punto decimale e senza punto
    finale ("0,30" -> "0.30", "1." -> "1"), prezzo vuoto ammesso.
    """
    entries = list(entries or [])
    if len(entries) > MAX_TOU_SLOTS:
        raise ServiceValidationError(
            f"{name}: al massimo {MAX_TOU_SLOTS} fasce, come nell'app EP Cube"
        )
    normalized = []
    for entry in entries:
        match = _TOU_ENTRY.match(str(entry).strip())
        if not match:
            raise ServiceValidationError(
                f"Fascia TOU non valida in {name}: '{entry}'. "
                "Formato richiesto: 'HH:MM_HH:MM_prezzo' (es. '08:00_12:00_0.31')"
            )
        h1, m1, h2, m2, price = match.groups()
        if int(h1) > 24 or int(h2) > 24 or int(m1) > 59 or int(m2) > 59:
            raise ServiceValidationError(f"Orario non valido in {name}: '{entry}'")
        price = (price or "").strip().replace(",", ".").rstrip(".")
        if price:
            try:
                float(price)
            except ValueError as err:
                raise ServiceValidationError(
                    f"Prezzo non valido in {name}: '{entry}'"
                ) from err
        normalized.append(f"{int(h1):02d}:{m1}_{int(h2):02d}:{m2}_{price}")
    return normalized


# Formato delle caselle di testo, controllato già dal frontend di Home
# Assistant: fino a MAX_TOU_SLOTS fasce "HH:MM-HH:MM" separate da virgola
_WINDOW = r"\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*"
TOU_TEXT_PATTERN = rf"^(|{_WINDOW}(,{_WINDOW}){{0,{MAX_TOU_SLOTS - 1}}})$"


def _real_slots(entries):
    """(inizio, fine, prezzo) delle fasce vere; "00:00_00:00" è un segnaposto vuoto."""
    for entry in entries or []:
        fields = str(entry).split("_")
        if len(fields) < 2 or not fields[0] or not fields[1]:
            continue
        if fields[0] == fields[1] == "00:00":
            continue
        yield fields[0], fields[1], fields[2] if len(fields) > 2 else ""


def tou_list_to_text(entries):
    """["08:00_13:00_0.31", "20:00_23:00_0.31"] -> "08:00-13:00, 20:00-23:00"."""
    return ", ".join(f"{start}-{end}" for start, end, _ in _real_slots(entries))


def tou_list_price(entries):
    """Prezzo delle fasce (quello della prima), None se non c'è."""
    for _, _, price in _real_slots(entries):
        try:
            return float(price.replace(",", "."))
        except ValueError:
            return None
    return None


def format_price(price):
    return "" if price is None else f"{price:g}"


def text_to_tou_list(name, text, price=None):
    """Orari scritti dall'utente + prezzo -> lista per l'API. Testo vuoto = nessuna fascia."""
    entries = []
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = re.fullmatch(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", chunk)
        if not match:
            raise ServiceValidationError(
                f"{name}: non capisco '{chunk}'. Scrivi gli orari così: 08:00-13:00, 20:00-23:00"
            )
        start, end = match.groups()
        if start == end:
            raise ServiceValidationError(f"{name}: la fascia {start}-{end} dura zero minuti")
        entries.append(f"{start}_{end}_{format_price(price)}")
    return normalize_tou_list(name, entries)


def with_price(name, entries, price):
    """Le stesse fasce con un nuovo prezzo."""
    return normalize_tou_list(
        name, [f"{start}_{end}_{format_price(price)}" for start, end, _ in _real_slots(entries)]
    )


# Tipi di fascia modificabili da Home Assistant (giorni feriali) -> lista di switchMode
TOU_BANDS = {
    "peak": "peakTimeList",
    "midpeak": "midPeakTimeList",
    "offpeak": "offPeakTimeList",
}


def band_slots(coordinator, band):
    data = (coordinator.data or {}).get("data") or {}
    return data.get(TOU_BANDS[band].lower()) or []


def pending_prices(hass, entry):
    """Prezzi scelti per tipi di fascia ancora senza orari: si applicano col primo orario."""
    return hass.data[DOMAIN][entry.entry_id].setdefault("tou_prices", {})


async def async_save_band(hass, entry, coordinator, band, slots):
    """Salva le fasce di un tipo senza cambiare modalità (onlySave=1)."""
    field = TOU_BANDS[band]
    payload = build_switch_mode_payload(
        coordinator.data.get("data", {}),
        only_save="1",
        current=coordinator.data.get("switch_mode"),
        **{field: slots},
    )
    if not await async_post_switch_mode(hass, entry, payload, f"{field}={slots}"):
        raise HomeAssistantError("Il server EP Cube ha rifiutato le fasce orarie (vedi log)")
    await coordinator.async_request_refresh()
