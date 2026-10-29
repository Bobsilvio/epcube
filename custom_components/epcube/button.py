"""Pulsante per rileggere subito firmware, avvisi, blackout e meteo.

Questi dati vengono letti ogni 15 minuti (SLOW_EXTRAS_INTERVAL): il pulsante
scarta la cache e li rilegge al prossimo aggiornamento, che viene forzato.
"""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import bind_entities_to_entry


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeCheckUpdatesButton(coordinator, entry)]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities)


class EpCubeCheckUpdatesButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "check_updates"
    _attr_icon = "mdi:cloud-refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = "epcube_check_updates"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    async def async_press(self):
        state = self.hass.data[DOMAIN][self.entry.entry_id]["state"]
        state.extras_at = 0.0
        await self.coordinator.async_refresh()
