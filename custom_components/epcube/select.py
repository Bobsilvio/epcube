from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import (
    DOMAIN, get_base_url, USER_AGENT, HTTP_TIMEOUT, 
    HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)
from .translations import OPERATION_MODES

import logging
import aiohttp
import asyncio
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
    async_add_entities([EpCubeModeSelect(coordinator, entry)], True)


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
        payload = {
            "devId": data.get("devid"),
            "workStatus": mode,
            "weatherWatch": "0",
            "onlySave": "0",
            # Preserve TOU settings regardless of target mode
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
            "allowChargingXiaGrid": str(data.get("allowchargingxiagrid", "1")),
        }

        # Aggiungi i parametri specifici per modalità
        if mode == "1":  # Autoconsumo
            pass  # selfConsumptioinReserveSoc già incluso sopra
        elif mode == "2":  # Tariffazione
            payload["evChargerReserveSoc"] = data.get("evchargerreservesoc", 50)
        elif mode == "3":  # Backup
            payload["backupPowerReserveSoc"] = str(data.get("backuppowerreservesoc", 50))

        _LOGGER.debug("Invio payload switchMode (modalità %s): %s", option, payload)
        await self._post_switch_mode(payload)

    async def _post_switch_mode(self, payload):
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

        timeout = aiohttp.ClientTimeout(
            total=HTTP_TIMEOUT,
            connect=HTTP_CONNECT_TIMEOUT
        )

        _LOGGER.debug("Invio payload switchMode (modalità): %s", payload)

        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=payload) as resp:
                        text = await resp.text()
                        
                        if resp.status == 200:
                            _LOGGER.info("Modalità EP Cube aggiornata correttamente. Risposta: %s", text)
                            await self.coordinator.async_request_refresh()
                            return
                        elif resp.status == 401:
                            _LOGGER.error("Token non valido o scaduto (401). Cambio modalità fallito.")
                            return
                        elif resp.status == 403:
                            _LOGGER.error("Accesso negato (403). Cambio modalità fallito.")
                            return
                        elif resp.status == 429:
                            _LOGGER.warning("Rate limit raggiunto al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY * 2)  # Doppio delay per rate limit
                                continue
                            else:
                                _LOGGER.error("Rate limit: riprova più tardi")
                                return
                        elif resp.status >= 500:
                            _LOGGER.warning("Errore server %s al tentativo %d/%d. Risposta: %s", 
                                          resp.status, attempt + 1, MAX_RETRIES, text)
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            else:
                                _LOGGER.error("Errore server persistente nel cambio modalità")
                                return
                        else:
                            _LOGGER.error("Errore HTTP %s nel cambio modalità EP Cube: %s", 
                                        resp.status, text)
                            return
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    _LOGGER.error("Timeout: cambio modalità fallito")
                    return
            except aiohttp.ClientError as e:
                _LOGGER.warning("Errore connessione al tentativo %d/%d: %s", 
                               attempt + 1, MAX_RETRIES, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    _LOGGER.error("Errore connessione persistente nel cambio modalità")
                    return
            except Exception as e:
                _LOGGER.exception("Errore inaspettato durante cambio modalità: %s", e)
                return
    
