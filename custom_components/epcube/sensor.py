from homeassistant.const import (
    UnitOfEnergy, UnitOfPower, UnitOfTime, PERCENTAGE,
    UnitOfElectricCurrent, UnitOfElectricPotential,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntityDescription, SensorEntity
from homeassistant.helpers.entity import EntityCategory, Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity
from homeassistant.helpers.entity_registry import async_get, RegistryEntryDisabler
from homeassistant.helpers.restore_state import RestoreEntity

from .state import EpCubeDataState
from .entity import bind_entities_to_entry, legacy_unique_id
from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_ENABLE_TOTAL, CONF_ENABLE_ANNUAL, 
    CONF_ENABLE_MONTHLY, get_base_url, USER_AGENT, HTTP_TIMEOUT, 
    HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY, STATS_TIMEOUT,
    BATTERY_POWER_DEADBAND_KW, BATTERY_STATUS_IDLE_KW
)
from .translations import translate_field_name, translate_status_value, SYSTEM_STATUS_OPTIONS
from .extras import (
    async_fetch_settings, async_fetch_slow_extras, async_fetch_pv_power,
    async_fetch_battery_series,
)
import aiohttp
import asyncio
import json
from datetime import timedelta, datetime, date

import logging
_LOGGER = logging.getLogger(__name__)

# Lunghezza massima di uno stato in Home Assistant
MAX_STATE_LENGTH = 255


