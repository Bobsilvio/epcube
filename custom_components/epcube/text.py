"""Orari delle fasce della Tariffazione modificabili da Home Assistant.

Una casella per tipo di fascia con i soli orari, "08:00-13:00, 20:00-23:00";
il prezzo è nel number "Prezzo ...". Salvare non cambia modalità: la
Tariffazione si attiva dal menu "Modalità".
"""

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import bind_entities_to_entry, tou_slots_supported
from .tou import (
    TOU_BANDS, TOU_TEXT_PATTERN, async_save_band, band_slots, pending_prices,
    text_to_tou_list, tou_list_price, tou_list_to_text,
)

ICONS = {"peak": "mdi:cash-plus", "midpeak": "mdi:cash", "offpeak": "mdi:cash-minus"}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeTouText(coordinator, entry, band) for band in TOU_BANDS]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities, True)


class EpCubeTouText(CoordinatorEntity, TextEntity):
    """Orari di un tipo di fascia (costo alto / normale / basso) nei giorni feriali."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 255
    # Home Assistant rifiuta già dal frontend un testo che non rispetta il formato
    _attr_pattern = TOU_TEXT_PATTERN

    def __init__(self, coordinator, entry, band):
        super().__init__(coordinator)
        self.entry = entry
        self._band = band
        self._attr_translation_key = f"tou_{band}_times"
        self._attr_icon = ICONS[band]
        self._attr_unique_id = f"epcube_tou_{band}_times_text"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def available(self):
        # Con i piani TOU stagionali l'app non usa le fasce: come lei, niente
        return super().available and tou_slots_supported(self.coordinator, self.entry)

    @property
    def native_value(self):
        return tou_list_to_text(band_slots(self.coordinator, self._band))

    async def async_set_value(self, value: str):
        # Le nuove fasce tengono il prezzo attuale del tipo, o quello scelto
        # prima che ci fossero orari
        price = tou_list_price(band_slots(self.coordinator, self._band))
        if price is None:
            price = pending_prices(self.hass, self.entry).get(self._band)
        slots = text_to_tou_list(self.name or self._band, value, price)
        await async_save_band(self.hass, self.entry, self.coordinator, self._band, slots)
