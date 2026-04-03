from homeassistant.const import UnitOfEnergy, UnitOfPower, PERCENTAGE
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntityDescription, SensorEntity
from homeassistant.helpers.entity import EntityCategory, Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity
from homeassistant.helpers.entity_registry import async_get, RegistryEntryDisabler
from homeassistant.helpers.restore_state import RestoreEntity

from .state import EpCubeDataState
from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_ENABLE_TOTAL, CONF_ENABLE_ANNUAL, 
    CONF_ENABLE_MONTHLY, get_base_url, USER_AGENT, HTTP_TIMEOUT, 
    HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)
from .translations import translate_field_name, translate_status_value
import aiohttp
import async_timeout
import asyncio
import json
from datetime import timedelta, datetime, date

import logging
_LOGGER = logging.getLogger(__name__)

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
            entity_category = EntityCategory.CONFIG
        elif base_key in diagnostic_sensors:
            entity_category = EntityCategory.DIAGNOSTIC

        #ectricity = kWh
        #power = kW (none)
        #power (i numeri arrivano in watt) = W
        
        if "electricity" in base_key:
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
        ):
            device_class = SensorDeviceClass.POWER
            unit_of_measurement = UnitOfPower.WATT
            state_class = SensorStateClass.MEASUREMENT

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
            entity_registry_enabled_default=entity_registry_enabled_default
        )

        sensors.append(sensor)

    return sensors

async def fetch_device_info(session, token, dev_id, region):
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
        with async_timeout.timeout(HTTP_TIMEOUT):
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

async def fetch_device_list(session, token, dev_id, region):
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
        with async_timeout.timeout(HTTP_TIMEOUT):
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


async def fetch_switch_mode(session, token, dev_id, region):
    """Fetch getSwitchMode e ritorna i dati normalizzati in lowercase."""
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
        with async_timeout.timeout(HTTP_TIMEOUT):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    raw_data = json_data.get("data", {})
                    return {k.lower(): v for k, v in raw_data.items()}
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


async def fetch_epcube_stats(session, token, dev_id, date_str, scope_type, region):
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
        with async_timeout.timeout(HTTP_TIMEOUT):
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

async def async_update_data_with_stats(session, url, headers, dev_id_sn, token, hass, entry_id):
    config_entry = hass.data[DOMAIN][entry_id].get("config_entry")
    region = config_entry.data.get("region", "EU") if config_entry else "EU"
    base_url = get_base_url(region)
    
    try:
        with async_timeout.timeout(HTTP_TIMEOUT):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    raise UpdateFailed("Token non valido o scaduto")
                elif resp.status == 403:
                    raise UpdateFailed("Accesso negato all'API")
                elif resp.status == 429:
                    raise UpdateFailed("Rate limit raggiunto - riprova più tardi")
                elif resp.status >= 500:
                    raise UpdateFailed(f"Errore server {resp.status}")
                elif resp.status != 200:
                    raise UpdateFailed(f"Errore HTTP {resp.status}")
                
                if resp.content_type != "application/json":
                    raise UpdateFailed(f"Tipo MIME non gestito: {resp.content_type}")

                live_data = await resp.json()
                full_data_raw = live_data.get("data", {})
                full_data = {k.lower(): v for k, v in full_data_raw.items()}
                real_dev_id = full_data.get("devid")

                if not real_dev_id:
                    raise UpdateFailed("Device ID non trovato nella risposta")

                now = datetime.now()
                year_str = str(now.year)
                month_str = now.strftime("%Y-%m")
                today_str = now.strftime("%Y-%m-%d")

                live_data = {}
                total_data = {}
                annual_data = {}
                monthly_data = {}
                device_info = {}
                device_list_info = {}
                switch_mode_data = {}
                try:
                    (
                        live_data,
                        total_data,
                        annual_data,
                        monthly_data,
                        device_info,
                        device_list_info,
                        switch_mode_data,
                    ) = await asyncio.gather(
                        fetch_epcube_stats(session, token, real_dev_id, today_str, 1, region),
                        fetch_epcube_stats(session, token, real_dev_id, year_str, 0, region),
                        fetch_epcube_stats(session, token, real_dev_id, year_str, 3, region),
                        fetch_epcube_stats(session, token, real_dev_id, month_str, 2, region),
                        fetch_device_info(session, token, real_dev_id, region),
                        fetch_device_list(session, token, real_dev_id, region),
                        fetch_switch_mode(session, token, real_dev_id, region),
                        return_exceptions=False,
                    )
                except Exception as e:
                    _LOGGER.warning("Errore nel fetch dati supplementari: %s", e)

                # Merge switch mode — sovrascrive homeDeviceInfo per SoC e config TOU
                for k, v in switch_mode_data.items():
                    full_data[k] = v

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

                battery_now = full_data.get("batterycurrentelectricity")
                if battery_now is not None:
                    try:
                        state: EpCubeDataState = hass.data[DOMAIN][entry_id]["state"]
                        state.update(float(battery_now))
                    except Exception as e:
                        _LOGGER.warning("Errore nel calcolo del SOC cumulativo: %s", e)

                return {"data": full_data}

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
        EpCubeTotalLoadPowerSensor(coordinator),
        EpCubeTotalLoadEnergySensor(coordinator),
        # Sensori TOU (Tariffazione)
        EpCubeTouScheduleSensor(coordinator, "peak"),
        EpCubeTouScheduleSensor(coordinator, "midpeak"),
        EpCubeTouScheduleSensor(coordinator, "offpeak"),
        EpCubeTouScheduleSensor(coordinator, "daylight_peak"),
        EpCubeTouScheduleSensor(coordinator, "daylight_midpeak"),
        EpCubeTouScheduleSensor(coordinator, "daylight_offpeak"),
        EpCubeTouActiveWeeksSensor(coordinator, "workday"),
        EpCubeTouActiveWeeksSensor(coordinator, "non_workday"),
    ]
    

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

            registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=entity.unique_id,
                suggested_object_id=entity.unique_id,
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

        if value is not None:
            if self.entity_description.device_class == SensorDeviceClass.POWER:
                try:
                    return round(float(value) * 10, 1)
                except (ValueError, TypeError):
                    return None
        return value

class EpCubeLastUpdateSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "EP CUBE Ultimo Aggiornamento"
        self._attr_unique_id = "epcube_last_update"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True

    @property
    def native_value(self):
        return dt_util.utcnow()

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

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        return round(state_obj.total_in, 3)


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

    @property
    def native_value(self):
        state_obj = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["state"]
        return round(state_obj.total_out, 3)


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
        return round(state_obj.daily_in, 3)


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
        return round(state_obj.daily_out, 3)

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
        value = round(power_kw, 3)

        _LOGGER.debug(
            "[EPCube BatteryPower] Solare: %.1f W | Backup: %.1f W | NonBackup: %.1f W | Grid: %.1f W → Batteria: %.3f kW",
            float(produzione) * 10, float(consumo) * 10, float(non_backup) * 10, float(rete) * 10, value
        )

        return value


class EpCubeTotalLoadPowerSensor(CoordinatorEntity, SensorEntity):
    """Potenza istantanea totale dei carichi (backup + non-backup)."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "epcube_total_load_power"
        self._attr_name = "Potenza Consumo Totale"
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
        self._attr_name = "Energia Consumo Totale (Oggi)"
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


def _format_time_range(times_list):
    """Formatta una lista di intervalli orari in stringa leggibile."""
    if not times_list or len(times_list) == 0:
        return "Non configurato"
    
    formatted = []
    for interval in times_list:
        if isinstance(interval, (list, tuple)) and len(interval) >= 2:
            start, end = interval[0], interval[1]
            formatted.append(f"{int(start):02d}:00-{int(end):02d}:00")
    
    return ", ".join(formatted) if formatted else "Non configurato"


class EpCubeTouScheduleSensor(CoordinatorEntity, SensorEntity):
    """Sensore che mostra gli orari TOU impostati."""
    def __init__(self, coordinator, tou_type):
        super().__init__(coordinator)
        self.tou_type = tou_type
        self.coordinator = coordinator
        
        # Mapping tipo TOU -> info
        self.tou_info = {
            "peak": {
                "name": "Orari di Picco",
                "unique_id": "epcube_tou_peak_times",
                "key": "peaktimelist",
                "icon": "mdi:flash"
            },
            "midpeak": {
                "name": "Orari Semi-Picco",
                "unique_id": "epcube_tou_midpeak_times",
                "key": "midpeaktimelist",
                "icon": "mdi:flash-outline"
            },
            "offpeak": {
                "name": "Orari Fuori Picco",
                "unique_id": "epcube_tou_offpeak_times",
                "key": "offpeaktimelist",
                "icon": "mdi:moon-waxing-crescent"
            },
            "daylight_peak": {
                "name": "Orari Luce - Picco",
                "unique_id": "epcube_tou_daylight_peak_times",
                "key": "daylightpeaktimelist",
                "icon": "mdi:sun-clock"
            },
            "daylight_midpeak": {
                "name": "Orari Luce - Semi-Picco",
                "unique_id": "epcube_tou_daylight_midpeak_times",
                "key": "daylightmidpeaktimelist",
                "icon": "mdi:sun-clock-outline"
            },
            "daylight_offpeak": {
                "name": "Orari Luce - Fuori Picco",
                "unique_id": "epcube_tou_daylight_offpeak_times",
                "key": "daylightoffpeaktimelist",
                "icon": "mdi:moon-new"
            }
        }
        
        info = self.tou_info[tou_type]
        self._attr_name = info["name"]
        self._attr_unique_id = info["unique_id"]
        self._attr_icon = info["icon"]
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_class = None
        self._attr_device_info = {
            "identifiers": {("epcube", "epcube_device")},
            "name": "EPCUBE",
            "manufacturer": "CanadianSolar",
            "model": "EPCUBE",
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get("data", {})
        info = self.tou_info[self.tou_type]
        times_list = data.get(info["key"], [])
        return _format_time_range(times_list)


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
            self._attr_name = "Giorni Attivi - Lavorativi"
            self._attr_unique_id = "epcube_tou_active_week"
            self._attr_icon = "mdi:calendar-week"
            self.key = "activeweek"
        else:  # non_workday
            self._attr_name = "Giorni Attivi - Festivi"
            self._attr_unique_id = "epcube_tou_active_week_nonworkday"
            self._attr_icon = "mdi:calendar-remove"
            self.key = "activeweeknonworkday"
        
        self._attr_entity_category = EntityCategory.CONFIG
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