def _is_numeric(value):
    """True se il valore è convertibile in float (anche se arriva come stringa)."""
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def generate_sensors(data, enable_total=False, enable_annual=False, enable_monthly=False):
    """Genera i sensori per i dati ricevuti."""
    sensors = []

    suffix_map = {
        "_total": "Totale",
        "_annual": "Annuale",
        "_monthly": "Mensile"
    }

    disabled_by_variant = {
        "batterysoc": ["annual", "monthly", "total"],
        "solarflow": ["annual", "monthly", "total"],
        "solarpower": ["annual", "monthly", "total"],
        "backuppower": ["annual", "monthly", "total"],
        "backupflowpower": ["annual", "monthly", "total"],
        "gridhalfpower": ["annual", "monthly", "total"],
        "gridtotalpower": ["annual", "monthly", "total"],
        "gridpower": ["annual", "monthly", "total"],
        "solardcelectricity": ["annual", "monthly", "total"],
        "solaracelectricity": ["annual", "monthly", "total"],
    }
    diagnostic_sensors = [
        "status", "systemstatus", "workstatus", "isalert", "isfault",
        "backuploadsmode", "backuptype", "deftimezone", "devid",
        "faultwarningtype", "fromtimezone", "fromtype", "generatorlight",
        "gridlight", "isnewdevice", "off_on_grid_hint", "payloadversion",
        "ressnumber", "version", "evlight", "defcreatetime", "fromcreatetime",
        "gridpowerfailurenum", "activationdata", "warrantydata", "modeltype",
        "allowchargingxiagrid", "daylightsavingtime", "offgridpowersupplytime",
        "onlysave", "selfhelprate",
        # Sensori di 'tempo di utilizzo'
        "activeweek", "activeweeknonworkday",
        "daylightactiveweek", "daylightactiveweeknonworkday", "daytype",
        "isdaylightsaving", "weatherwatch",
        "treenum", "coal",
        # Metadati valuta
        "unitdefault", "unitsmallest", "unitmulti",
        # Tipo tariffazione e modalità speciali
        "toutype", "systemspecialworkmode",
        # Dispositivo
        "devtype", "batterypacknum", "heatpumpsettingspermission", "homeconnectauth",
        # Dati da deviceList
        "devicesystemtype", "systemcapacity", "batterytype",
        "lastconnecttime", "lat", "lon", "addressinfo",
        "isparallel", "hybridnum", "dynamicpriceauth",
        "softwareversion",
        # Info dispositivo statiche (spec, connettività, identificatori)
        "batterycapacity", "signallevel", "isonline", "networking",
        "existssg", "snitems", "rtusn",
        # Valori economici (non dati energetici)
        "earningyesterday", "hasvalue",
        # Configurazione e programmi (getSwitchMode / homeDeviceInfo)
        "hasev", "hasgenerator", "newapptou", "vppcode", "exporteverything",
        "sellingenable", "backupaftermode", "backupdurationhour",
        "backupdurationminute", "backupendtime",
        "ja122025enabled", "ja122025enabledsoc", "ja12effectivedate",
        # Id del record lato cloud e strutture della nuova app (filtri VPP, fasce)
        "id", "filters", "toucurrenttimes", "tousettings",
        # Campi del backend EU non usati dall'app Android
        "chargingpowerfromgridlimit", "pvtopowertogridlimits", "drycontactinputdevicetype",
        "eebuspromptmsg", "enwgeegenable", "heatpumpsettingstip", "heatpumpworkmode",
        "homeconnectdevices", "dynamicprice",
        "gridstandard", "lpptimeduration", "lpctimeduration", "wintermode",
        "winterprotect", "charginglimitsoc", "hasevse", "evseonline",
        "dynamicpricetips",
    ]

    config_sensors = [
        # Orari TOU — giorni lavorativi
        "peaktimelist", "midpeaktimelist", "offpeaktimelist",
        # Orari TOU — giorni festivi/weekend
        "peaktimelistnonworkday", "midpeaktimelistnonworkday", "offpeaktimelistnonworkday",
        # Orari TOU — ora legale
        "daylightpeaktimelist", "daylightmidpeaktimelist", "daylightoffpeaktimelist",
        "daylightpeaktimelistnonworkday", "daylightmidpeaktimelistnonworkday", "daylightoffpeaktimelistnonworkday",
    ]

    disabled_by_default = [
        "defcreatetime", "fromcreatetime",
        "allowchargingxiagrid", "daylightsavingtime", "offgridpowersupplytime",
        "onlysave",
        # Disabilito i sensori 'tempo di utilizzo'
        "activeweek", "activeweeknonworkday",
        "daylightactiveweek", "daylightactiveweeknonworkday", "daytype",
        "isdaylightsaving", "weatherwatch", "treenum", "coal",
        # Sensori con valori uguali ad altri o ridondanti
        "gridhalfpower", "solarflow", "backupflowpower",
        "generatorpower", "generatorflowpower",  # alias di solarpower per questo modello
        # Metadati valuta (non utili come sensori)
        "unitdefault", "unitsmallest", "unitmulti",
        # Diagnostici meno utili
        "toutype", "systemspecialworkmode", "devtype",
        "heatpumpsettingspermission", "homeconnectauth",
        # Flag interni dell'app e funzioni solo per la California (JA12/Title 24)
        "id", "filters", "toucurrenttimes", "tousettings",
        "hasev", "hasgenerator", "newapptou", "dynamicpricetips",
        "lpptimeduration", "lpctimeduration",
        "ja122025enabled", "ja122025enabledsoc", "ja12effectivedate",
        # Dati da deviceList — disabilitati di default (info statiche o private)
        "lat", "lon", "addressinfo",
        "isparallel", "hybridnum", "dynamicpriceauth",
        "softwareversion",
    ]

    diagnostic_sensors = [s.lower() for s in diagnostic_sensors]
    config_sensors = [s.lower() for s in config_sensors]
    disabled_by_default = [s.lower() for s in disabled_by_default]

    disabled_by_variant = {
        k.lower(): [v.lower() for v in vals]
        for k, vals in disabled_by_variant.items()
    }

    for key, value in data.items():
        key_lower = key.lower()
        entity_category = None
        options = None

        # I campi *_yesterday alimentano i sensori dedicati EpCubeYesterday*Sensor:
        # non generare duplicati auto-nominati male
        if key_lower.endswith("_yesterday"):
            continue

        suffix_label = ""
        base_key = key_lower
        for suffix, label in suffix_map.items():
            if key_lower.endswith(suffix):
                base_key = key_lower.removesuffix(suffix)
                suffix_label = suffix[1:]
                break

        if suffix_label in disabled_by_variant.get(base_key, []):
            continue

        if base_key in config_sensors:
            entity_category = EntityCategory.DIAGNOSTIC
        elif base_key in diagnostic_sensors:
            entity_category = EntityCategory.DIAGNOSTIC

        #ectricity = kWh
        #power = kW (none)
        #power (i numeri arrivano in watt) = W
        
        # Valori testuali (orari TOU tipo "23:00_07:00_", hint, liste): mai
        # device_class/state_class numerici. Il nome di alcuni di questi campi
        # contiene "electricity" (lowElectricityPriceTime) e finirebbe fra i
        # sensori di energia: HA solleva ValueError nel push agli entity e
        # l'eccezione blocca l'aggiornamento di TUTTI i sensori (issue #26)
        if (isinstance(value, str) and not _is_numeric(value)) or isinstance(value, (list, dict)):
            device_class = None
            unit_of_measurement = None
            state_class = None
            if entity_category is None:
                entity_category = EntityCategory.DIAGNOSTIC

        elif "electricity" in base_key:
            unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            device_class = SensorDeviceClass.ENERGY
            # _annual/_monthly/_total si azzerano periodicamente o dopo reset HW:
            # usare TOTAL (gestisce decrementi come reset) invece di TOTAL_INCREASING
            if suffix_label in ("annual", "monthly", "total"):
                state_class = SensorStateClass.TOTAL
            else:
                state_class = SensorStateClass.TOTAL_INCREASING

            if 'battery' in base_key:
                device_class = None
                state_class = SensorStateClass.MEASUREMENT

            
        elif ("flow" in base_key or "power" in base_key) and base_key not in (
            "gridpowerfailurenum", "offgridpowersupplytime",
            "backuppowerreservesoc",
            # Limiti impostati dall'installatore (app EU): unità non verificata
            "chargingpowerfromgridlimit", "pvtopowertogridlimits",
        ):
            device_class = SensorDeviceClass.POWER
            unit_of_measurement = UnitOfPower.WATT
            state_class = SensorStateClass.MEASUREMENT

        # Autonomia residua in blackout: l'app la mostra come ore:minuti
        elif base_key == "timeleft":
            device_class = SensorDeviceClass.DURATION
            unit_of_measurement = UnitOfTime.MINUTES
            state_class = SensorStateClass.MEASUREMENT

        # systemStatus = stato del gateway (0-7), esposto come enum tradotto
        elif base_key == "systemstatus" and not suffix_label:
            device_class = SensorDeviceClass.ENUM
            unit_of_measurement = None
            state_class = None
            options = list(SYSTEM_STATUS_OPTIONS.values())

        elif "soc" in base_key:
            unit_of_measurement = PERCENTAGE
            state_class = SensorStateClass.MEASUREMENT

            if base_key == "batterysoc":
                device_class = SensorDeviceClass.BATTERY
                entity_category = None
            elif base_key in ("backuppowerreservesoc", "selfconsumptioinreservesoc", "evchargerreservesoc"):
                device_class = None
                entity_category = EntityCategory.DIAGNOSTIC
            else:
                device_class = None
                entity_category = EntityCategory.DIAGNOSTIC

        else:
            device_class = None
            unit_of_measurement = None
            state_class = None

        # Nei contesti statistici (_total/_annual/_monthly) i campi "power"/"flow"
        # sono sempre 0 (placeholder vuoti dell'API) — non creare sensori inutili
        if device_class == SensorDeviceClass.POWER and suffix_label in ("total", "annual", "monthly"):
            continue

        if base_key == "batterysoc":
            entity_registry_enabled_default = True

        elif key_lower.endswith("_annual"):
            entity_registry_enabled_default = enable_annual
        elif key_lower.endswith("_monthly"):
            entity_registry_enabled_default = enable_monthly
        elif key_lower.endswith("_total"):
            entity_registry_enabled_default = enable_total

        elif value is None:
            entity_registry_enabled_default = False
        elif base_key in disabled_by_default:
            entity_registry_enabled_default = False
        else:
            entity_registry_enabled_default = True

        translation_key = f"{base_key}_{suffix_label}" if suffix_label else base_key
        translated_name = translate_field_name(key)
        
        sensor = SensorEntityDescription(
            key=key,
            name=translated_name,
            translation_key=translation_key,
            native_unit_of_measurement=unit_of_measurement,
            device_class=device_class,
            entity_category=entity_category,
            state_class=state_class,
            options=options,
            entity_registry_enabled_default=entity_registry_enabled_default
        )

        sensors.append(sensor)

    return sensors

