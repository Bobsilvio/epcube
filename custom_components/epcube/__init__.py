from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError, ServiceValidationError
from .const import (
    DOMAIN, PLATFORMS, DEFAULT_SCAN_INTERVAL, get_base_url, USER_AGENT,
)
from .sensor import async_update_data_with_stats, EpCubeAuthError
from .state import EpCubeDataState
from .entity import async_migrate_entry_identifiers
from .api import async_post_switch_mode, entry_token
from .payload import build_switch_mode_payload
from .entity import tou_slots_supported
from .auth import async_refresh_token, has_credentials, InvalidCredentials
from .wallbox import async_check_wallbox_support
from .override import OverrideManager, CHARGE, DISCHARGE, HOLD
from .tou import normalize_tou_list
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from datetime import timedelta, datetime
import logging

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TOU_SCHEDULE = "set_tou_schedule"
SERVICE_SET_OPERATING_MODE = "set_operating_mode"
SERVICE_CHECK_WALLBOX_SUPPORT = "check_wallbox_support"
SERVICE_FORCE_CHARGE = "force_charge"
SERVICE_FORCE_DISCHARGE = "force_discharge"
SERVICE_HOLD_BATTERY = "hold_battery"
SERVICE_CLEAR_BATTERY_OVERRIDE = "clear_battery_override"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    sn = entry.data["sn"]
    region = entry.options.get("region") or entry.data.get("region", "EU")
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    base_url = get_base_url(region)

    state = EpCubeDataState()

    async def async_fetch():
        # Token letto a ogni giro: può essere stato rinnovato nel frattempo
        token = entry_token(entry)
        headers = {
            "accept": "*/*",
            "accept-language": "it-IT",
            "accept-encoding": "gzip, deflate, br",
            "user-agent": USER_AGENT,
            "authorization": token
        }
        today_str = datetime.now().strftime("%Y-%m-%d")
        url = f"{base_url}/device/homeDeviceInfo?dayMonthYearFormat={today_str}&sgSn={sn}"
        return await async_update_data_with_stats(session, url, headers, sn, token, hass=hass, entry_id=entry.entry_id)

    async def async_update_data():
        try:
            return await async_fetch()
        except EpCubeAuthError as err:
            if not has_credentials(entry):
                # Solo token: serve un nuovo token o le credenziali (reauth)
                raise ConfigEntryAuthFailed(str(err)) from err
            try:
                new_token = await async_refresh_token(hass, entry)
            except InvalidCredentials as login_err:
                raise ConfigEntryAuthFailed(f"Credenziali rifiutate: {login_err}") from login_err
            if not new_token:
                raise UpdateFailed(f"{err} (rinnovo del token non riuscito, riprovo più tardi)") from err
        try:
            return await async_fetch()
        except EpCubeAuthError as err:
            raise ConfigEntryAuthFailed(f"Token rifiutato anche dopo un nuovo login: {err}") from err

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

    override = OverrideManager(hass, entry, coordinator)
    hass.data[DOMAIN][entry.entry_id]["override"] = override
    await override.async_load()

    # unique_id e device per-impianto: migra le installazioni pre-1.6.0 prima
    # di creare le entità, così entity_id e storico restano invariati (#25)
    async_migrate_entry_identifiers(hass, entry)

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

    # Verifica se il firmware del gateway implementa davvero la funzione wallbox
    async def handle_check_wallbox_support(call) -> ServiceResponse:
        return await async_check_wallbox(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_WALLBOX_SUPPORT,
        handle_check_wallbox_support,
        supports_response=SupportsResponse.ONLY,
    )

    # Override temporanei della batteria (riserva di Autoconsumo)
    async def handle_force_charge(call):
        await _override(hass, call).async_start(
            CHARGE, target_soc=_target_soc(call), duration=_duration(call)
        )

    async def handle_force_discharge(call):
        await _override(hass, call).async_start(
            DISCHARGE, target_soc=_target_soc(call), duration=_duration(call)
        )

    async def handle_hold_battery(call):
        await _override(hass, call).async_start(HOLD, duration=_duration(call))

    async def handle_clear_battery_override(call):
        await _override(hass, call).async_clear()

    for name, handler in (
        (SERVICE_FORCE_CHARGE, handle_force_charge),
        (SERVICE_FORCE_DISCHARGE, handle_force_discharge),
        (SERVICE_HOLD_BATTERY, handle_hold_battery),
        (SERVICE_CLEAR_BATTERY_OVERRIDE, handle_clear_battery_override),
    ):
        hass.services.async_register(DOMAIN, name, handler)

    return True


