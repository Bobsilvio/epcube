import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import aiohttp
import asyncio
import logging
from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SCALE_POWER,
    CONF_ENABLE_TOTAL, CONF_ENABLE_ANNUAL, CONF_ENABLE_MONTHLY, get_base_url,
    USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

_LOGGER = logging.getLogger(__name__)

class EpCubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._errors = {}

    async def async_step_user(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            region = user_input["region"]
            token = user_input["token"].strip()
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"

            sn = await self._get_sn_from_token(token, region)

            if not sn:
                self._errors["base"] = "sn_not_found"
            else:
                for entry in self._async_current_entries():
                    if entry.data.get("sn") == sn:
                        return self.async_abort(reason="already_configured")

                await self.async_set_unique_id(sn)
                return self.async_create_entry(
                    title=f"EpCube {sn}",
                    data={
                        "token": token,
                        "sn": sn,
                        "region": region
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("token"): str,
                vol.Required("region", default="EU"): vol.In(["EU", "US", "JP"]),
            }),
            errors=self._errors,
        )

    async def _get_sn_from_token(self, token, region):
        base_url = get_base_url(region)
        url = f"{base_url}/user/user/base"
        headers = {
            "accept": "*/*",
            "accept-language": "it-IT",
            "accept-encoding": "gzip, deflate, br",
            "user-agent": USER_AGENT,
            "authorization": token
        }
        
        timeout = aiohttp.ClientTimeout(
            total=HTTP_TIMEOUT,
            connect=HTTP_CONNECT_TIMEOUT
        )
        
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            _LOGGER.debug("Risposta user/base: %s", data)
                            sn = data.get("data", {}).get("defDevSgSn")
                            if sn:
                                return sn
                            else:
                                _LOGGER.error("Serial number non trovato nella risposta")
                                self._errors["base"] = "sn_not_found"
                                return None
                        elif response.status == 401:
                            _LOGGER.error("Token non valido o scaduto (401)")
                            self._errors["base"] = "invalid_token"
                            return None
                        elif response.status == 403:
                            _LOGGER.error("Accesso negato (403)")
                            self._errors["base"] = "forbidden"
                            return None
                        elif response.status >= 500:
                            _LOGGER.warning("Errore server %s al tentativo %d/%d", response.status, attempt + 1, MAX_RETRIES)
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            else:
                                self._errors["base"] = "server_error"
                                return None
                        else:
                            _LOGGER.error("Errore HTTP %s nella richiesta user/base", response.status)
                            self._errors["base"] = "http_error"
                            return None
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout al tentativo %d/%d", attempt + 1, MAX_RETRIES)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    self._errors["base"] = "timeout"
                    return None
            except aiohttp.ClientError as e:
                _LOGGER.warning("Errore connessione al tentativo %d/%d: %s", attempt + 1, MAX_RETRIES, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    self._errors["base"] = "connection_error"
                    return None
            except Exception as e:
                _LOGGER.exception("Errore durante la richiesta user/base: %s", e)
                self._errors["base"] = "unknown_error"
                return None
        
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EpCubeOptionsFlow(config_entry)

class EpCubeOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            token = user_input.get("token", "").strip()
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            return self.async_create_entry(title="", data={
                "token": token,
                "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                CONF_SCALE_POWER: user_input.get(CONF_SCALE_POWER, False),
                CONF_ENABLE_TOTAL: user_input.get(CONF_ENABLE_TOTAL, False),
                CONF_ENABLE_ANNUAL: user_input.get(CONF_ENABLE_ANNUAL, False),
                CONF_ENABLE_MONTHLY: user_input.get(CONF_ENABLE_MONTHLY, False),
                "region": user_input.get("region", self._config_entry.data.get("region", "EU")),
            })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("token", default=self._config_entry.data.get("token")): str,
                vol.Optional("scan_interval", default=self._config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                vol.Optional(CONF_ENABLE_TOTAL, default=self._config_entry.options.get(CONF_ENABLE_TOTAL, False)): bool,
                vol.Optional(CONF_ENABLE_ANNUAL, default=self._config_entry.options.get(CONF_ENABLE_ANNUAL, False)): bool,
                vol.Optional(CONF_ENABLE_MONTHLY, default=self._config_entry.options.get(CONF_ENABLE_MONTHLY, False)): bool,
                vol.Optional("region", default=self._config_entry.data.get("region", "EU")): vol.In(["EU", "US", "JP"]),
            })
        )
