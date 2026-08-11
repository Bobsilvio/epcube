"""Invio delle chiamate di scrittura all'API EP Cube.

Il POST a /device/switchMode era ricopiato in select, switch e number, ognuno
con la propria gestione (o assenza) di timeout e retry: number.py apriva una
ClientSession senza timeout e senza ritentare. Qui c'è una sola implementazione.
"""

from .const import (
    get_base_url, USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT,
    MAX_RETRIES, RETRY_DELAY,
)

import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


def entry_token(entry):
    """Token della entry, preferendo quello aggiornato dalle opzioni."""
    return entry.options.get("token") or entry.data.get("token")


async def async_post_switch_mode(session, entry, payload, label="switchMode"):
    """Invia un payload a /device/switchMode. True se il server ha accettato."""
    region = entry.options.get("region") or entry.data.get("region", "EU")
    url = f"{get_base_url(region)}/device/switchMode"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": entry_token(entry),
        "user-agent": USER_AGENT,
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
    }
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

    _LOGGER.debug("Invio payload %s: %s", label, payload)

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(
                url, headers=headers, json=payload, timeout=timeout
            ) as resp:
                text = await resp.text()

                if resp.status == 200:
                    _LOGGER.info("%s applicato. Risposta: %s", label, text)
                    return True
                if resp.status == 401:
                    _LOGGER.error("Token non valido o scaduto (401): %s fallito", label)
                    return False
                if resp.status == 403:
                    _LOGGER.error("Accesso negato (403): %s fallito", label)
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
