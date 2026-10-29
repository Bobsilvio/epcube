"""Login EP Cube con email e password.

Il login dell'app passa da un captcha a puzzle (slider orizzontale):

  1. POST /open/common/captcha/get    {clientUid}
     -> sfondo, tassello, secretKey, token del captcha
  2. si cerca la posizione x del tassello nello sfondo (correlazione
     normalizzata, come cv2.matchTemplate TM_CCOEFF_NORMED)
  3. POST /open/common/captcha/check  {clientUid, token, pointJson}
     pointJson = AES-ECB(secretKey, {"x":..,"y":5}) in base64
  4. POST /open/common/login          {userName, password, captchaVerification}
     captchaVerification = AES-ECB(secretKey, "<token>---{"x":..,"y":5}")

Stesso flusso di epcube-token (https://github.com/Bobsilvio/epcube-token),
portato in asincrono e senza opencv. Un tentativo di captcha riesce circa
4 volte su 5, per questo se ne fanno più di uno.

Quando il token scade (401/403) async_refresh_token rifà il login con le
credenziali salvate nella entry e aggiorna il token salvato.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from io import BytesIO

import aiohttp
import numpy as np
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, USER_AGENT, HTTP_TIMEOUT, HTTP_CONNECT_TIMEOUT, get_base_url,
    CONF_USERNAME, CONF_PASSWORD, api_language,
)

_LOGGER = logging.getLogger(__name__)

CAPTCHA_ATTEMPTS = 3
# Lo slider è solo orizzontale: il server valida la x, la y è fissa
CAPTCHA_Y = 5
# Dopo un re-login fallito non si riprova prima di questo intervallo, altrimenti
# con scan_interval di pochi secondi si risolverebbero captcha a raffica
RELOGIN_COOLDOWN = 60  # seconds

def _headers():
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "accept-language": api_language(),
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
    }


class EpCubeLoginError(Exception):
    """Errore generico di login."""


class InvalidCredentials(EpCubeLoginError):
    """Email o password rifiutate dal server."""


class CaptchaFailed(EpCubeLoginError):
    """Nessun tentativo di captcha è stato accettato."""


class CannotConnect(EpCubeLoginError):
    """Server non raggiungibile o risposta non valida."""


def has_credentials(entry) -> bool:
    return bool(entry.data.get(CONF_USERNAME) and entry.data.get(CONF_PASSWORD))


async def async_login(session, region, username, password, attempts=CAPTCHA_ATTEMPTS):
    """Esegue il login completo e restituisce il token già nel formato 'Bearer ...'."""
    base_url = get_base_url(region)
    loop = asyncio.get_running_loop()
    last_error = None

    for attempt in range(1, attempts + 1):
        client_uid = str(uuid.uuid4())
        rep = await _post(session, f"{base_url}/open/common/captcha/get", {"clientUid": client_uid})
        rep_data = (rep.get("data") or {}).get("repData") or {}
        try:
            background = rep_data["originalImageBase64"]
            piece = rep_data["jigsawImageBase64"]
            secret_key = rep_data["secretKey"]
            captcha_token = rep_data["token"]
        except KeyError as err:
            raise CannotConnect(f"Risposta captcha/get incompleta: manca {err}") from err

        try:
            x = await loop.run_in_executor(None, solve_captcha, background, piece)
        except Exception as err:  # immagini illeggibili: si prova un altro captcha
            _LOGGER.debug("Captcha %d/%d non risolvibile: %s", attempt, attempts, err)
            last_error = str(err)
            continue

        point = json.dumps({"x": float(x), "y": float(CAPTCHA_Y)}, separators=(",", ":"))
        check = await _post(session, f"{base_url}/open/common/captcha/check", {
            "clientUid": client_uid,
            "token": captcha_token,
            "pointJson": _aes_ecb_b64(point, secret_key),
        })
        if not _captcha_accepted(check):
            data = check.get("data") if isinstance(check.get("data"), dict) else {}
            last_error = data.get("repMsg") or f"repCode {data.get('repCode')}"
            _LOGGER.debug("Captcha %d/%d rifiutato: %s", attempt, attempts, last_error)
            continue

        login = await _post(session, f"{base_url}/open/common/login", {
            "userName": username,
            "password": password,
            "captchaVerification": _aes_ecb_b64(f"{captcha_token}---{point}", secret_key),
        })
        token = (login.get("data") or {}).get("token") if isinstance(login.get("data"), dict) else None
        if not token:
            raise InvalidCredentials(login.get("message") or "Login rifiutato")
        _LOGGER.debug("Login EP Cube riuscito al tentativo captcha %d/%d", attempt, attempts)
        return token if token.startswith("Bearer ") else f"Bearer {token}"

    raise CaptchaFailed(f"Captcha non superato dopo {attempts} tentativi ({last_error})")


async def async_refresh_token(hass, entry):
    """Rifà il login con le credenziali della entry e salva il nuovo token.

    Restituisce il nuovo token, oppure None se la entry non ha credenziali o se
    un tentativo è fallito da poco. Solleva InvalidCredentials se il server
    rifiuta email/password. Un solo login alla volta per entry: chi arriva
    mentre è in corso riceve il token appena ottenuto.
    """
    if not has_credentials(entry):
        return None

    # Fuori da hass.data[DOMAIN], che i servizi scorrono come elenco di entry
    auth_state = hass.data.setdefault(f"{DOMAIN}_auth", {}).setdefault(
        entry.entry_id, {"lock": asyncio.Lock(), "failed_at": 0.0}
    )
    old_token = entry.options.get("token") or entry.data.get("token")

    async with auth_state["lock"]:
        current = entry.options.get("token") or entry.data.get("token")
        if current != old_token:
            return current  # rinnovato da un'altra chiamata mentre aspettavamo
        if time.monotonic() - auth_state["failed_at"] < RELOGIN_COOLDOWN:
            return None

        region = entry.options.get("region") or entry.data.get("region", "EU")
        try:
            token = await async_login(
                async_get_clientsession(hass), region,
                entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
            )
        except InvalidCredentials:
            auth_state["failed_at"] = time.monotonic()
            raise
        except (EpCubeLoginError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            auth_state["failed_at"] = time.monotonic()
            _LOGGER.warning("Rinnovo token EP Cube fallito: %s", err)
            return None

        options = dict(entry.options)
        if "token" in options:
            options["token"] = token
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "token": token}, options=options
        )
        _LOGGER.info("Token EP Cube rinnovato con un nuovo login")
        return token


def solve_captcha(background_b64, piece_b64) -> int:
    """Restituisce la x (bordo sinistro) del tassello nello sfondo."""
    background = _to_gray(background_b64)
    piece = _to_gray(piece_b64)

    # A volte lo sfondo arriva di qualche pixel più basso del tassello:
    # lo si allunga con il suo valore medio per poter fare il confronto
    missing_rows = piece.shape[0] - background.shape[0]
    if 0 < missing_rows <= 4:
        top = missing_rows // 2
        background = np.pad(
            background, ((top, missing_rows - top), (0, 0)),
            mode="constant", constant_values=background.mean(),
        )
    if piece.shape[0] > background.shape[0] or piece.shape[1] > background.shape[1]:
        raise ValueError(f"tassello {piece.shape} più grande dello sfondo {background.shape}")

    scores = _match_template(background, piece)
    _, x = np.unravel_index(int(scores.argmax()), scores.shape)
    return int(x)


def _to_gray(b64) -> np.ndarray:
    img = Image.open(BytesIO(base64.b64decode(b64)))
    if img.mode == "P":
        # Sfondi a palette: gli indici della palette correlano col tassello
        # meglio della luminanza ricostruita
        return np.asarray(img, dtype=np.float64)
    rgb = np.asarray(img.convert("RGB"), dtype=np.float64)
    return rgb @ np.array([0.299, 0.587, 0.114])


def _match_template(image: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Correlazione incrociata normalizzata a media nulla (TM_CCOEFF_NORMED).

    Il numeratore è una correlazione col template a media nulla, calcolata via
    FFT; il denominatore usa somme cumulative per media e varianza di ogni
    finestra dell'immagine.
    """
    ih, iw = image.shape
    th, tw = template.shape
    n = th * tw

    t = template - template.mean()
    t_energy = float((t * t).sum())

    shape = (ih + th - 1, iw + tw - 1)
    corr = np.fft.irfft2(
        np.fft.rfft2(image, shape) * np.fft.rfft2(t[::-1, ::-1], shape), shape
    )[th - 1:ih, tw - 1:iw]

    def window_sums(a):
        c = np.pad(a.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return c[th:, tw:] - c[:-th, tw:] - c[th:, :-tw] + c[:-th, :-tw]

    s = window_sums(image)
    var_n = np.maximum(window_sums(image * image) - s * s / n, 0.0)
    denom = np.sqrt(var_n * t_energy)
    return np.divide(corr, denom, out=np.zeros_like(corr), where=denom > 1e-9)


def _aes_ecb_b64(text: str, key: str) -> str:
    padder = padding.PKCS7(128).padder()
    data = padder.update(text.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key.encode("utf-8")), modes.ECB()).encryptor()
    return base64.b64encode(encryptor.update(data) + encryptor.finalize()).decode("utf-8")


def _captcha_accepted(check) -> bool:
    # Il "message" esterno vale "Success" anche col captcha sbagliato:
    # conta solo l'esito interno
    data = check.get("data")
    if not isinstance(data, dict):
        return False
    rep_data = data.get("repData")
    if isinstance(rep_data, dict) and rep_data.get("result") is True:
        return True
    return data.get("repCode") == "0000"


async def _post(session, url, payload) -> dict:
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)
    try:
        async with session.post(url, headers=_headers(), json=payload, timeout=timeout) as resp:
            # Gli errori applicativi (credenziali, captcha) arrivano come JSON
            # anche con status 4xx: si scarta solo l'errore del server
            if resp.status >= 500:
                raise CannotConnect(f"{url} ha risposto {resp.status}")
            body = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        raise CannotConnect(f"{url}: {err}") from err
    if not isinstance(body, dict):
        raise CannotConnect(f"{url}: risposta inattesa")
    return body