async def fetch_device_info(session, token, dev_id, region, timeout=STATS_TIMEOUT):
    base_url = get_base_url(region)
    url = f"{base_url}/device/userDeviceInfo?devId={dev_id}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    raw_data = json_data.get("data", {})
                    normalized = {k.lower(): v for k, v in raw_data.items()}
                    return normalized
                elif resp.status == 401:
                    _LOGGER.error("Token non valido o scaduto nel fetch device info (401)")
                    return {}
                elif resp.status >= 500:
                    _LOGGER.warning("Errore server %s nel fetch device info", resp.status)
                    return {}
                else:
                    _LOGGER.error("Errore HTTP %s nel fetch device info", resp.status)
                    return {}
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout nel fetch device info")
        return {}
    except aiohttp.ClientError as e:
        _LOGGER.error("Errore connessione nel fetch device info: %s", e)
        return {}
    except Exception as e:
        _LOGGER.exception("Errore inaspettato nel fetch device info: %s", e)
        return {}

async def fetch_device_list(session, token, dev_id, region, timeout=STATS_TIMEOUT):
    """Fetch deviceList e ritorna l'entry corrispondente a dev_id."""
    base_url = get_base_url(region)
    url = f"{base_url}/device/deviceList"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    devices = json_data.get("data", [])
                    for device in devices:
                        if str(device.get("id")) == str(dev_id):
                            return device
                    _LOGGER.warning("Device %s non trovato in deviceList", dev_id)
                    return {}
                elif resp.status == 401:
                    _LOGGER.error("Token non valido nel fetch deviceList (401)")
                    return {}
                elif resp.status >= 500:
                    _LOGGER.warning("Errore server %s nel fetch deviceList", resp.status)
                    return {}
                else:
                    _LOGGER.error("Errore HTTP %s nel fetch deviceList", resp.status)
                    return {}
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout nel fetch deviceList")
        return {}
    except aiohttp.ClientError as e:
        _LOGGER.error("Errore connessione nel fetch deviceList: %s", e)
        return {}
    except Exception as e:
        _LOGGER.exception("Errore inaspettato nel fetch deviceList: %s", e)
        return {}


async def fetch_switch_mode(session, token, dev_id, region, timeout=STATS_TIMEOUT):
    """Fetch getSwitchMode: dati con le chiavi originali (camelCase).

    Le chiavi originali servono a rispedire la configurazione a switchMode;
    il merge nei dati del coordinator le porta in minuscolo.
    """
    base_url = get_base_url(region)
    url = f"{base_url}/device/getSwitchMode?devId={dev_id}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    raw_data = json_data.get("data") or {}
                    return dict(raw_data) if isinstance(raw_data, dict) else {}
                elif resp.status == 401:
                    _LOGGER.error("Token non valido nel fetch switch mode (401)")
                    return {}
                elif resp.status >= 500:
                    _LOGGER.warning("Errore server %s nel fetch switch mode", resp.status)
                    return {}
                else:
                    _LOGGER.error("Errore HTTP %s nel fetch switch mode", resp.status)
                    return {}
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout nel fetch switch mode")
        return {}
    except aiohttp.ClientError as e:
        _LOGGER.warning("Errore connessione nel fetch switch mode: %s", e)
        return {}
    except Exception as e:
        _LOGGER.exception("Errore inaspettato nel fetch switch mode: %s", e)
        return {}


async def fetch_epcube_stats(session, token, dev_id, date_str, scope_type, region, timeout=STATS_TIMEOUT):
    base_url = get_base_url(region)
    url = f"{base_url}/device/queryDataElectricityV2?devId={dev_id}&queryDateStr={date_str}&scopeType={scope_type}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token
    }

    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    raw_data = json_data.get("data", {})
                    normalized = {k.lower(): v for k, v in raw_data.items()}
                    return normalized
                elif resp.status == 401:
                    _LOGGER.error("Token non valido o scaduto nel fetch epcube stats (401)")
                    return {}
                elif resp.status >= 500:
                    _LOGGER.warning("Errore server %s nel fetch epcube stats per %s", resp.status, date_str)
                    return {}
                else:
                    _LOGGER.error("Errore HTTP %s nel fetch epcube stats", resp.status)
                    return {}
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout nel fetch epcube stats per %s", date_str)
        return {}
    except aiohttp.ClientError as e:
        _LOGGER.error("Errore connessione nel fetch epcube stats: %s", e)
        return {}
    except Exception as e:
        _LOGGER.exception("Errore inaspettato nel fetch epcube stats: %s", e)
        return {}

class EpCubeAuthError(UpdateFailed):
    """Il server ha rifiutato il token (scaduto o di un'altra regione)."""


