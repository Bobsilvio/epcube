"""Invio delle chiamate di scrittura all'API EP Cube.

Il POST a /device/switchMode era ricopiato in select, switch e number, ognuno
con la propria gestione (o assenza) di timeout e retry: number.py apriva una
ClientSession senza timeout e senza ritentare. Qui c'è una sola implementazione.
"""

from .const import (
    get_base_url, USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT,
    MAX_RETRIES, RETRY_DELAY, api_language,
)

from .auth import async_refresh_token, InvalidCredentials
from .extras import async_fetch_api_data
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import aiohttp
import asyncio
import json
import logging

_LOGGER = logging.getLogger(__name__)


def entry_token(entry):
    """Token della entry, preferendo quello aggiornato dalle opzioni."""
    return entry.options.get("token") or entry.data.get("token")


# Tipi di /device/saveSettings, dall'app Android: ogni tipo salva solo i suoi
# campi, senza toccare TOU e riserve come invece fa switchMode
SETTING_WEATHER_WATCH = "1"
SETTING_EV_CHARGER = "2"
SETTING_GENERATOR = "3"
SETTING_OFF_GRID_NOTIFICATION = "4"
SETTING_AUTO_UPDATE = "5"
SETTING_REMOTE_PRIVILEGE = "6"
SETTING_SLEEP_MODE = "7"
SETTING_INDICATOR_LIGHT = "8"
SETTING_WINTER_MODE = "9"
SETTING_ALLOW_CHARGING = "10"


async def async_post_switch_mode(hass, entry, payload, label="switchMode"):
    """Invia un payload a /device/switchMode. True se il server ha accettato."""
    return await _async_post(hass, entry, "/device/switchMode", payload, label)


# Attesa prima di rileggere getSwitchMode dopo una scrittura
SWITCH_MODE_SETTLE = 3  # seconds


async def async_read_switch_mode_field(hass, entry, dev_id, field):
    """Rilegge un campo di getSwitchMode dopo una scrittura, None se non leggibile.

    Il server risponde "Success" anche ai campi che il gateway poi ignora:
    rileggere è l'unico modo per sapere se il valore è stato preso.
    """
    await asyncio.sleep(SWITCH_MODE_SETTLE)
    region = entry.options.get("region") or entry.data.get("region", "EU")
    data = await async_fetch_api_data(
        async_get_clientsession(hass), entry_token(entry), region,
        f"/device/getSwitchMode?devId={dev_id}",
    )
    return data.get(field) if isinstance(data, dict) else None


async def async_save_settings(hass, entry, dev_id, setting_type, fields, label=None):
    """Salva un gruppo di impostazioni con /device/saveSettings."""
    payload = {"devId": str(dev_id), "type": setting_type, "onlySave": "0", **fields}
    return await _async_post(
        hass, entry, "/device/saveSettings", payload, label or f"saveSettings tipo {setting_type}"
    )


# Modalità invernale nell'app EU: endpoint dedicato e valori 170 (accesa) / 85
# (spenta), gli stessi che getSwitchMode restituisce in winterProtect
WINTER_PROTECT_ON = 170
WINTER_PROTECT_OFF = 85


async def async_set_winter_protect(hass, entry, dev_id, enabled):
    """Accende o spegne la modalità invernale come l'app EU (settingWinterProtect)."""
    payload = {
        "devId": str(dev_id),
        "winterProtect": WINTER_PROTECT_ON if enabled else WINTER_PROTECT_OFF,
        "onlySave": "0",
    }
    return await _async_post(
        hass, entry, "/device/settingWinterProtect", payload, f"winterProtect={payload['winterProtect']}"
    )


async def _async_post(hass, entry, path, payload, label):
    session = async_get_clientsession(hass)
    region = entry.options.get("region") or entry.data.get("region", "EU")
    url = f"{get_base_url(region)}{path}"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": entry_token(entry),
        "user-agent": USER_AGENT,
        "accept-language": api_language(),
        "accept-encoding": "gzip, deflate, br",
    }
    relogged = False
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

    _LOGGER.debug("Invio payload %s: %s", label, payload)

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(
                url, headers=headers, json=payload, timeout=timeout
            ) as resp:
                text = await resp.text()

                status = resp.status
                if status == 200:
                    # Alcuni server rispondono 200 con l'errore vero nel corpo
                    status = _body_status(text) or 200
                if status == 200:
                    _LOGGER.info("%s applicato. Risposta: %s", label, text)
                    return True
                if status in (401, 403):
                    if not relogged and await _async_relogin(hass, entry):
                        relogged = True
                        headers["authorization"] = entry_token(entry)
                        continue
                    _LOGGER.error("Token non valido o scaduto (%s): %s fallito", status, label)
                    return False
                if resp.status == 200:
                    _LOGGER.error("%s rifiutato dal server: %s", label, text)
                    return False
                if resp.status == 429:
                    _LOGGER.warning(
                        "Rate limit al tentativo %d/%d per %s", attempt + 1, MAX_RETRIES, label
                    )
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * 2)
                        continue
                    _LOGGER.error("Rate limit: %s non applicato", label)
                    return False
                if resp.status >= 500:
                    _LOGGER.warning(
                        "Errore server %s al tentativo %d/%d per %s: %s",
                        resp.status, attempt + 1, MAX_RETRIES, label, text,
                    )
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return False

                _LOGGER.error("Errore HTTP %s per %s: %s", resp.status, label, text)
                return False

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout al tentativo %d/%d per %s", attempt + 1, MAX_RETRIES, label)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            _LOGGER.error("Timeout: %s non applicato", label)
            return False
        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Errore connessione al tentativo %d/%d per %s: %s",
                attempt + 1, MAX_RETRIES, label, err,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            _LOGGER.error("Connessione fallita: %s non applicato", label)
            return False

    return False


async def _async_relogin(hass, entry):
    """Rinnova il token se la entry ha le credenziali. True se rinnovato."""
    try:
        return bool(await async_refresh_token(hass, entry))
    except InvalidCredentials as err:
        _LOGGER.error("Credenziali EP Cube rifiutate: %s", err)
        entry.async_start_reauth(hass)
        return False


def _body_status(text):
    """Campo status del corpo JSON, se presente."""
    try:
        status = json.loads(text).get("status")
        return int(status) if status is not None else None
    except (ValueError, TypeError, AttributeError):
        return None