def _override(hass, call):
    _get_entry_coordinator(hass, call.data.get("entry_id"))
    entry_id = call.data.get("entry_id") or next(iter(hass.data[DOMAIN]))
    return hass.data[DOMAIN][entry_id]["override"]


def _target_soc(call):
    try:
        soc = int(call.data["target_soc"])
    except (KeyError, TypeError, ValueError) as err:
        raise ServiceValidationError("target_soc deve essere un numero tra 0 e 100") from err
    if not 0 <= soc <= 100:
        raise ServiceValidationError("target_soc deve essere tra 0 e 100")
    return soc


def _duration(call):
    """Durata in minuti; assente = finché non si chiama clear_battery_override."""
    minutes = call.data.get("duration")
    if minutes in (None, "", 0):
        return None
    try:
        minutes = float(minutes)
    except (TypeError, ValueError) as err:
        raise ServiceValidationError("duration è in minuti") from err
    if minutes <= 0:
        raise ServiceValidationError("duration deve essere positiva")
    return timedelta(minutes=minutes)


async def async_check_wallbox(hass: HomeAssistant, call) -> ServiceResponse:
    """Scrive un registro della wallbox e lo rilegge, per vedere se resta."""
    coordinator, entry = _get_entry_coordinator(hass, call.data.get("entry_id"))
    dev_id = coordinator.data["data"]["devid"]
    region = entry.options.get("region") or entry.data.get("region", "EU")
    return await async_check_wallbox_support(
        async_get_clientsession(hass),
        entry_token(entry),
        region,
        str(dev_id),
        solo_lettura=call.data.get("read_only", False),
    )

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        override = hass.data[DOMAIN][entry.entry_id].get("override")
        if override:
            override.async_unload()
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
    - self_consumption_reserve_soc: SoC riserva autoconsumo % (opzionale, default: valore attuale)
    - allow_charging_from_grid: Permetti ricarica da rete 0/1 (opzionale, default: valore attuale)
    - daylight_saving_time: Ora legale true/false (opzionale, default false)
    - switch_to_mode: Passare a modalità Tariffazione (opzionale, default false)
    """

    coordinator, config_entry = _get_entry_coordinator(hass, call.data.get("entry_id"))
    data = coordinator.data["data"]

    if not tou_slots_supported(coordinator, config_entry):
        raise ServiceValidationError(
            "Il firmware di questo EP Cube usa i piani TOU stagionali dell'app "
            "(firmware 4.0.8 o successivo): le fasce orarie di set_tou_schedule "
            "non vengono usate. Configura la tariffazione dall'app EP Cube."
        )

    # Le liste non passate vengono svuotate: il servizio imposta l'intero piano
    lists = {
        api_key: normalize_tou_list(param, call.data.get(param, []))
        for param, api_key in TOU_LIST_PARAMS.items()
    }

    overrides = {
        **lists,
        "activeWeek": [str(d) for d in call.data.get("active_week", [1, 2, 3, 4, 5])],
        "activeWeekNonWorkDay": [str(d) for d in call.data.get("active_week_non_workday", [6, 7])],
        "dayLightActiveWeek": [str(d) for d in call.data.get("daylight_active_week", [1, 2, 3, 4, 5])],
        "dayLightActiveWeekNonWorkDay": [
            str(d) for d in call.data.get("daylight_active_week_non_workday", [6, 7])
        ],
        "dayLightSavingTime": call.data.get("daylight_saving_time", False),
    }
    # Parametri facoltativi: se assenti restano i valori attuali del dispositivo.
    # Passando alla Tariffazione a fasce l'app imposta touType "0"
    # ("1" è la tariffa dinamica)
    if "tou_type" in call.data:
        overrides["touType"] = call.data["tou_type"]
    elif call.data.get("switch_to_mode", False):
        overrides["touType"] = "0"
    if "self_consumption_reserve_soc" in call.data:
        overrides["selfConsumptioinReserveSoc"] = str(call.data["self_consumption_reserve_soc"])
    if call.data.get("allow_charging_from_grid") is not None:
        overrides["allowChargingXiaGrid"] = str(call.data["allow_charging_from_grid"])

    # switch_to_mode False: salva le fasce senza cambiare modalità (onlySave=1)
    payload = build_switch_mode_payload(
        data,
        work_status="2",
        only_save="0" if call.data.get("switch_to_mode", False) else "1",
        current=coordinator.data.get("switch_mode"),
        **overrides,
    )

    _LOGGER.info("Invio configurazione TOU al dispositivo: %s", payload)
    if not await async_post_switch_mode(hass, config_entry, payload, "configurazione TOU"):
        raise HomeAssistantError("Il server EP Cube ha rifiutato la configurazione TOU (vedi log)")
    await coordinator.async_request_refresh()


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
    mode = str(call.data.get("mode", "1"))
    if mode not in ("1", "3"):
        raise ServiceValidationError(
            f"Modalità non valida: '{mode}'. Valori accettati: '1' (Autoconsumo), "
            "'3' (Backup). Per la Tariffazione usare il servizio set_tou_schedule."
        )

    coordinator, config_entry = _get_entry_coordinator(hass, call.data.get("entry_id"))
    data = coordinator.data["data"]

    # Come l'app: fuori dalla tariffa dinamica touType è "0"
    overrides = {"touType": "0"}
    if mode == "3" and "backup_power_reserve_soc" in call.data:
        overrides["backupPowerReserveSoc"] = str(call.data["backup_power_reserve_soc"])
    if mode == "1" and "self_consumption_reserve_soc" in call.data:
        overrides["selfConsumptioinReserveSoc"] = str(call.data["self_consumption_reserve_soc"])

    # Payload completo: fasce TOU e l'altra riserva restano invariate (#18, #31)
    payload = build_switch_mode_payload(
        data, work_status=mode, current=coordinator.data.get("switch_mode"), **overrides,
    )
    if not await async_post_switch_mode(hass, config_entry, payload, f"modalità {mode}"):
        raise HomeAssistantError("Il server EP Cube ha rifiutato il cambio di modalità (vedi log)")
    await coordinator.async_request_refresh()


def _get_entry_coordinator(hass, entry_id):
    """Coordinator e config entry del servizio (la prima entry se non indicata)."""
    entries = hass.data.get(DOMAIN, {})
    if not entry_id:
        if not entries:
            raise ServiceValidationError("Nessun EP Cube configurato")
        entry_id = next(iter(entries))
    if entry_id not in entries:
        raise ServiceValidationError(f"EP Cube {entry_id} non trovato")
    coordinator = entries[entry_id]["coordinator"]
    if not coordinator.data or not coordinator.data.get("data", {}).get("devid"):
        raise HomeAssistantError("Dati EP Cube non ancora disponibili, riprova tra poco")
    return coordinator, entries[entry_id]["config_entry"]


# Parametri del servizio set_tou_schedule -> campi di switchMode
TOU_LIST_PARAMS = {
    "peak_times": "peakTimeList",
    "mid_peak_times": "midPeakTimeList",
    "off_peak_times": "offPeakTimeList",
    "peak_times_non_workday": "peakTimeListNonWorkDay",
    "mid_peak_times_non_workday": "midPeakTimeListNonWorkDay",
    "off_peak_times_non_workday": "offPeakTimeListNonWorkDay",
    "daylight_peak_times": "dayLightPeakTimeList",
    "daylight_mid_peak_times": "dayLightMidPeakTimeList",
    "daylight_off_peak_times": "dayLightOffPeakTimeList",
}
