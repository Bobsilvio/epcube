"""Diagnostica scaricabile (Impostazioni > Dispositivi > EP Cube > Scarica diagnostica).

Oltre ai dati del coordinator interroga una volta gli endpoint dell'app non
ancora integrati, per vedere cosa restituisce davvero ogni impianto prima di
trasformarli in entità. Credenziali, token, serial number e posizione vengono
oscurati.
"""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import entry_token
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, USER_AGENT, STATS_TIMEOUT, get_base_url

import aiohttp
import asyncio

TO_REDACT = {
    "token", CONF_USERNAME, CONF_PASSWORD, "sn",
    # Identificativi e posizione dell'impianto (chiavi in minuscolo e originali)
    "sgsn", "sgSn", "rtusn", "rtuSn", "snitems", "snItems", "outersn", "outerSn",
    "defdevsgsn", "defDevSgSn", "lat", "lon", "addressinfo", "addressInfo",
    "email", "wifiname", "wifiName",
}


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = coordinator.data or {}
    dev_id = (data.get("data") or {}).get("devid")

    probes = {}
    if dev_id:
        region = entry.options.get("region") or entry.data.get("region", "EU")
        session = async_get_clientsession(hass)
        token = entry_token(entry)
        paths = {
            "getSolarPvPower": f"/device/getSolarPvPower?devId={dev_id}",
            "getDeviceNewestInfo": f"/device/v2/getDeviceNewestInfo?devId={dev_id}",
            "netWorkInfo": f"/device/netWorkInfo?devId={dev_id}",
            "queryFirmwareInfo": f"/user/user/queryFirmwareInfo?devId={dev_id}",
            "getWarranty": f"/device/getWarranty?devId={dev_id}",
            "getEarningsConfig": f"/device/getEarningsConfig?devId={dev_id}",
            "getNewestModeInfo": f"/device/getNewestModeInfo?devId={dev_id}",
            "getSettingsData": f"/device/getSettingsData?devId={dev_id}",
        }
        # Il tipo dell'elenco allarmi non è ricavabile dall'app decompilata
        for alert_type in ("0", "1", "2"):
            paths[f"getAlertFaultList_{alert_type}"] = (
                f"/device/getAlertFaultList/{dev_id}/{alert_type}?pageNo=1&pageSize=10"
            )
        results = await asyncio.gather(*(
            _async_probe(session, token, region, path) for path in paths.values()
        ))
        probes = dict(zip(paths, results))

    return async_redact_data({
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "data": data,
        },
        "probes": probes,
    }, TO_REDACT)


async def _async_probe(session, token, region, path):
    """GET grezzo: stato HTTP e corpo, anche quando è un errore."""
    headers = {"accept": "*/*", "user-agent": USER_AGENT, "authorization": token}
    try:
        async with asyncio.timeout(STATS_TIMEOUT):
            async with session.get(f"{get_base_url(region)}{path}", headers=headers) as resp:
                text = await resp.text()
                try:
                    body = await resp.json(content_type=None)
                except ValueError:
                    body = text[:500]
                return {"http_status": resp.status, "body": body}
    except (asyncio.TimeoutError, aiohttp.ClientError) as err:
        return {"error": str(err)}
