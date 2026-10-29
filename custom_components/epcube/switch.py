from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import (
    bind_entities_to_entry, setting_value as _setting, async_save_setting as _async_save,
    winter_mode_supported, region_of,
)
from .payload import build_switch_mode_payload
from .extras import has_winter_mode
from homeassistant.exceptions import HomeAssistantError
from .api import (
    async_post_switch_mode, async_read_switch_mode_field, async_set_winter_protect, WINTER_PROTECT_ON,
    SETTING_ALLOW_CHARGING, SETTING_WEATHER_WATCH, SETTING_WINTER_MODE,
    SETTING_OFF_GRID_NOTIFICATION, SETTING_INDICATOR_LIGHT, SETTING_AUTO_UPDATE,
)
from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [EpCubeAllowChargingFromGridSwitch(coordinator, entry)]

    # App EU: modalità invernale in getSwitchMode (winterProtect 170/85)
    data = coordinator.data or {}
    if region_of(entry) == "EU" and "winterProtect" in (data.get("switch_mode") or {}):
        device = (data.get("extras") or {}).get("user_device")
        if not device or has_winter_mode(device, "EU"):
            entities.append(EpCubeEuWinterModeSwitch(coordinator, entry))

    # Solo le impostazioni che il sistema espone (dipendono da modello e regione)
    settings = (coordinator.data or {}).get("settings") or {}
    entities += [
        EpCubeSettingSwitch(coordinator, entry, spec)
        for spec in SETTING_SWITCHES
        if spec[1] in settings
        and (spec[0] != "winter_mode" or winter_mode_supported(coordinator, entry))
    ]
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
            translation_key="allow_charging_from_grid",
            icon="mdi:transmission-tower-import",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_has_entity_name = True
        self._attr_unique_id = "epcube_allow_charging_from_grid"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EP CUBE",
            "manufacturer": "CanadianSolar",
        }

    @property
    def is_on(self):
        value = _setting(self.coordinator, "allowchargingxiagrid")
        if value is None:
            data = self.coordinator.data.get("data", {}) if self.coordinator.data else {}
            value = data.get("allowchargingxiagrid", "0")
        return str(value) == "1"

    async def async_turn_on(self, **kwargs):
        await self._send("1")

    async def async_turn_off(self, **kwargs):
        await self._send("0")

    async def _send(self, value: str):
        if region_of(self.entry) == "US":
            # App USA: saveSettings tipo 10 scrive solo questo campo
            await _async_save(
                self, SETTING_ALLOW_CHARGING, {"allowChargingXiaGrid": value},
                f"allowChargingXiaGrid={value}",
            )
            return
        # App EU: il campo fa parte della modalità (switchMode); payload completo,
        # salvato senza cambiare modalità
        data = self.coordinator.data.get("data", {}) if self.coordinator.data else {}
        if not data.get("devid"):
            _LOGGER.error("Device ID non disponibile, impossibile aggiornare allowChargingXiaGrid")
            return
        payload = build_switch_mode_payload(
            data, only_save="1", current=self.coordinator.data.get("switch_mode"),
            allowChargingXiaGrid=value,
        )
        if not await async_post_switch_mode(self.hass, self.entry, payload, f"allowChargingXiaGrid={value}"):
            raise HomeAssistantError("Il server EP Cube ha rifiutato la modifica (vedi log)")
        # Su alcuni firmware il campo è bloccato (di solito dall'installatore):
        # il server risponde "Success" ma il valore non cambia
        applied = await async_read_switch_mode_field(
            self.hass, self.entry, data["devid"], "allowChargingXiaGrid"
        )
        await self.coordinator.async_request_refresh()
        if applied is not None and str(applied) != value:
            raise HomeAssistantError(
                "Il gateway ha accettato la richiesta ma la ricarica da rete non è "
                "cambiata: su questo impianto l'impostazione è bloccata "
                "(di solito la sblocca solo l'installatore)"
            )


def _soc(coordinator, key, default):
    value = _setting(coordinator, key)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# (chiave entità, campo di getSettingsData, tipo saveSettings, icona, campi da
# inviare). saveSettings riscrive tutti i campi del suo tipo: quelli collegati
# (es. il SoC) vengono rimandati col valore attuale
SETTING_SWITCHES = (
    # Winter mode: con temperatura e SoC bassi carica la batteria al SoC impostato
    ("winter_mode", "winterprotect", SETTING_WINTER_MODE, "mdi:snowflake",
     lambda c, on: {"winterProtect": 1 if on else 0,
                    "winterProtectSoc": _soc(c, "winterprotectsoc", 50)}),
    # Weather watch: carica le batterie in previsione di eventi meteo estremi
    ("weather_watch", "weatherwatch", SETTING_WEATHER_WATCH, "mdi:weather-lightning-rainy",
     lambda c, on: {"weatherWatch": "1" if on else "0"}),
    # Notifica dell'app quando in blackout la batteria scende al SoC impostato
    ("off_grid_notification", "offgridnotification", SETTING_OFF_GRID_NOTIFICATION, "mdi:bell-alert",
     lambda c, on: {"offGridNotification": "1" if on else "0",
                    "offGridNotificationSoc": _soc(c, "offgridnotificationsoc", 30)}),
    # Luce indicatore sul lato destro dell'inverter ibrido
    ("indicator_light", "indicatorlight", SETTING_INDICATOR_LIGHT, "mdi:led-on",
     lambda c, on: {"indicatorLight": "1" if on else "0"}),
    # Aggiornamento automatico del firmware
    ("auto_update_firmware", "aotuupdatefirmware", SETTING_AUTO_UPDATE, "mdi:update",
     lambda c, on: {"aotuUpdateFirmware": "1" if on else "0"}),
)


class EpCubeSettingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch su un'impostazione di getSettingsData / saveSettings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, spec):
        super().__init__(coordinator)
        self.entry = entry
        key, self._setting_key, self._setting_type, icon, self._fields = spec
        self._attr_translation_key = key
        self._attr_icon = icon
        self._attr_unique_id = f"epcube_{key}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def available(self):
        return super().available and _setting(self.coordinator, self._setting_key) is not None

    @property
    def is_on(self):
        return str(_setting(self.coordinator, self._setting_key)) == "1"

    async def async_turn_on(self, **kwargs):
        await self._send(True)

    async def async_turn_off(self, **kwargs):
        await self._send(False)

    async def _send(self, on):
        fields = self._fields(self.coordinator, on)
        await _async_save(self, self._setting_type, fields, f"{self._setting_key}={int(on)}")


class EpCubeEuWinterModeSwitch(CoordinatorEntity, SwitchEntity):
    """Modalità invernale dell'app EU (settingWinterProtect)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "winter_mode"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        # Stesso unique_id dello switch USA: è la stessa impostazione
        self._attr_unique_id = "epcube_winter_mode"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def _value(self):
        return ((self.coordinator.data or {}).get("switch_mode") or {}).get("winterProtect")

    @property
    def available(self):
        return super().available and self._value is not None

    @property
    def is_on(self):
        return str(self._value) == str(WINTER_PROTECT_ON)

    async def async_turn_on(self, **kwargs):
        await self._send(True)

    async def async_turn_off(self, **kwargs):
        await self._send(False)

    async def _send(self, enabled):
        data = self.coordinator.data.get("data", {}) if self.coordinator.data else {}
        if not data.get("devid"):
            _LOGGER.error("Device ID non disponibile, impossibile salvare la modalità invernale")
            return
        if await async_set_winter_protect(self.hass, self.entry, data["devid"], enabled):
            await self.coordinator.async_request_refresh()