async def async_update_data_with_stats(session, url, headers, dev_id_sn, token, hass, entry_id):
    config_entry = hass.data[DOMAIN][entry_id].get("config_entry")
    region = config_entry.data.get("region", "EU") if config_entry else "EU"
    base_url = get_base_url(region)
    
    try:
        async with asyncio.timeout(HTTP_TIMEOUT):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    raise EpCubeAuthError("Token non valido o scaduto")
                elif resp.status == 403:
                    raise EpCubeAuthError("Accesso negato all'API")
                elif resp.status == 429:
                    raise UpdateFailed("Rate limit raggiunto - riprova più tardi")
                elif resp.status >= 500:
                    raise UpdateFailed(f"Errore server {resp.status}")
                elif resp.status != 200:
                    raise UpdateFailed(f"Errore HTTP {resp.status}")
                
                if resp.content_type != "application/json":
                    raise UpdateFailed(f"Tipo MIME non gestito: {resp.content_type}")

                live_data = await resp.json()

                # I server US/JP restituiscono HTTP 200 con l'errore reale nel corpo
                api_status = live_data.get("status")
                if api_status is not None and int(api_status) != 200:
                    api_message = live_data.get("message", "")
                    if int(api_status) in (401, 403):
                        raise EpCubeAuthError(f"Token non valido o scaduto: {api_message}")
                    raise UpdateFailed(f"Errore API {api_status}: {api_message}")

                full_data_raw = live_data.get("data") or {}
                full_data = {k.lower(): v for k, v in full_data_raw.items()}
                real_dev_id = full_data.get("devid")

                if not real_dev_id:
                    raise UpdateFailed("Device ID non trovato nella risposta")

                now = datetime.now()
                year_str = str(now.year)
                month_str = now.strftime("%Y-%m")
                today_str = now.strftime("%Y-%m-%d")
                yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

                state: EpCubeDataState = hass.data[DOMAIN][entry_id]["state"]
                live_data = {}
                total_data = {}
                annual_data = {}
                monthly_data = {}
                yesterday_data = {}
                device_info = {}
                device_list_info = {}
                switch_mode_data = {}
                settings_data = {}
                pv_data = {}
                extras_data = {}
                # Gli endpoint supplementari sono opzionali: se uno è lento o rotto
                # (es. queryDataElectricityV2 sul cluster JP, issue #27) i dati live
                # di homeDeviceInfo devono comunque arrivare in Home Assistant.
                # Ogni fetch ha il proprio budget STATS_TIMEOUT < HTTP_TIMEOUT.
                try:
                    results = await asyncio.gather(
                        fetch_epcube_stats(session, token, real_dev_id, today_str, 1, region),
                        fetch_epcube_stats(session, token, real_dev_id, year_str, 0, region),
                        fetch_epcube_stats(session, token, real_dev_id, year_str, 3, region),
                        fetch_epcube_stats(session, token, real_dev_id, month_str, 2, region),
                        fetch_epcube_stats(session, token, real_dev_id, yesterday_str, 1, region),
                        fetch_device_info(session, token, real_dev_id, region),
                        fetch_device_list(session, token, real_dev_id, region),
                        fetch_switch_mode(session, token, real_dev_id, region),
                        async_fetch_settings(session, token, region, real_dev_id, state),
                        async_fetch_pv_power(session, token, region, real_dev_id),
                        async_fetch_slow_extras(
                            session, token, region, real_dev_id, dev_id_sn, state,
                        ),
                        async_fetch_battery_series(session, token, region, real_dev_id, state),
                        return_exceptions=True,
                    )
                    labels = (
                        "stats giornaliere", "stats totali", "stats annuali",
                        "stats mensili", "stats ieri", "device info",
                        "deviceList", "switch mode", "impostazioni", "stringhe FV", "extra",
                        "serie batteria",
                    )
                    clean = []
                    for label, result in zip(labels, results):
                        if isinstance(result, BaseException):
                            _LOGGER.warning("Fetch %s fallito: %s", label, result)
                            clean.append({})
                        else:
                            clean.append(result or {})
                    (
                        live_data,
                        total_data,
                        annual_data,
                        monthly_data,
                        yesterday_data,
                        device_info,
                        device_list_info,
                        switch_mode_data,
                        settings_data,
                        pv_data,
                        extras_data,
                        _series,
                    ) = clean
                except Exception as e:
                    _LOGGER.warning("Errore nel fetch dati supplementari: %s", e)

                # Merge switch mode — sovrascrive homeDeviceInfo per SoC e config TOU
                for k, v in switch_mode_data.items():
                    full_data[k.lower()] = v

                # Merge device info (userDeviceInfo)
                for k in ["activationdata", "warrantydata", "modeltype", "batterycapacity"]:
                    if k in device_info:
                        full_data[k] = device_info.get(k)

                # Merge deviceList — campi device fissi
                DEVICE_LIST_KEYS = [
                    "rtusn", "snitems", "softwareversion",
                    "devicesystemtype", "systemcapacity", "batterytype",
                    "lastconnecttime", "lat", "lon", "addressinfo",
                    "isparallel", "hybridnum", "dynamicpriceauth",
                ]
                if device_list_info:
                    normalized_dl = {k.lower(): v for k, v in device_list_info.items()}
                    for k in DEVICE_LIST_KEYS:
                        if k in normalized_dl and normalized_dl[k] is not None:
                            full_data[k] = normalized_dl[k]

                    # workParam: usato come fallback/integrazione per dati TOU/mode
                    # se getSwitchMode ha già popolato i dati, workParam non sovrascrive
                    work_param_str = device_list_info.get("workParam", "")
                    if work_param_str:
                        try:
                            work_param = json.loads(work_param_str)
                            for k, v in work_param.items():
                                key_lower = k.lower()
                                if key_lower not in full_data or full_data[key_lower] is None:
                                    full_data[key_lower] = v
                        except (json.JSONDecodeError, TypeError) as e:
                            _LOGGER.warning("Errore nel parsing workParam: %s", e)

                INCLUDED_LIVE_KEYS = {
                    "gridelectricity", "gridelectricityfrom", "gridelectricityto",
                    "solarelectricity", "backupelectricity", "nonbackupelectricity",
                    "selfhelprate", "treenum", "coal",
                }

                for k, v in live_data.items():
                    key_lower = k.lower()
                    if key_lower in INCLUDED_LIVE_KEYS:
                        full_data[key_lower] = v

                for k, v in total_data.items():
                    full_data[f"{k}_total"] = v
                for k, v in annual_data.items():
                    full_data[f"{k}_annual"] = v
                for k, v in monthly_data.items():
                    full_data[f"{k}_monthly"] = v

                INCLUDED_YESTERDAY_KEYS = {
                    "gridelectricityfrom", "gridelectricityto",
                    "solarelectricity", "backupelectricity", "nonbackupelectricity",
                }
                for k, v in yesterday_data.items():
                    if k.lower() in INCLUDED_YESTERDAY_KEYS:
                        full_data[f"{k.lower()}_yesterday"] = v

                battery_now = full_data.get("batterycurrentelectricity")
                if battery_now is not None:
                    try:
                        state.update(float(battery_now))
                    except Exception as e:
                        _LOGGER.warning("Errore nel calcolo del SOC cumulativo: %s", e)

                # Impostazioni ed extra restano separati da "data": da lì
                # generate_sensors crea un sensore per ogni chiave
                return {
                    "data": full_data, "settings": settings_data,
                    "switch_mode": switch_mode_data,
                    "pv": pv_data, "extras": extras_data,
                }

    except asyncio.TimeoutError:
        raise UpdateFailed("Timeout nella lettura dei dati principali")
    except aiohttp.ClientError as e:
        raise UpdateFailed(f"Errore di connessione: {e}")
    except UpdateFailed:
        raise
    except Exception as err:
        raise UpdateFailed(f"Errore nell'aggiornamento dei dati: {err}")

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    options = entry.options
    enable_total = options.get(CONF_ENABLE_TOTAL, False)
    enable_annual = options.get(CONF_ENABLE_ANNUAL, False)
    enable_monthly = options.get(CONF_ENABLE_MONTHLY, False)

    if not coordinator.data or "data" not in coordinator.data:
        return

    filtered_data = coordinator.data["data"]
    
    sensors = generate_sensors(
        filtered_data,
        enable_total=enable_total,
        enable_annual=enable_annual,
        enable_monthly=enable_monthly
    )

    region = entry.data.get("region", "EU")

    entities = [
        EpCubeSensor(coordinator, sensor, region) for sensor in sensors
    ] + [
        EpCubeLastUpdateSensor(coordinator),
        EpCubeBatteryChargeSensor(coordinator),
        EpCubeBatteryDischargeSensor(coordinator),
        EpCubeBatteryDailyChargeSensor(coordinator),
        EpCubeBatteryDailyDischargeSensor(coordinator),
        EpCubeBatteryPowerSensor(coordinator),
        EpCubeBatteryStatusSensor(coordinator),
        EpCubeTotalLoadPowerSensor(coordinator),
        EpCubeTotalLoadEnergySensor(coordinator),
        # Sensori giorno precedente
        EpCubeYesterdayGridFromSensor(coordinator),
        EpCubeYesterdayGridToSensor(coordinator),
        EpCubeYesterdaySolarSensor(coordinator),
        EpCubeYesterdayLoadSensor(coordinator),
        # Giorni della Tariffazione (le fasce si modificano dalle entità testo)
        EpCubeTouActiveWeeksSensor(coordinator, "workday"),
        EpCubeTouActiveWeeksSensor(coordinator, "non_workday"),
        # Endpoint dell'app Android (extras.py)
        EpCubeLastPowerCutSensor(coordinator),
        EpCubeWeatherSensor(coordinator),
        EpCubeAlertSensor(coordinator, "warnings", "last_warning"),
        EpCubeAlertSensor(coordinator, "faults", "last_fault"),
        EpCubeWifiSensor(coordinator),
        EpCubeFirmwareSensor(coordinator),
        EpCubeAuthoritySensor(coordinator, "kebaAuthority"),
        EpCubeAuthoritySensor(coordinator, "eebusAuthority"),
        EpCubeAuthoritySensor(coordinator, "triphaseAuthority"),
    ] + [
        # Il server EU non ha earningsGraph (404): sensori sempre non disponibili
        EpCubeEarningSensor(coordinator, key)
        for key in ("earning_today", "earning_month")
        if "/device/earningsGraph" not in hass.data[DOMAIN][entry.entry_id]["state"].unsupported
    ] + [
        EpCubePvStringSensor(coordinator, key)
        for key, value in sorted(((coordinator.data or {}).get("pv") or {}).items())
        if value is not None
    ]
    

    bind_entities_to_entry(entities, entry)

    registry = async_get(hass)

    for entity in entities:
        if registry.async_get_entity_id("sensor", DOMAIN, entity.unique_id) is None:
            disabled_by = None
            if entity.unique_id.endswith("_total") and not enable_total:
                disabled_by = RegistryEntryDisabler.INTEGRATION
            elif entity.unique_id.endswith("_annual") and not enable_annual:
                disabled_by = RegistryEntryDisabler.INTEGRATION
            elif entity.unique_id.endswith("_monthly") and not enable_monthly:
                disabled_by = RegistryEntryDisabler.INTEGRATION
            elif not getattr(entity, "entity_registry_enabled_default", True):
                # Senza questo la lista disabled_by_default di generate_sensors
                # restava senza effetto: l'entità veniva registrata attiva
                disabled_by = RegistryEntryDisabler.INTEGRATION

            registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=entity.unique_id,
                # entity_id senza il serial number: con più impianti è Home
                # Assistant ad aggiungere il suffisso _2 al secondo
                suggested_object_id=legacy_unique_id(entity.unique_id, entry),
                disabled_by=disabled_by
            )

    async_add_entities(entities, True)
    

class EpCubeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, description, region):
        super().__init__(coordinator)
        base_url = get_base_url(region)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"epcube_{description.key}"
        self._attr_entity_id = f"sensor.epcube_{description.key}"
        self._attr_has_entity_name = True
        self._attr_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_options = description.options
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
            "entry_type": "service",
            "configuration_url": f"{base_url}/"
        }

    @property
    def native_value(self):
        value = self.coordinator.data["data"].get(self.entity_description.key)

        if isinstance(value, (list, dict)):
            # Liste e oggetti (fasce TOU, giorni, filtri VPP): HA rifiuta stati
            # oltre 255 caratteri, il valore completo resta negli attributi
            return str(value)[:MAX_STATE_LENGTH]

        if value is not None:
            if self.entity_description.device_class == SensorDeviceClass.ENUM:
                # Valore fuori mappa: None invece di uno stato non dichiarato in options
                return SYSTEM_STATUS_OPTIONS.get(str(value))

            if self.entity_description.device_class == SensorDeviceClass.POWER:
                try:
                    return round(float(value) * 10, 1)
                except (ValueError, TypeError):
                    return None

            # Rete di sicurezza: un sensore numerico che riceve testo farebbe
            # sollevare ValueError a HA, uccidendo l'update di tutti gli altri
            if (
                self.entity_description.state_class is not None
                or self.entity_description.device_class is not None
            ) and not _is_numeric(value):
                _LOGGER.warning(
                    "Valore non numerico %r per il sensore %s (%s): ignorato",
                    value, self.entity_description.key,
                    self.entity_description.device_class,
                )
                return None
        return value

    @property
    def extra_state_attributes(self):
        value = self.coordinator.data["data"].get(self.entity_description.key)
        if isinstance(value, (list, dict)) and len(str(value)) > MAX_STATE_LENGTH:
            return {"value": value}
        return None


class EpCubeLastUpdateSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = "last_update"
        self._attr_unique_id = "epcube_last_update"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True

    @property
    def native_value(self):
        return dt_util.utcnow()

def _battery_state(coordinator) -> EpCubeDataState:
    return coordinator.hass.data[DOMAIN][coordinator.config_entry.entry_id]["state"]


def _battery_source(state_obj):
    """Da dove arrivano carica e scarica: serie misurata o stima dal SoC."""
    return "measured" if state_obj.series_mode else "estimated"


def _series_today(state_obj, key):
    series = state_obj.series
    if series is None or series["day"] != date.today():
        return None
    return round(series[key], 3)


def _series_attributes(state_obj, direction):
    """Fonte dei valori e contabilità della serie, ripristinata al riavvio."""
    attributes = {"source": _battery_source(state_obj)}
    if state_obj.series_day is not None:
        attributes["series_day"] = state_obj.series_day.isoformat()
        attributes["series_seen"] = round(getattr(state_obj, f"series_seen_{direction}"), 4)
    return attributes


def _restore_series(state_obj, attributes, direction):
    """Riprende la contabilità della serie: si somma solo ciò che non era già contato."""
    day = attributes.get("series_day")
    seen = attributes.get("series_seen")
    if not day or seen is None:
        return
    try:
        state_obj.series_day = date.fromisoformat(day)
        setattr(state_obj, f"series_seen_{direction}", float(seen))
    except (TypeError, ValueError):
        return
    state_obj.series_mode = True
    state_obj.series_needs_baseline = False


# Cumulativo totale: energia caricata nella batteria
class EpCubeBatteryChargeSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_energy_in"
        self._attr_translation_key = "battery_energy_in"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        if last_state is not None:
            try:
                state_obj.total_in = float(last_state.state)
            except ValueError:
                pass
            _restore_series(state_obj, last_state.attributes, "in")

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        return round(state_obj.total_in, 3)

    @property
    def extra_state_attributes(self):
        return _series_attributes(_battery_state(self.coordinator), "in")


# Cumulativo totale: energia scaricata dalla batteria
class EpCubeBatteryDischargeSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_energy_out"
        self._attr_translation_key = "battery_energy_out"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        if last_state is not None:
            try:
                state_obj.total_out = float(last_state.state)
            except ValueError:
                pass
            _restore_series(state_obj, last_state.attributes, "out")

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        return round(state_obj.total_out, 3)

    @property
    def extra_state_attributes(self):
        return _series_attributes(_battery_state(self.coordinator), "out")


# Giornaliero: carica accumulata oggi
class EpCubeBatteryDailyChargeSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_daily_charge"
        self._attr_translation_key = "battery_daily_charge"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]

        if (
            last_state is not None
            and last_state.state not in (None, "unknown", "unavailable")
            and dt_util.as_local(last_state.last_changed).date() == date.today()
        ):
            try:
                state_obj.daily_in = float(last_state.state)
            except ValueError:
                state_obj.daily_in = 0.0
        else:
            state_obj.daily_in = 0.0

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        if state_obj.series_mode:
            return _series_today(state_obj, "charge")
        return round(state_obj.daily_in, 3)

    @property
    def extra_state_attributes(self):
        return {"source": _battery_source(_battery_state(self.coordinator))}


# Giornaliero: scarica erogata oggi
class EpCubeBatteryDailyDischargeSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_daily_discharge"
        self._attr_translation_key = "battery_daily_discharge"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]

        if (
            last_state is not None
            and last_state.state not in (None, "unknown", "unavailable")
            and dt_util.as_local(last_state.last_changed).date() == date.today()
        ):
            try:
                state_obj.daily_out = float(last_state.state)
            except ValueError:
                state_obj.daily_out = 0.0
        else:
            state_obj.daily_out = 0.0

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        if state_obj.series_mode:
            return _series_today(state_obj, "discharge")
        return round(state_obj.daily_out, 3)

    @property
    def extra_state_attributes(self):
        return {"source": _battery_source(_battery_state(self.coordinator))}

class EpCubeBatteryPowerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_power"
        self._attr_translation_key = "battery_power"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})

        produzione = data.get("solarpower")
        consumo = data.get("backuppower")
        rete = data.get("gridtotalpower")

        if produzione is None or consumo is None or rete is None:
            return None

        # I valori API sono in unità ×10W — vanno moltiplicati × 10 per ottenere Watt.
        # Grid negativo = esportazione, positivo = importazione.
        # Bilancio: batteria = solare + rete - carichi
        non_backup = data.get("nonbackuppower") or 0
        power_kw = 10 * (float(produzione) + float(rete) - float(consumo) - float(non_backup)) / 1000

        # I termini della stima non sono campionati nello stesso istante: a
        # batteria ferma resta un residuo di qualche decina di watt, sotto la
        # risoluzione della misura. Meglio dichiarare 0 che inventare un flusso
        if abs(power_kw) < BATTERY_POWER_DEADBAND_KW:
            power_kw = 0.0

        value = round(power_kw, 3)

        _LOGGER.debug(
            "[EPCube BatteryPower] Solare: %.1f W | Backup: %.1f W | NonBackup: %.1f W | Grid: %.1f W → Batteria: %.3f kW",
            float(produzione) * 10, float(consumo) * 10, float(non_backup) * 10, float(rete) * 10, value
        )

        return value

    @property
    def extra_state_attributes(self):
        # Potenza misurata dal gateway, media degli ultimi 5 minuti (serie):
        # in ritardo fino a SERIES_INTERVAL, ma senza il rumore della stima
        series = _battery_state(self.coordinator).series
        last = series.get("last") if series else None
        if not last:
            return None
        when, power_kw = last
        # La serie è positiva in scarica: qui positivo vuol dire in carica
        return {"measured_power_5min": round(-power_kw, 3), "measured_at": when}


