from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory
from .entity import (
    bind_entities_to_entry, setting_value, async_save_setting, winter_mode_supported,
    tou_slots_supported,
)
from .api import SETTING_WINTER_MODE, SETTING_SLEEP_MODE, SETTING_OFF_GRID_NOTIFICATION, SETTING_EV_CHARGER
from .payload import build_switch_mode_payload
from .api import async_post_switch_mode
from .const import DOMAIN, get_base_url
from .tou import (
    TOU_BANDS, async_save_band, band_slots, pending_prices, tou_list_price, tou_list_to_text, with_price,
)

import logging

_LOGGER = logging.getLogger(__name__)

SOC_KEYS = {
    "selfconsumptioinreservesoc": "selfConsumptioinReserveSoc",
    "backuppowerreservesoc": "backupPowerReserveSoc",
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        EpCubeDynamicSocNumber(coordinator, entry),
        EpCubeStaticSocNumber(coordinator, entry, "selfconsumptioinreservesoc", "self_consumption_reserve_soc", 0, 100),
        EpCubeStaticSocNumber(coordinator, entry, "backuppowerreservesoc", "backup_reserve_soc", 50, 100),
    ] + [
        # Parametri dell'override batteria scelto dal menu "Override batteria"
        EpCubeOverrideNumber(coordinator, entry, spec) for spec in OVERRIDE_NUMBERS
    ] + [
        # Prezzo di ogni tipo di fascia della Tariffazione (gli orari sono in text.py)
        EpCubeTouPriceNumber(coordinator, entry, band) for band in TOU_BANDS
    ]
    # Prezzi target della tariffa dinamica (app EU), se il sistema li gestisce
    data = (coordinator.data or {}).get("data") or {}
    current = (coordinator.data or {}).get("switch_mode") or {}
    if str(data.get("dynamicpriceauth")) == "1" or str(data.get("toutype")) == "1":
        entities += [
            EpCubeDynamicPriceNumber(coordinator, entry, key, field)
            for key, field in DYNAMIC_PRICE_FIELDS.items()
            if field in current
        ]

    settings = (coordinator.data or {}).get("settings") or {}
    entities += [
        EpCubeSettingNumber(coordinator, entry, spec)
        for spec in SETTING_NUMBERS
        if spec["setting"] in settings and spec.get("enabled", lambda st: True)(settings)
        and (spec["key"] != "winter_mode_soc" or winter_mode_supported(coordinator, entry))
    ]
    bind_entities_to_entry(entities, entry)
    async_add_entities(entities, True)


class EpCubeDynamicSocNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self.region = entry.data.get("region", "EU")
        self.base_url = get_base_url(self.region)
        self.entity_description = NumberEntityDescription(
            key="epcube_dynamic_soc",
            translation_key="dynamic_reserve_soc",
            icon="mdi:battery-charging",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_has_entity_name = True
        self._attr_unique_id = "epcube_soc_dynamic"
        self._attr_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
            "entry_type": "service",
            "configuration_url": f"{self.base_url}/"
        }

        if coordinator.data and coordinator.data.get("data"):
            mode = str(coordinator.data["data"].get("workstatus", ""))
        else:
            mode = ""

        if mode == "1":
            self._attr_native_min_value = 0
        else:
            self._attr_native_min_value = 50
        self._attr_native_max_value = 100

    @property
    def _mode(self):
        return str(self.coordinator.data.get("data", {}).get("workstatus", ""))

    @property
    def _soc_key(self):
        return {
            "1": "selfConsumptioinReserveSoc",
            "3": "backupPowerReserveSoc"
        }.get(self._mode)

    @property
    def native_value(self):
        soc_key = self._soc_key
        if soc_key is None:
            return None
        value = self.coordinator.data.get("data", {}).get(soc_key.lower())
        _LOGGER.debug("SOC attuale (%s): %s", soc_key.lower(), value)
        return int(value) if value is not None else None
    
    
    

    async def async_set_native_value(self, value: float):
        soc_key = self._soc_key
        if soc_key is None:
            _LOGGER.warning(
                "Modalità %s senza SoC di riserva associato: valore ignorato", self._mode
            )
            return

        data = self.coordinator.data.get("data", {})

        # Payload completo: i campi omessi vengono riportati al default dal
        # server, azzerando fasce TOU e l'altro SoC di riserva (issue #31)
        payload = build_switch_mode_payload(
            data,
            work_status=self._mode,
            current=self.coordinator.data.get("switch_mode"),
            **{soc_key: str(int(value))},
        )

        if await async_post_switch_mode(self.hass, self.entry, payload, "SOC dinamico"):
            await self.coordinator.async_request_refresh()


class EpCubeStaticSocNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, key, translation_key, min_val, max_val):
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self.region = entry.data.get("region", "EU")
        self.base_url = get_base_url(self.region)
        self.original_key = SOC_KEYS.get(key.lower(), key)
        self.entity_description = NumberEntityDescription(
            key=self.original_key,
            translation_key=translation_key,
            icon="mdi:battery-charging",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_has_entity_name = True
        self._attr_unique_id = f"epcube_soc_{self.original_key}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_mode = "slider"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
            "entry_type": "service",
            "configuration_url": f"{self.base_url}/"
        }

    @property
    def native_value(self):
        value = self.coordinator.data.get("data", {}).get(self.original_key.lower())
        _LOGGER.debug("SOC statico attuale (%s): %s", self.original_key.lower(), value)
        return int(value) if value is not None else None
    

    async def async_set_native_value(self, value: float):
        data = self.coordinator.data.get("data", {})

        # Payload completo, vedi EpCubeDynamicSocNumber (issue #31)
        payload = build_switch_mode_payload(
            data,
            current=self.coordinator.data.get("switch_mode"),
            **{self.original_key: str(int(value))},
        )

        if await async_post_switch_mode(self.hass, self.entry, payload, "SOC statico"):
            await self.coordinator.async_request_refresh()

def _int_setting(coordinator, key, default):
    value = setting_value(coordinator, key)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# Impostazioni numeriche di getSettingsData / saveSettings. "fields" costruisce
# il corpo del tipo: i campi collegati (es. l'interruttore) col valore attuale
SETTING_NUMBERS = (
    # SoC a cui il winter mode porta la batteria con temperature basse
    {"key": "winter_mode_soc", "setting": "winterprotectsoc", "type": SETTING_WINTER_MODE,
     "min": 0, "max": 100, "icon": "mdi:snowflake-thermometer",
     "fields": lambda c, v: {"winterProtect": _int_setting(c, "winterprotect", 0),
                             "winterProtectSoc": v}},
    # SoC sotto cui il sistema entra in sleep mode: l'app accetta 5-30%
    {"key": "sleep_mode_soc", "setting": "lowpowersoc", "type": SETTING_SLEEP_MODE,
     "min": 5, "max": 30, "icon": "mdi:sleep",
     "fields": lambda c, v: {"lowPowerSoc": str(v)}},
    # SoC a cui l'app avvisa durante un blackout
    {"key": "off_grid_notification_soc", "setting": "offgridnotificationsoc",
     "type": SETTING_OFF_GRID_NOTIFICATION, "min": 0, "max": 100, "icon": "mdi:bell-alert",
     "fields": lambda c, v: {
         "offGridNotification": str(setting_value(c, "offgridnotification") or "0"),
         "offGridNotificationSoc": v}},
    # Riserva per caricatore EV / grandi carichi, solo se presenti
    {"key": "ev_charger_reserve_soc", "setting": "evchargerreservesoc", "type": SETTING_EV_CHARGER,
     "min": 0, "max": 100, "icon": "mdi:ev-station",
     "enabled": lambda st: bool(st.get("haveev")),
     "fields": lambda c, v: {"evChargerReserveSoc": v}},
)


