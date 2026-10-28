"""Entità update: segnala quando c'è un firmware più recente per l'EP Cube.

La versione installata arriva da queryFirmwareInfo (firmwareVersion), quella
disponibile da checkUpgrade (newSoftWareVersion), entrambe già lette negli extras.
L'aggiornamento vero si avvia dall'app EP Cube (o lo spinge l'installatore), quindi
l'entità è di sola segnalazione: niente pulsante installa, solo "disponibile".
"""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import bind_entities_to_entry


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeFirmwareUpdate(coordinator)]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities, True)


class EpCubeFirmwareUpdate(CoordinatorEntity, UpdateEntity):
    """Firmware del gateway EP Cube: installato vs disponibile."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_device_class = None
    # Nessun install da HA: l'aggiornamento parte solo dall'app EP Cube
    _attr_supported_features = UpdateEntityFeature(0)
    _attr_icon = "mdi:cube-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_firmware_update"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    def _extras(self):
        return (self.coordinator.data or {}).get("extras") or {}

    @property
    def installed_version(self):
        firmware = self._extras().get("firmware") or {}
        return firmware.get("firmwareVersion")

    @property
    def latest_version(self):
        """Versione disponibile; se il server non ne propone, resta l'installata."""
        upgrade = self._extras().get("upgrade") or {}
        new = upgrade.get("newSoftWareVersion")
        # newSoftWareVersion compare solo quando c'è davvero un aggiornamento
        return new or self.installed_version

    @property
    def release_summary(self):
        if self.latest_version and self.latest_version != self.installed_version:
            return ("Aggiornamento firmware disponibile. L'installazione va avviata "
                    "dall'app EP Cube (o tramite l'installatore).")
        return None