class EpCubeBatteryStatusSensor(CoordinatorEntity, SensorEntity):
    """Stato batteria (in carica / in scarica / ferma) dal segno della potenza.

    Deriva dallo stesso bilancio di EpCubeBatteryPowerSensor: batteria =
    solare + rete - carichi. Dentro il deadband la batteria è ferma.
    """

    # Testo leggibile per ciascuno stato, esposto come attributo "scritta".
    STATUS_LABELS = {
        "charging": "In carica",
        "discharging": "In scarica",
        "idle": "Ferma",
    }

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_battery_status"
        self._attr_translation_key = "battery_status"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["charging", "discharging", "idle"]
        self._attr_icon = "mdi:battery-charging"
        self._last_status = "idle"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    def _compute_status(self):
        data = self.coordinator.data.get("data", {})

        produzione = data.get("solarpower")
        consumo = data.get("backuppower")
        rete = data.get("gridtotalpower")

        if produzione is None or consumo is None or rete is None:
            return None

        non_backup = data.get("nonbackuppower") or 0
        power_kw = 10 * (float(produzione) + float(rete) - float(consumo) - float(non_backup)) / 1000

        # Isteresi: si entra in carica/scarica oltre ±DEADBAND e si torna a
        # ferma solo sotto IDLE_KW; nella fascia intermedia si tiene lo stato
        # precedente per non oscillare.
        if power_kw > BATTERY_POWER_DEADBAND_KW:
            status = "charging"
        elif power_kw < -BATTERY_POWER_DEADBAND_KW:
            status = "discharging"
        elif abs(power_kw) < BATTERY_STATUS_IDLE_KW:
            status = "idle"
        else:
            status = self._last_status

        self._last_status = status
        return status

    @property
    def native_value(self):
        return self._compute_status()

    @property
    def extra_state_attributes(self):
        status = self._last_status
        return {"scritta": self.STATUS_LABELS.get(status, status)}


class EpCubeTotalLoadPowerSensor(CoordinatorEntity, SensorEntity):
    """Potenza istantanea totale dei carichi (backup + non-backup)."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_total_load_power"
        self._attr_has_entity_name = True
        self._attr_translation_key = "total_load_power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:home-lightning-bolt"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        backup = data.get("backuppower")
        nonbackup = data.get("nonbackuppower")
        if backup is None and nonbackup is None:
            return None
        return round((float(backup or 0) + float(nonbackup or 0)) * 10, 1)


class EpCubeTotalLoadEnergySensor(CoordinatorEntity, SensorEntity):
    """Energia totale consumata oggi (backup + non-backup)."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_total_load_energy"
        self._attr_has_entity_name = True
        self._attr_translation_key = "total_load_energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:home-lightning-bolt-outline"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        backup = data.get("backupelectricity")
        nonbackup = data.get("nonbackupelectricity")
        if backup is None and nonbackup is None:
            return None
        return round(float(backup or 0) + float(nonbackup or 0), 3)


class EpCubeYesterdayGridFromSensor(CoordinatorEntity, SensorEntity):
    """Energia prelevata dalla rete ieri."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_yesterday_grid_from"
        self._attr_translation_key = "yesterday_grid_from"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:transmission-tower-import"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        v = data.get("gridelectricityfrom_yesterday")
        return round(float(v), 3) if v is not None else None


class EpCubeYesterdayGridToSensor(CoordinatorEntity, SensorEntity):
    """Energia immessa in rete ieri."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_yesterday_grid_to"
        self._attr_translation_key = "yesterday_grid_to"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        v = data.get("gridelectricityto_yesterday")
        return round(float(v), 3) if v is not None else None


class EpCubeYesterdaySolarSensor(CoordinatorEntity, SensorEntity):
    """Energia prodotta dal fotovoltaico ieri."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_yesterday_solar"
        self._attr_translation_key = "yesterday_solar"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:solar-power-variant"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        v = data.get("solarelectricity_yesterday")
        return round(float(v), 3) if v is not None else None


class EpCubeYesterdayLoadSensor(CoordinatorEntity, SensorEntity):
    """Energia totale consumata ieri (backup + non-backup)."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_yesterday_load"
        self._attr_translation_key = "yesterday_load"
        self._attr_has_entity_name = True
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:home-lightning-bolt-outline"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        backup = data.get("backupelectricity_yesterday")
        nonbackup = data.get("nonbackupelectricity_yesterday")
        if backup is None and nonbackup is None:
            return None
        return round(float(backup or 0) + float(nonbackup or 0), 3)


class EpCubeTouActiveWeeksSensor(CoordinatorEntity, SensorEntity):
    """Sensore che mostra i giorni attivi per la tariffazione."""
    def __init__(self, coordinator, week_type):
        super().__init__(coordinator)
        self.week_type = week_type
        self.coordinator = coordinator
        
        # Giorni della settimana
        self.day_names = {
            1: "Lunedì",
            2: "Martedì",
            3: "Mercoledì",
            4: "Giovedì",
            5: "Venerdì",
            6: "Sabato",
            7: "Domenica"
        }
        
        if week_type == "workday":
            self._attr_has_entity_name = True
            self._attr_translation_key = "tou_active_week"
            self._attr_unique_id = "epcube_tou_active_week"
            self._attr_icon = "mdi:calendar-week"
            self.key = "activeweek"
        else:  # non_workday
            self._attr_has_entity_name = True
            self._attr_translation_key = "tou_active_week_nonworkday"
            self._attr_unique_id = "epcube_tou_active_week_nonworkday"
            self._attr_icon = "mdi:calendar-remove"
            self.key = "activeweeknonworkday"
        
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        days = data.get(self.key, [])
        
        if not days or len(days) == 0:
            return "Non configurato"
        
        day_names = [self.day_names.get(d, f"Giorno {d}") for d in days]
        return ", ".join(day_names)


class EpCubeExtrasSensor(CoordinatorEntity, SensorEntity):
    """Sensore su un valore di coordinator.data["extras"] (vedi extras.py)."""

    _attr_has_entity_name = True
    extras_key = None

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"epcube_{key}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def _extra(self):
        extras = (self.coordinator.data or {}).get("extras") or {}
        return extras.get(self.extras_key)

    @property
    def available(self):
        return super().available and self._extra is not None


