from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS, DEFAULT_SCAN_INTERVAL, get_base_url
from .sensor import async_update_data_with_stats
from .state import EpCubeDataState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    token = entry.data["token"]
    sn = entry.data["sn"]
    region = entry.data.get("region", "EU")
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    base_url = get_base_url(region)
    url = f"{base_url}/api/device/homeDeviceInfo?&sgSn={sn}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)",
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
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