class EpCubeSettingNumber(CoordinatorEntity, NumberEntity):
    """Number su un'impostazione di getSettingsData / saveSettings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry, spec):
        super().__init__(coordinator)
        self.entry = entry
        self._spec = spec
        self._attr_translation_key = spec["key"]
        self._attr_icon = spec["icon"]
        self._attr_native_min_value = spec["min"]
        self._attr_native_max_value = spec["max"]
        self._attr_unique_id = f"epcube_{spec['key']}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def available(self):
        return super().available and setting_value(self.coordinator, self._spec["setting"]) is not None

    @property
    def native_value(self):
        value = setting_value(self.coordinator, self._spec["setting"])
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value):
        value = int(value)
        await async_save_setting(
            self, self._spec["type"], self._spec["fields"](self.coordinator, value),
            f"{self._spec['setting']}={value}",
        )


# Soglie della tariffa dinamica: sotto "Prezzo target" EP Cube carica dalla
# rete, sopra la soglia di vendita scarica (testo dell'app EU)
DYNAMIC_PRICE_FIELDS = {
    "dynamic_charge_price": "dynamicChargePrice",
    "dynamic_discharge_price": "dynamicDischargePrice",
}


class EpCubeDynamicPriceNumber(CoordinatorEntity, NumberEntity):
    """Prezzo target della tariffa dinamica, salvato senza cambiare modalità."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:cash-sync"
    _attr_mode = "box"
    # I prezzi dinamici possono essere negativi
    _attr_native_min_value = -10
    _attr_native_max_value = 10
    _attr_native_step = 0.001

    def __init__(self, coordinator, entry, key, field):
        super().__init__(coordinator)
        self.entry = entry
        self._field = field
        self._attr_translation_key = key
        self._attr_unique_id = f"epcube_{key}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_unit_of_measurement(self):
        unit = ((self.coordinator.data or {}).get("data") or {}).get("unitdefault")
        return f"{unit}/kWh" if isinstance(unit, str) and unit else None

    @property
    def native_value(self):
        value = ((self.coordinator.data or {}).get("switch_mode") or {}).get(self._field)
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value):
        data = self.coordinator.data.get("data", {})
        # onlySave=1: salva il prezzo senza cambiare modalità
        payload = build_switch_mode_payload(
            data,
            only_save="1",
            current=self.coordinator.data.get("switch_mode"),
            **{self._field: f"{value:g}"},
        )
        if await async_post_switch_mode(self.hass, self.entry, payload, f"{self._field}={value:g}"):
            await self.coordinator.async_request_refresh()


# Valori usati dal menu "Override batteria": restano in Home Assistant, non sul
# gateway. Durata 0 = finché non si torna su "Nessuno"
OVERRIDE_NUMBERS = (
    {"key": "override_target_soc", "setting": "target_soc", "min": 0, "max": 100,
     "step": 5, "unit": "%", "icon": "mdi:battery-arrow-up"},
    {"key": "override_duration", "setting": "duration", "min": 0, "max": 1440,
     "step": 15, "unit": "min", "icon": "mdi:timer-outline"},
)


class EpCubeOverrideNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """SoC obiettivo e durata per il prossimo override scelto dal menu."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = "box"

    def __init__(self, coordinator, entry, spec):
        super().__init__(coordinator)
        self.entry = entry
        self._setting = spec["setting"]
        self._attr_translation_key = spec["key"]
        self._attr_icon = spec["icon"]
        self._attr_native_min_value = spec["min"]
        self._attr_native_max_value = spec["max"]
        self._attr_native_step = spec["step"]
        self._attr_native_unit_of_measurement = spec["unit"]
        self._attr_unique_id = f"epcube_{spec['key']}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def _manager(self):
        return self.hass.data[DOMAIN][self.entry.entry_id]["override"]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._manager.settings[self._setting] = int(float(last_state.state))
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self):
        return self._manager.settings[self._setting]

    async def async_set_native_value(self, value):
        self._manager.settings[self._setting] = int(value)
        self.async_write_ha_state()


class EpCubeTouPriceNumber(CoordinatorEntity, NumberEntity):
    """Prezzo di un tipo di fascia della Tariffazione, uguale per tutte le sue fasce."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:currency-eur"
    _attr_mode = "box"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 0.001

    def __init__(self, coordinator, entry, band):
        super().__init__(coordinator)
        self.entry = entry
        self._band = band
        self._attr_translation_key = f"tou_{band}_price"
        self._attr_unique_id = f"epcube_tou_{band}_price"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def available(self):
        return super().available and tou_slots_supported(self.coordinator, self.entry)

    @property
    def native_unit_of_measurement(self):
        unit = ((self.coordinator.data or {}).get("data") or {}).get("unitdefault")
        return f"{unit}/kWh" if isinstance(unit, str) and unit else None

    @property
    def native_value(self):
        price = tou_list_price(band_slots(self.coordinator, self._band))
        if price is None:
            price = pending_prices(self.hass, self.entry).get(self._band)
        return price

    async def async_set_native_value(self, value):
        slots = band_slots(self.coordinator, self._band)
        pending_prices(self.hass, self.entry)[self._band] = value
        if tou_list_to_text(slots):
            await async_save_band(
                self.hass, self.entry, self.coordinator, self._band,
                with_price(self.name or self._band, slots, value),
            )
        else:
            # Ancora nessun orario: il prezzo si applica quando li scrivi
            self.async_write_ha_state()
