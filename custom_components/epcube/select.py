from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .entity import bind_entities_to_entry
from .payload import build_switch_mode_payload
from .api import async_post_switch_mode
from .const import DOMAIN
from .translations import OPERATION_MODES

import logging
import json

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "1": "Autoconsumo",
    "2": "Tariffazione",
    "3": "Backup",
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeModeSelect(coordinator, entry)]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities, True)


class EpCubeModeSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.region = entry.data.get("region", "EU")
        self.entity_description = SelectEntityDescription(
            key="workstatus",
            name="EP CUBE Modalità",
            icon="mdi:transmission-tower",
            entity_category=EntityCategory.CONFIG
        )
        self._attr_unique_id = "epcube_mode_select"
        self._attr_options = list(MODE_MAP.values())
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EP CUBE",
            "manufacturer": "CanadianSolar",
        }

    @property
    def current_option(self):
        raw = str(self.coordinator.data["data"].get("workstatus"))
        return MODE_MAP.get(raw, "Sconosciuto")

    async def async_select_option(self, option: str):
        mode = REVERSE_MODE_MAP.get(option)
        if not mode:
            _LOGGER.warning("Modalità non valida selezionata: %s", option)
            return

        data = self.coordinator.data["data"]

        # Payload completo: i campi omessi vengono riportati al default dal
        # server, cancellando le fasce TOU e i SoC di riserva (issue #18, #31)
        payload = build_switch_mode_payload(data, work_status=mode)

        # Parametri specifici della modalità di destinazione
        if mode == "2":  # Tariffazione
            payload["evChargerReserveSoc"] = data.get("evchargerreservesoc", 50)

        session = async_get_clientsession(self.hass)
        if await async_post_switch_mode(session, self.entry, payload, f"modalità {option}"):
            await self.coordinator.async_request_refresh()
