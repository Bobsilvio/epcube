from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .entity import bind_entities_to_entry
from .payload import build_switch_mode_payload
from .api import async_post_switch_mode
from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeAllowChargingFromGridSwitch(coordinator, entry)]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities, True)


class EpCubeAllowChargingFromGridSwitch(CoordinatorEntity, SwitchEntity):
    """Toggle per allowChargingXiaGrid: salva senza cambiare modalità (onlySave=1)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.region = entry.data.get("region", "EU")
        self.entity_description = SwitchEntityDescription(
            key="allow_charging_from_grid",
            name="EP CUBE Permetti Ricarica da Rete",
            icon="mdi:transmission-tower-import",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_unique_id = "epcube_allow_charging_from_grid"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EP CUBE",
            "manufacturer": "CanadianSolar",
        }

    @property
    def is_on(self):
        data = self.coordinator.data.get("data", {}) if self.coordinator.data else {}
        return str(data.get("allowchargingxiagrid", "0")) == "1"

    async def async_turn_on(self, **kwargs):
        await self._send("1")

    async def async_turn_off(self, **kwargs):
        await self._send("0")

    async def _send(self, value: str):
        data = self.coordinator.data.get("data", {}) if self.coordinator.data else {}
        if not data.get("devid"):
            _LOGGER.error("Device ID non disponibile, impossibile aggiornare allowChargingXiaGrid")
            return

        # onlySave=1: salva la configurazione senza applicare un cambio modalità
        payload = build_switch_mode_payload(data, only_save="1", allowChargingXiaGrid=value)

        session = async_get_clientsession(self.hass)
        if await async_post_switch_mode(session, self.entry, payload, f"allowChargingXiaGrid={value}"):
            await self.coordinator.async_request_refresh()
