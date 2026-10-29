import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import aiohttp
import asyncio
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_SCALE_POWER,
    CONF_ENABLE_TOTAL, CONF_ENABLE_ANNUAL, CONF_ENABLE_MONTHLY, get_base_url,
    USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    CONF_USERNAME, CONF_PASSWORD, api_language, set_api_language,
)
from .auth import async_login, InvalidCredentials, CaptchaFailed, EpCubeLoginError

_LOGGER = logging.getLogger(__name__)

REGIONS = ["EU", "US", "JP"]


async def _async_login_errors(hass, region, username, password, errors):
    """Login con email e password: token, oppure None con l'errore in errors."""
    try:
        return await async_login(async_get_clientsession(hass), region, username, password)
    except InvalidCredentials as err:
        _LOGGER.error("Login EP Cube rifiutato: %s", err)
        errors["base"] = "invalid_auth"
    except CaptchaFailed as err:
        _LOGGER.error("Login EP Cube: %s", err)
        errors["base"] = "captcha_failed"
    except EpCubeLoginError as err:
        _LOGGER.error("Login EP Cube: %s", err)
        errors["base"] = "connection_error"
    except Exception:
        _LOGGER.exception("Errore inatteso nel login EP Cube")
        errors["base"] = "unknown_error"
    return None


class EpCubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._errors = {}

    async def async_step_user(self, user_input=None):
        set_api_language(self.hass.config.language)
        return self.async_show_menu(step_id="user", menu_options=["credentials", "token"])

    async def async_step_credentials(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            region = user_input["region"]
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            token = await _async_login_errors(self.hass, region, username, password, self._errors)
            if token:
                result = await self._async_create_for_token(token, region, {
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                })
                if result:
                    return result

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required("region", default="EU"): vol.In(REGIONS),
            }),
            errors=self._errors,
        )

    async def async_step_token(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            region = user_input["region"]
            token = user_input["token"].strip()
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            result = await self._async_create_for_token(token, region, {})
            if result:
                return result

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({
                vol.Required("token"): str,
                vol.Required("region", default="EU"): vol.In(REGIONS),
            }),
            errors=self._errors,
        )

    async def _async_create_for_token(self, token, region, extra_data):
        """Crea la entry per il dispositivo del token, None se c'è un errore."""
        sn = await self._get_sn_from_token(token, region)

        if not sn:
            # _get_sn_from_token ha già impostato l'errore specifico
            self._errors.setdefault("base", "sn_not_found")
            return None

        for entry in self._async_current_entries():
            if entry.data.get("sn") == sn:
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(sn)
        return self.async_create_entry(
            title=f"EpCube {sn}",
            data={
                "token": token,
                "sn": sn,
                "region": region,
                **extra_data,
            },
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Token scaduto o credenziali cambiate: nuovo login con email e password."""
        self._errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        region = entry.options.get("region") or entry.data.get("region", "EU")

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            token = await _async_login_errors(self.hass, region, username, password, self._errors)
            if token:
                sn = await self._get_sn_from_token(token, region)
                if sn and sn != entry.data.get("sn"):
                    self._errors["base"] = "wrong_account"
                elif sn:
                    if "token" in entry.options:
                        self.hass.config_entries.async_update_entry(
                            entry, options={**entry.options, "token": token}
                        )
                    return self.async_update_reload_and_abort(entry, data={
                        **entry.data,
                        "token": token,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    })

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=self._errors,
        )

    async def _get_sn_from_token(self, token, region):
        base_url = get_base_url(region)
        url = f"{base_url}/user/user/base"
        headers = {
            "accept": "*/*",
            "accept-language": api_language(),
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
                            data = await response.json(content_type=None)
                            _LOGGER.debug("Risposta user/base: %s", data)

                            # I server US/JP incapsulano gli errori in una risposta
                            # HTTP 200 con lo stato reale nel corpo (es. token di
                            # un'altra regione -> status 403 "User token expired")
                            api_status = data.get("status")
                            if api_status is not None and int(api_status) != 200:
                                api_message = data.get("message", "")
                                _LOGGER.error(
                                    "Errore API %s su %s: %s", api_status, base_url, api_message
                                )
                                if int(api_status) in (401, 403):
                                    self._errors["base"] = "invalid_token"
                                elif int(api_status) >= 500:
                                    self._errors["base"] = "server_error"
                                else:
                                    self._errors["base"] = "http_error"
                                return None

                            sn = (data.get("data") or {}).get("defDevSgSn")
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
        errors = {}
        entry = self._config_entry

        if user_input is not None:
            token = user_input.get("token", "").strip()
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            region = user_input.get("region", entry.data.get("region", "EU"))

            # Password inserita: nuovo login, così il token si rinnova da solo
            password = user_input.get(CONF_PASSWORD)
            username = (user_input.get(CONF_USERNAME) or "").strip()
            if password:
                if not username:
                    errors["base"] = "missing_username"
                else:
                    new_token = await _async_login_errors(
                        self.hass, region, username, password, errors
                    )
                    if new_token:
                        token = new_token
                        self.hass.config_entries.async_update_entry(entry, data={
                            **entry.data,
                            "token": token,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        })

            if not errors:
                return self.async_create_entry(title="", data={
                    "token": token,
                    "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                    CONF_SCALE_POWER: user_input.get(CONF_SCALE_POWER, False),
                    CONF_ENABLE_TOTAL: user_input.get(CONF_ENABLE_TOTAL, False),
                    CONF_ENABLE_ANNUAL: user_input.get(CONF_ENABLE_ANNUAL, False),
                    CONF_ENABLE_MONTHLY: user_input.get(CONF_ENABLE_MONTHLY, False),
                    "region": region,
                })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional("token", default=entry.options.get("token") or entry.data.get("token")): str,
                vol.Optional("scan_interval", default=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
                vol.Optional(CONF_ENABLE_TOTAL, default=entry.options.get(CONF_ENABLE_TOTAL, False)): bool,
                vol.Optional(CONF_ENABLE_ANNUAL, default=entry.options.get(CONF_ENABLE_ANNUAL, False)): bool,
                vol.Optional(CONF_ENABLE_MONTHLY, default=entry.options.get(CONF_ENABLE_MONTHLY, False)): bool,
                vol.Optional("region", default=entry.data.get("region", "EU")): vol.In(REGIONS),
            }),
            errors=errors,
        )