class EpCubeLastPowerCutSensor(EpCubeExtrasSensor):
    """Ultimo blackout dal registro getDevPowerCutLog; i precedenti negli attributi."""

    extras_key = "power_cuts"
    _attr_icon = "mdi:transmission-tower-off"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "last_power_cut")

    @property
    def native_value(self):
        # Registro vuoto (nessun blackout): disponibile ma senza valore
        if not self._extra:
            return None
        return self._extra[0].get("startTime")

    @property
    def extra_state_attributes(self):
        events = self._extra or []
        last = events[0] if events else {}
        return {
            "end_time": last.get("endTime"),
            "duration": last.get("duration"),
            "events": [
                {
                    "start_time": event.get("startTime"),
                    "end_time": event.get("endTime"),
                    "duration": event.get("duration"),
                }
                for event in events
            ],
        }


class EpCubeEarningSensor(EpCubeExtrasSensor):
    """Guadagno calcolato dal cloud (earningsGraph), con la valuta dell'impianto."""

    _attr_icon = "mdi:cash"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.extras_key = key

    @property
    def native_value(self):
        return self._extra

    @property
    def native_unit_of_measurement(self):
        data = (self.coordinator.data or {}).get("data") or {}
        unit = data.get("unitdefault")
        return unit if isinstance(unit, str) and unit else None


class EpCubeWeatherSensor(EpCubeExtrasSensor):
    """Meteo che l'app mostra nella Home (homeDeviceInfoWeather)."""

    extras_key = "weather"
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "weather")

    @property
    def native_value(self):
        weather = self._extra or {}
        return weather.get("description") or weather.get("main")

    @property
    def extra_state_attributes(self):
        weather = self._extra or {}
        return {
            "condition": weather.get("main"),
            "temperature": weather.get("temp") or weather.get("weatherTemp"),
            "temperature_min": weather.get("tempMin"),
            "temperature_max": weather.get("tempMax"),
            "icon_code": weather.get("icon"),
        }


class EpCubePvStringSensor(CoordinatorEntity, SensorEntity):
    """Grandezza di una stringa FV (getSolarPvPower): potenza, corrente o tensione.

    getSolarPvPower restituisce per ogni stringa pvNpower (kW), pvNcurrent (A) e
    pvNvoltage (V): ognuna va presentata con nome, unità e device class propri,
    non tutte come potenza (era il bug: 'Potenza Stringa PV1current').
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:solar-panel"

    # suffisso chiave -> (translation_key, device_class, unità)
    _MEASURES = {
        "power": ("pv_string_power", SensorDeviceClass.POWER, UnitOfPower.KILO_WATT),
        "current": ("pv_string_current", SensorDeviceClass.CURRENT,
                    UnitOfElectricCurrent.AMPERE),
        "voltage": ("pv_string_voltage", SensorDeviceClass.VOLTAGE,
                    UnitOfElectricPotential.VOLT),
    }

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._key = key
        # Riconosce il tipo dal suffisso; default a potenza per retrocompatibilità
        measure = next((m for m in ("current", "voltage") if key.endswith(m)), "power")
        translation_key, device_class, unit = self._MEASURES[measure]
        number = key.removeprefix("pv").removesuffix(measure)
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_translation_placeholders = {"number": number}
        self._attr_unique_id = f"epcube_{key}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def available(self):
        pv = (self.coordinator.data or {}).get("pv") or {}
        return super().available and pv.get(self._key) is not None

    @property
    def native_value(self):
        pv = (self.coordinator.data or {}).get("pv") or {}
        value = pv.get(self._key)
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None


class EpCubeAuthoritySensor(CoordinatorEntity, SensorEntity):
    """Autorizzazione/capacità dell'account (user/user/base -> tblDevice).

    Flag come kebaAuthority, eebusAuthority, triphaseAuthority: decidono quali
    funzioni l'app mostra. Diagnostici, disabilitati di default.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:shield-key-outline"

    def __init__(self, coordinator, field):
        super().__init__(coordinator)
        self._field = field
        self._attr_translation_key = field.lower()
        self._attr_unique_id = f"epcube_{field.lower()}"
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        extras = (self.coordinator.data or {}).get("extras") or {}
        device = extras.get("user_device") or {}
        value = device.get(self._field)
        return str(value) if value is not None else None


class EpCubeAlertSensor(EpCubeExtrasSensor):
    """Ultimo avviso o guasto (getAlertFaultList), testo e soluzione in inglese."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, extras_key, key):
        super().__init__(coordinator, key)
        self.extras_key = extras_key

    @property
    def native_value(self):
        # Elenco vuoto: nessun avviso/guasto attivo. Si riporta "Nessuno" invece
        # di None, così lo stato dice chiaramente "tutto ok" e non "unknown".
        if not self._extra:
            return "Nessuno"
        content = self._extra[0].get("enContent") or ""
        return content[:255] or "Nessuno"

    @property
    def extra_state_attributes(self):
        events = self._extra or []
        last = events[0] if events else {}
        return {
            "start_time": last.get("startTime") or last.get("startDate"),
            "end_time": last.get("endTime") or last.get("endDate"),
            "solution": last.get("enSolution"),
            "events": [
                {
                    "content": event.get("enContent"),
                    "start_time": event.get("startTime") or event.get("startDate"),
                    "end_time": event.get("endTime") or event.get("endDate"),
                }
                for event in events
            ],
        }


class EpCubeWifiSensor(EpCubeExtrasSensor):
    """Stato del Wi-Fi del gateway (netWorkInfo)."""

    extras_key = "network"
    _attr_icon = "mdi:wifi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "wifi")

    @property
    def native_value(self):
        network = self._extra or {}
        return network.get("wifiStatusStr") or network.get("wifiStatus")

    @property
    def extra_state_attributes(self):
        network = self._extra or {}
        return {"ssid": network.get("wifiName"), "status_code": network.get("wifiStatus")}


class EpCubeFirmwareSensor(EpCubeExtrasSensor):
    """Versioni firmware di gateway e RTU (queryFirmwareInfo)."""

    extras_key = "firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "firmware")

    @property
    def native_value(self):
        return (self._extra or {}).get("firmwareVersion")

    @property
    def extra_state_attributes(self):
        firmware = self._extra or {}
        return {
            "rtu_version": firmware.get("rtuVersion"),
            "auto_update": firmware.get("aotuUpdateFirmware"),
        }
