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
from datetime import timedelta, datetime
import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TOU_SCHEDULE = "set_tou_schedule"
SERVICE_SET_OPERATING_MODE = "set_operating_mode"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    token = entry.options.get("token") or entry.data["token"]
    sn = entry.data["sn"]
    region = entry.options.get("region") or entry.data.get("region", "EU")
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    base_url = get_base_url(region)
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    state = EpCubeDataState()

    async def async_update_data():
        today_str = datetime.now().strftime("%Y-%m-%d")
        url = f"{base_url}/device/homeDeviceInfo?dayMonthYearFormat={today_str}&sgSn={sn}"
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

    # Registra il service per cambio modalità operativa
    async def handle_set_operating_mode(call):
        await async_set_operating_mode(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_OPERATING_MODE,
        handle_set_operating_mode
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
    - peak_times: Lista orari picco, formato ["HH:MM_HH:MM_prezzo"] (es. ["08:00_12:00_0.31"])
    - mid_peak_times: Lista orari semi-picco, stesso formato (opzionale)
    - off_peak_times: Lista orari fuori picco, stesso formato (opzionale)
    - peak_times_non_workday: Orari picco giorni non lavorativi (opzionale)
    - mid_peak_times_non_workday: Orari semi-picco giorni non lavorativi (opzionale)
    - off_peak_times_non_workday: Orari fuori picco giorni non lavorativi (opzionale)
    - daylight_peak_times: Orari luce picco (opzionale)
    - daylight_mid_peak_times: Orari luce semi-picco (opzionale)
    - daylight_off_peak_times: Orari luce fuori picco (opzionale)
    - active_week: Giorni lavorativi [1-7] (opzionale, default [1,2,3,4,5])
    - active_week_non_workday: Giorni non lavorativi (opzionale, default [6,7])
    - daylight_active_week: Giorni luce lavorativi (opzionale, default [1,2,3,4,5])
    - daylight_active_week_non_workday: Giorni luce non lavorativi (opzionale, default [6,7])
    - tou_type: Tipo tariffazione (opzionale, default 0)
    - self_consumption_reserve_soc: SoC riserva autoconsumo % (opzionale, default 5)
    - allow_charging_from_grid: Permetti ricarica da rete 0/1 (opzionale, default 0)
    - daylight_saving_time: Ora legale true/false (opzionale, default false)
    - switch_to_mode: Passare a modalità Tariffazione (opzionale, default false)
    """
    
    def _validate_time_list(name, entries):
        """Valida che ogni entry abbia inizio E fine nel formato HH:MM_HH:MM[_prezzo]."""
        for entry in entries:
            parts = str(entry).split("_")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                _LOGGER.error(
                    "Formato orario TOU non valido in '%s': '%s'. "
                    "Formato richiesto: 'HH:MM_HH:MM_prezzo' (es. '08:00_12:00_0.31')",
                    name, entry
                )
                return False
        return True

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

    # Valida tutti i time list non vuoti
    time_lists_to_validate = [
        ("peak_times", peak_times),
        ("mid_peak_times", mid_peak_times),
        ("off_peak_times", off_peak_times),
        ("peak_times_non_workday", call.data.get("peak_times_non_workday", [])),
        ("mid_peak_times_non_workday", call.data.get("mid_peak_times_non_workday", [])),
        ("off_peak_times_non_workday", call.data.get("off_peak_times_non_workday", [])),
        ("daylight_peak_times", daylight_peak_times),
        ("daylight_mid_peak_times", daylight_mid_peak_times),
        ("daylight_off_peak_times", daylight_off_peak_times),
    ]
    for list_name, entries in time_lists_to_validate:
        if entries and not _validate_time_list(list_name, entries):
            return
    
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
    
    # Se switch_to_mode è False, usa onlySave="1" per salvare senza cambiare modalità
    only_save = "0" if switch_to_mode else "1"

    # activeWeek deve essere array di stringhe (es. ["1","2","3","4","5"])
    active_week_str = [str(d) for d in active_week]
    active_week_non_workday_str = [str(d) for d in active_week_non_workday]

    # Prepara il payload
    # Formato orari TOU: lista di stringhe "HH:MM_HH:MM_prezzo" (es. "08:00_12:00_0.31")
    payload = {
        "devId": dev_id,
        "workStatus": "2",  # Tariffazione
        "weatherWatch": "0",
        "onlySave": only_save,
        "touType": call.data.get("tou_type", 0),
        "peakTimeList": peak_times,
        "midPeakTimeList": mid_peak_times,
        "offPeakTimeList": off_peak_times,
        "peakTimeListNonWorkDay": call.data.get("peak_times_non_workday", []),
        "midPeakTimeListNonWorkDay": call.data.get("mid_peak_times_non_workday", []),
        "offPeakTimeListNonWorkDay": call.data.get("off_peak_times_non_workday", []),
        "dayLightPeakTimeList": daylight_peak_times,
        "dayLightMidPeakTimeList": daylight_mid_peak_times,
        "dayLightOffPeakTimeList": daylight_off_peak_times,
        "activeWeek": active_week_str,
        "activeWeekNonWorkDay": active_week_non_workday_str,
        "dayLightActiveWeek": call.data.get("daylight_active_week", [1, 2, 3, 4, 5]),
        "dayLightActiveWeekNonWorkDay": call.data.get("daylight_active_week_non_workday", [6, 7]),
        "dayLightSavingTime": call.data.get("daylight_saving_time", False),
        "selfConsumptioinReserveSoc": str(call.data.get("self_consumption_reserve_soc", 5)),
        "allowChargingXiaGrid": str(call.data.get("allow_charging_from_grid", 0)),
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


async def async_set_operating_mode(hass: HomeAssistant, call):
    """
    Service per cambiare la modalità operativa del dispositivo.

    Parametri:
    - entry_id: ID dell'entry (opzionale, usa il primo se non specificato)
    - mode: modalità operativa — "1" = Autoconsumo, "3" = Backup
            Per TOU usare il service set_tou_schedule
    - backup_power_reserve_soc: SoC riserva backup % (usato solo in modalità Backup, default 50)
    - self_consumption_reserve_soc: SoC riserva autoconsumo % (usato solo in modalità Autoconsumo, default 5)
    """
    entry_id = call.data.get("entry_id")
    mode = str(call.data.get("mode", "1"))

    if mode not in ("1", "3"):
        _LOGGER.error(
            "Modalità non valida: '%s'. Valori accettati: '1' (Autoconsumo), '3' (Backup). "
            "Per TOU usare il service set_tou_schedule.",
            mode
        )
        return

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

    # Costruisci il payload in base alla modalità
    if mode == "3":
        soc_value = str(call.data.get("backup_power_reserve_soc", 50))
        payload = {
            "devId": dev_id,
            "workStatus": "3",
            "weatherWatch": "0",
            "onlySave": "0",
            "backupPowerReserveSoc": soc_value,
        }
        _LOGGER.info("Attivazione modalità Backup con SoC riserva %s%%", soc_value)
    else:  # mode == "1"
        soc_value = str(call.data.get("self_consumption_reserve_soc", 5))
        payload = {
            "devId": dev_id,
            "workStatus": "1",
            "weatherWatch": "0",
            "onlySave": "0",
            "selfConsumptioinReserveSoc": soc_value,
        }
        _LOGGER.info("Attivazione modalità Autoconsumo con SoC riserva %s%%", soc_value)

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

    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        _LOGGER.info("Modalità impostata correttamente. Risposta: %s", text)
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
                        _LOGGER.error("Rate limit persistente")
                        return
                    elif resp.status >= 500:
                        _LOGGER.warning("Errore server %s al tentativo %d/%d", resp.status, attempt + 1, MAX_RETRIES)
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_DELAY)
                            continue
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
            _LOGGER.error("Timeout persistente")
            return
        except aiohttp.ClientError as e:
            _LOGGER.warning("Errore connessione al tentativo %d/%d: %s", attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            _LOGGER.error("Errore connessione persistente")
            return
        except Exception as e:
            _LOGGER.exception("Errore inaspettato: %s", e)
            return
