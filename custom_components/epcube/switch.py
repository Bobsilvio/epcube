from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import bind_entities_to_entry
from .const import (
    DOMAIN, get_base_url, USER_AGENT, HTTP_TIMEOUT,
    HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

import logging
import aiohttp
import asyncio

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
        dev_id = data.get("devid")
        if not dev_id:
            _LOGGER.error("Device ID non disponibile, impossibile aggiornare allowChargingXiaGrid")
            return

        # Payload completo preservando lo stato corrente; onlySave=1 = salva senza cambiare modalità
        payload = {
            "devId": dev_id,
            "workStatus": str(data.get("workstatus", "1")),
            "weatherWatch": "0",
            "onlySave": "1",
            "touType": data.get("toutype", 0),
            "peakTimeList": data.get("peaktimelist", []),
            "midPeakTimeList": data.get("midpeaktimelist", []),
            "offPeakTimeList": data.get("offpeaktimelist", []),
            "peakTimeListNonWorkDay": data.get("peaktimelistnonworkday", []),
            "midPeakTimeListNonWorkDay": data.get("midpeaktimelistnonworkday", []),
            "offPeakTimeListNonWorkDay": data.get("offpeaktimelistnonworkday", []),
            "dayLightPeakTimeList": data.get("daylightpeaktimelist", []),
            "dayLightMidPeakTimeList": data.get("daylightmidpeaktimelist", []),
            "dayLightOffPeakTimeList": data.get("daylightoffpeaktimelist", []),
            # L'API EP Cube richiede array di stringhe; il coordinator può restituire interi
            "activeWeek": [str(d) for d in data.get("activeweek", ["1", "2", "3", "4", "5"])],
            "activeWeekNonWorkDay": [str(d) for d in data.get("activeweeknonworkday", ["6", "7"])],
            "dayLightActiveWeek": [str(d) for d in data.get("daylightactiveweek", ["1", "2", "3", "4", "5"])],
            "dayLightActiveWeekNonWorkDay": [str(d) for d in data.get("daylightactiveweeknonworkday", ["6", "7"])],
            "dayLightSavingTime": data.get("daylightsavingtime", False),
            "selfConsumptioinReserveSoc": str(data.get("selfconsumptioinreservesoc", 5)),
            "backupPowerReserveSoc": str(data.get("backuppowerreservesoc", 50)),
            "allowChargingXiaGrid": value,
        }

        base_url = get_base_url(self.region)
        url = f"{base_url}/device/switchMode"
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "authorization": self.entry.data.get("token"),
            "user-agent": USER_AGENT,
            "accept-language": "it-IT",
            "accept-encoding": "gzip, deflate, br",
        }
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

        _LOGGER.debug("Invio payload allowChargingXiaGrid=%s: %s", value, payload)

        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=payload) as resp:
                        text = await resp.text()
                        if resp.status == 200:
                            _LOGGER.info("allowChargingXiaGrid impostato a %s. Risposta: %s", value, text)
                            await self.coordinator.async_request_refresh()
                            return
                        if resp.status in (401, 403):
                            _LOGGER.error("Autenticazione fallita (%s) impostando allowChargingXiaGrid: %s",
                                          resp.status, text)
                            return
                        if resp.status == 429:
                            _LOGGER.warning("Rate limit al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY * 2)
                                continue
                            _LOGGER.error("Rate limit persistente impostando allowChargingXiaGrid")
                            return
                        if resp.status >= 500:
                            _LOGGER.warning("Errore server %s al tentativo %d/%d. Risposta: %s",
                                            resp.status, attempt + 1, MAX_RETRIES, text)
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            _LOGGER.error("Errore server persistente impostando allowChargingXiaGrid")
                            return
                        _LOGGER.error("Errore HTTP %s impostando allowChargingXiaGrid: %s", resp.status, text)
                        return
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                _LOGGER.error("Timeout persistente impostando allowChargingXiaGrid")
                return
            except aiohttp.ClientError as e:
                _LOGGER.warning("Errore connessione al tentativo %d/%d: %s",
                                attempt + 1, MAX_RETRIES, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                _LOGGER.error("Errore connessione persistente impostando allowChargingXiaGrid")
                return
            except Exception as e:
                _LOGGER.exception("Errore inaspettato impostando allowChargingXiaGrid: %s", e)
                return
