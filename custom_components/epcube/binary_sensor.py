"""Stati on/off ricavati dai codici numerici di homeDeviceInfo.

Significati presi dall'app Android EP Cube (2.6.2), dove decidono cosa
mostra la schermata Home.
"""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .entity import bind_entities_to_entry
from .const import DOMAIN

from dataclasses import dataclass
import logging

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EpCubeBinarySensorDescription(BinarySensorEntityDescription):
    """field: chiave in homeDeviceInfo; on_values: valori che significano acceso."""

    field: str = ""
    on_values: tuple = ()


BINARY_SENSORS = (
    # status "0": l'app mostra l'icona off-grid e blocca il cambio modalità
    EpCubeBinarySensorDescription(
        key="off_grid",
        translation_key="off_grid",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:transmission-tower-off",
        field="status",
        on_values=("0",),
    ),
    # gridLight 1: icona della rete accesa nel flusso di potenza
    EpCubeBinarySensorDescription(
        key="grid_present",
        translation_key="grid_present",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:transmission-tower",
        field="gridlight",
        on_values=("1",),
    ),
    # systemSpecialWorkMode 6: la Home mostra "Backup (winter mode)"
    EpCubeBinarySensorDescription(
        key="winter_mode_active",
        translation_key="winter_mode_active",
        icon="mdi:snowflake",
        field="systemspecialworkmode",
        on_values=("6",),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = (coordinator.data or {}).get("data") or {}
    entities = [
        EpCubeBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.field in data
    ]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities)


class EpCubeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"epcube_{description.key}"
        # entity_id suggerito indipendente dalla lingua (con più impianti HA
        # aggiunge _2, _3): così automazioni e README restano validi
        self.entity_id = f"binary_sensor.epcube_{description.key}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def _value(self):
        data = (self.coordinator.data or {}).get("data") or {}
        return data.get(self.entity_description.field)

    @property
    def available(self):
        return super().available and self._value is not None

    @property
    def is_on(self):
        value = self._value
        if value is None:
            return None
        return str(value) in self.entity_description.on_values
