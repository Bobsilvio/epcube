from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN, get_base_url, USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT

import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

SOC_KEYS = {
    "selfconsumptioinreservesoc": "selfConsumptioinReserveSoc",
    "backuppowerreservesoc": "backupPowerReserveSoc",
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        EpCubeDynamicSocNumber(coordinator, entry),
        EpCubeStaticSocNumber(coordinator, entry, "selfconsumptioinreservesoc", "SOC Autoconsumo", 0, 100),
        EpCubeStaticSocNumber(coordinator, entry, "backuppowerreservesoc", "SOC Backup", 50, 100),
        # Number entities per TOU (Tariffazione)
        EpCubeTouHourNumber(coordinator, entry, "peak_start", "TOU Picco Inizio", 0),
        EpCubeTouHourNumber(coordinator, entry, "peak_end", "TOU Picco Fine", 0),
        EpCubeTouHourNumber(coordinator, entry, "midpeak_start", "TOU Semi-Picco Inizio", 0),
        EpCubeTouHourNumber(coordinator, entry, "midpeak_end", "TOU Semi-Picco Fine", 0),
        EpCubeTouHourNumber(coordinator, entry, "offpeak_start", "TOU Fuori Picco Inizio", 0),
        EpCubeTouHourNumber(coordinator, entry, "offpeak_end", "TOU Fuori Picco Fine", 0),
    ], True)


class EpCubeDynamicSocNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self.region = entry.data.get("region", "EU")
        self.base_url = get_base_url(self.region)
        self.entity_description = NumberEntityDescription(
            key="epcube_dynamic_soc",
            name="EPCUBE SOC Dinamico",
            icon="mdi:battery-charging",
            entity_category=EntityCategory.CONFIG,
        )
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
        dev_id = self.coordinator.data.get("data", {}).get("devid")
        work_status = self._mode

        key_original = self._soc_key
        payload = {
            "devId": dev_id,
            "workStatus": str(work_status),
            "weatherWatch": "0",
            "onlySave": "0",
            key_original: str(int(value)),
        }

        _LOGGER.debug("Invio payload switchMode (SOC dinamico): %s", payload)
        await self._post_switch_mode(payload)

    async def _post_switch_mode(self, payload):
        url = f"{self.base_url}/device/switchMode"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.entry.data.get("token"),
            "User-Agent": "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)",
            "Accept": "*/*",
            "Accept-Language": "it-IT",
            "Accept-Encoding": "gzip, deflate, br"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                text = await resp.text()
                if resp.status != 200:
                    _LOGGER.error("Errore nell'invio SoC EP Cube dinamico: %s", text)
                else:
                    _LOGGER.info("SOC dinamico aggiornato correttamente. Risposta: %s", text)
                    await self.coordinator.async_request_refresh()


class EpCubeStaticSocNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, key, name, min_val, max_val):
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self.region = entry.data.get("region", "EU")
        self.base_url = get_base_url(self.region)
        self.original_key = SOC_KEYS.get(key.lower(), key)
        self.entity_description = NumberEntityDescription(
            key=self.original_key,
            name=f"EPCUBE {name}",
            icon="mdi:battery-charging",
            entity_category=EntityCategory.CONFIG,
        )
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
        dev_id = self.coordinator.data.get("data", {}).get("devid")
        work_status = self.coordinator.data.get("data", {}).get("workstatus")
        

        payload = {
            "devId": dev_id,
            "workStatus": str(work_status),
            "weatherWatch": "0",
            "onlySave": "0",
            self.original_key: str(int(value)),
        }

        _LOGGER.debug("Invio payload switchMode (SOC statico): %s", payload)
        await self._post_switch_mode(payload)

    async def _post_switch_mode(self, payload):
        url = f"{self.base_url}/device/switchMode"
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.entry.data.get("token"),
            "User-Agent": "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)",
            "Accept": "*/*",
            "Accept-Language": "it-IT",
            "Accept-Encoding": "gzip, deflate, br"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                text = await resp.text()
                if resp.status != 200:
                    _LOGGER.error("Errore nell'invio SoC EP Cube statico: %s", text)
                else:
                    _LOGGER.info("SOC statico aggiornato correttamente. Risposta: %s", text)
                    await self.coordinator.async_request_refresh()

class EpCubeTouHourNumber(CoordinatorEntity, RestoreEntity, NumberEntity):
    """Number entity per configurare gli orari TOU (Time of Use)."""

    def __init__(self, coordinator, entry, hour_type, name, default_value):
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self.region = entry.data.get("region", "EU")
        self.base_url = get_base_url(self.region)
        self.hour_type = hour_type
        self._default_value = default_value

        self.entity_description = NumberEntityDescription(
            key=f"epcube_tou_{hour_type}",
            name=f"EPCUBE {name} (HH:00)",
            icon="mdi:clock-outline",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_unique_id = f"epcube_tou_{hour_type}_fix_range_v3"
        self._attr_step = 1
        self._attr_native_min_value = 0
        self._attr_native_max_value = 23
        self._attr_native_unit_of_measurement = None
        self._attr_mode = "slider"
        self._current_value = default_value
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
            "entry_type": "service",
            "configuration_url": f"{self.base_url}/"
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._current_value = int(float(last_state.state))
            except (ValueError, TypeError):
                self._current_value = self._default_value

    @property
    def native_value(self):
        return self._current_value

    async def async_set_native_value(self, value: float):
        int_value = max(0, min(23, int(value)))
        self._current_value = int_value
        _LOGGER.debug("Impostato %s = %d (%02d:00)", self.hour_type, self._current_value, int_value)
        self.async_write_ha_state()