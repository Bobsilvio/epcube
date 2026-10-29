from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import bind_entities_to_entry
from .payload import build_switch_mode_payload
from .api import async_post_switch_mode
from .const import DOMAIN
from .translations import OPERATION_MODES
from .override import CHARGE, DISCHARGE, HOLD

from homeassistant.exceptions import HomeAssistantError

import logging
import json

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "1": "Autoconsumo",
    "2": "Tariffazione",
    "3": "Backup",
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}

# Tariffa dinamica (app EU): workStatus 2 con touType "1"; la Tariffazione a
# fasce è workStatus 2 con touType "0"
DYNAMIC_OPTION = "Tariffa dinamica"


def _dynamic_available(data):
    return str(data.get("dynamicpriceauth")) == "1" or str(data.get("toutype")) == "1"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        EpCubeModeSelect(coordinator, entry),
        EpCubeBatteryOverrideSelect(coordinator, entry),
    ]
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
            translation_key="operating_mode",
            icon="mdi:transmission-tower",
            entity_category=EntityCategory.CONFIG
        )
        self._attr_has_entity_name = True
        self._attr_unique_id = "epcube_mode_select"
        data = (coordinator.data or {}).get("data") or {}
        self._attr_options = list(MODE_MAP.values()) + (
            [DYNAMIC_OPTION] if _dynamic_available(data) else []
        )
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EP CUBE",
            "manufacturer": "CanadianSolar",
        }

    @property
    def current_option(self):
        data = self.coordinator.data["data"]
        raw = str(data.get("workstatus"))
        if raw == "2" and str(data.get("toutype")) == "1" and DYNAMIC_OPTION in self.options:
            return DYNAMIC_OPTION
        # Valore fuori elenco (es. 6, programma VPP): nessuna opzione
        return MODE_MAP.get(raw)

    async def async_select_option(self, option: str):
        dynamic = option == DYNAMIC_OPTION
        mode = "2" if dynamic else REVERSE_MODE_MAP.get(option)
        if not mode:
            _LOGGER.warning("Modalità non valida selezionata: %s", option)
            return

        data = self.coordinator.data["data"]
        current = self.coordinator.data.get("switch_mode") or {}

        # Come l'app EU: la tariffa dinamica richiede un prezzo target
        if dynamic and not str(current.get("dynamicChargePrice") or "").strip():
            raise HomeAssistantError(
                "Per la tariffa dinamica imposta prima il prezzo target "
                "(entità 'Prezzo target' o app EP Cube)"
            )

        # Payload completo: i campi omessi vengono riportati al default dal
        # server, cancellando le fasce TOU e i SoC di riserva (issue #18, #31).
        # touType come l'app: "1" solo per la tariffa dinamica
        payload = build_switch_mode_payload(
            data, work_status=mode, current=current,
            touType="1" if dynamic else "0",
        )

        # Parametri specifici della modalità di destinazione
        if mode == "2":  # Tariffazione
            payload["evChargerReserveSoc"] = data.get("evchargerreservesoc", 50)

        if not await async_post_switch_mode(self.hass, self.entry, payload, f"modalità {option}"):
            raise HomeAssistantError(f"Il server EP Cube ha rifiutato la modalità {option}")
        await self.coordinator.async_request_refresh()


OVERRIDE_NONE = "none"


class EpCubeBatteryOverrideSelect(CoordinatorEntity, SelectEntity):
    """Override batteria: sceglierlo lo avvia, "Nessuno" lo annulla.

    SoC e durata vengono dai number "SoC obiettivo override" e "Durata override".
    """

    _attr_has_entity_name = True
    _attr_translation_key = "battery_override"
    _attr_icon = "mdi:battery-sync"
    _attr_options = [OVERRIDE_NONE, CHARGE, DISCHARGE, HOLD]

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = "epcube_battery_override_select"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def _manager(self):
        return self.hass.data[DOMAIN][self.entry.entry_id]["override"]

    @property
    def current_option(self):
        active = self._manager.active
        return active.kind if active else OVERRIDE_NONE

    @property
    def extra_state_attributes(self):
        active = self._manager.active
        if active is None:
            return None
        return {
            "target_soc": active.target_soc,
            "ends_at": active.ends_at.isoformat() if active.ends_at else None,
            "previous_reserve": active.previous_reserve,
        }

    async def async_select_option(self, option: str):
        if option == OVERRIDE_NONE:
            await self._manager.async_clear()
        else:
            await self._manager.async_start_from_settings(option)
        self.async_write_ha_state()
