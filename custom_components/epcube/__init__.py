from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .const import (
    DOMAIN, PLATFORMS, DEFAULT_SCAN_INTERVAL, get_base_url, 
    USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)
from .sensor import async_update_data_with_stats
from .state import EpCubeDataState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from datetime import timedelta
import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TOU_SCHEDULE = "set_tou_schedule"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    token = entry.data["token"]
    sn = entry.data["sn"]
    region = entry.data.get("region", "EU")
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    base_url = get_base_url(region)
    url = f"{base_url}/device/homeDeviceInfo?&sgSn={sn}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    state = EpCubeDataState()

    async def async_update_data():
        return await async_update_data_with_stats(session, url, headers, sn, token, hass=hass, entry_id=entry.entry_id)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="epcube_data",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "state": state,
        "config_entry": entry,
    }
    
    await coordinator.async_refresh()
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Registra il service per TOU
    async def handle_set_tou_schedule(call):
        await async_set_tou_schedule(hass, call)
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TOU_SCHEDULE,
        handle_set_tou_schedule
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_set_tou_schedule(hass: HomeAssistant, call):
    """
    Service per settare gli orari di tariffazione (TOU - Time of Use).
    
    Parametri:
    - entry_id: ID dell'entry (opzionale, usa il primo se non specificato)
    - peak_times: Lista di orari di picco [[8, 13], [20, 23]]
    - mid_peak_times: Lista di orari semi-picco (opzionale)
    - off_peak_times: Lista di orari fuori picco (opzionale)
    - daylight_peak_times: Orari luce di picco (opzionale)
    - daylight_mid_peak_times: Orari luce semi-picco (opzionale)
    - daylight_off_peak_times: Orari luce fuori picco (opzionale)
    - active_week: Giorni lavorativi [1-7] (opzionale, default [1,2,3,4,5])
    - active_week_non_workday: Giorni non lavorativi (opzionale, default [6,7])
    - switch_to_mode: Passare automaticamente a modalità "Tariffazione" (opzionale, default false)
    """
    
    # Estrai parametri
    entry_id = call.data.get("entry_id")
    peak_times = call.data.get("peak_times", [])
    mid_peak_times = call.data.get("mid_peak_times", [])
    off_peak_times = call.data.get("off_peak_times", [])
    daylight_peak_times = call.data.get("daylight_peak_times", [])
    daylight_mid_peak_times = call.data.get("daylight_mid_peak_times", [])
    daylight_off_peak_times = call.data.get("daylight_off_peak_times", [])
    active_week = call.data.get("active_week", [1, 2, 3, 4, 5])
    active_week_non_workday = call.data.get("active_week_non_workday", [6, 7])
    switch_to_mode = call.data.get("switch_to_mode", False)
    
    # Se entry_id non specificato, usa il primo
    if not entry_id:
        if DOMAIN not in hass.data or not hass.data[DOMAIN]:
            _LOGGER.error("Nessuna entry epcube trovata")
            return
        entry_id = next(iter(hass.data[DOMAIN].keys()))
    
    if entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.error("Entry %s non trovata", entry_id)
        return
    
    coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
    config_entry = hass.data[DOMAIN][entry_id]["config_entry"]
    region = config_entry.data.get("region", "EU")
    token = config_entry.data.get("token")
    
    if not coordinator.data or "data" not in coordinator.data:
        _LOGGER.error("Dati coordinator non disponibili")
        return
    
    dev_id = coordinator.data["data"].get("devid")
    if not dev_id:
        _LOGGER.error("Device ID non trovato")
        return
    
    # Prepara il payload
    payload = {
        "devId": dev_id,
        "workStatus": "2",  # Tariffazione
        "weatherWatch": "0",
        "onlySave": "0",
        "peakTimeList": peak_times,
        "midPeakTimeList": mid_peak_times,
        "offPeakTimeList": off_peak_times,
        "dayLightPeakTimeList": daylight_peak_times,
        "dayLightMidPeakTimeList": daylight_mid_peak_times,
        "dayLightOffPeakTimeList": daylight_off_peak_times,
        "activeWeek": active_week,
        "activeWeekNonWorkDay": active_week_non_workday,
        "dayLightSavingTime": call.data.get("daylight_saving_time", False),
        "evChargerReserveSoc": call.data.get("ev_charger_reserve_soc", 50),
    }
    
    _LOGGER.info("Invio configurazione TOU al dispositivo: %s", payload)
    
    base_url = get_base_url(region)
    url = f"{base_url}/device/switchMode"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": token,
        "user-agent": USER_AGENT,
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
    }
    
    timeout = aiohttp.ClientTimeout(
        total=HTTP_TIMEOUT,
        connect=HTTP_CONNECT_TIMEOUT
    )
    
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    text = await resp.text()
                    
                    if resp.status == 200:
                        _LOGGER.info("Configurazione TOU impostata correttamente. Risposta: %s", text)
                        await coordinator.async_request_refresh()
                        return
                    elif resp.status == 401:
                        _LOGGER.error("Token non valido o scaduto (401)")
                        return
                    elif resp.status == 403:
                        _LOGGER.error("Accesso negato (403)")
                        return
                    elif resp.status == 429:
                        _LOGGER.warning("Rate limit al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_DELAY * 2)
                            continue
                        else:
                            _LOGGER.error("Rate limit persistente")
                            return
                    elif resp.status >= 500:
                        _LOGGER.warning("Errore server %s al tentativo %d/%d", resp.status, attempt + 1, MAX_RETRIES)
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_DELAY)
                            continue
                        else:
                            _LOGGER.error("Errore server persistente")
                            return
                    else:
                        _LOGGER.error("Errore HTTP %s: %s", resp.status, text)
                        return
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout al tentativo %d/%d", attempt + 1, MAX_RETRIES)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                _LOGGER.error("Timeout persistente")
                return
        except aiohttp.ClientError as e:
            _LOGGER.warning("Errore connessione al tentativo %d/%d: %s", attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                _LOGGER.error("Errore connessione persistente")
                return
        except Exception as e:
            _LOGGER.exception("Errore inaspettato: %s", e)
            return
