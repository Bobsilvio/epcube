"""Endpoint aggiuntivi trovati nell'app Android EP Cube (2.6.2).

- /device/getSolarPvPower: potenza per stringa FV, letta a ogni aggiornamento.
- /device/getSettingsData: impostazioni del sistema (winter mode, weather
  watch, ricarica da rete, ...), lette a ogni aggiornamento perché sono la
  fonte che l'app usa per la pagina Impostazioni.
- /device/getDevPowerCutLog, /device/earningsGraph,
  /device/homeDeviceInfoWeather, /device/getAlertFaultList, /device/netWorkInfo,
  /user/user/queryFirmwareInfo: cambiano lentamente, quindi vengono letti al
  massimo ogni SLOW_EXTRAS_INTERVAL e tenuti in cache tra un giro e l'altro.
- /device/queryDataGraphV2 (serie a 5 minuti di oggi): potenza batteria
  misurata, da cui carica e scarica giornaliere; riletta ogni SERIES_INTERVAL.

Un endpoint che risponde 404 non esiste sul server della regione e non viene
più richiesto fino al reload (sul server EU getSettingsData ed earningsGraph).
"""

from .const import get_base_url, USER_AGENT, STATS_TIMEOUT

from datetime import date, datetime
from functools import partial
import aiohttp
import asyncio
import logging
import time

_LOGGER = logging.getLogger(__name__)

SLOW_EXTRAS_INTERVAL = 900  # seconds
POWER_CUT_LOG_SIZE = 10
ALERT_LOG_SIZE = 10


def _route(path):
    return path.split("?", 1)[0]


async def async_fetch_api_data(session, token, region, path, timeout=STATS_TIMEOUT, state=None):
    """GET su un endpoint dell'API: il campo data della risposta, None se fallisce.

    Con state, un endpoint che risponde 404 viene segnato come non disponibile
    sul server della regione e non viene più richiesto (es. getSettingsData ed
    earningsGraph sul server EU).
    """
    if state is not None and _route(path) in state.unsupported:
        return None
    url = f"{get_base_url(region)}{path}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": USER_AGENT,
        "authorization": token,
    }
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    _mark_unsupported(state, path)
                    return None
                if resp.status != 200:
                    _LOGGER.debug("GET %s: HTTP %s", path, resp.status)
                    return None
                body = await resp.json(content_type=None)
    except (asyncio.TimeoutError, aiohttp.ClientError, ValueError) as err:
        _LOGGER.debug("GET %s fallita: %s", path, err)
        return None
    if not isinstance(body, dict):
        return None
    status = body.get("status")
    if str(status) == "404":
        _mark_unsupported(state, path)
        return None
    if status is not None and str(status) != "200":
        _LOGGER.debug("GET %s: status %s %s", path, status, body.get("message"))
        return None
    return body.get("data")


def _mark_unsupported(state, path):
    route = _route(path)
    if state is not None and route not in state.unsupported:
        state.unsupported.add(route)
        _LOGGER.info("%s non esiste su questo server (404): non verrà più richiesto", route)


async def async_fetch_settings(session, token, region, dev_id, state=None):
    """Impostazioni di getSettingsData con chiavi in minuscolo."""
    data = await async_fetch_api_data(
        session, token, region, f"/device/getSettingsData?devId={dev_id}", state=state
    )
    if not isinstance(data, dict):
        return {}
    return {k.lower(): v for k, v in data.items()}


async def async_fetch_pv_power(session, token, region, dev_id):
    """Potenza per stringa FV in kW (getSolarPvPower): {"pv1power": 1.2, ...}."""
    data = await async_fetch_api_data(
        session, token, region, f"/device/getSolarPvPower?devId={dev_id}"
    )
    if isinstance(data, list):
        # Con più inverter ibridi l'app mostra una riga per inverter: qui si
        # usa il primo
        data = data[0] if data else None
    if not isinstance(data, dict):
        return {}
    return {k.lower(): v for k, v in data.items() if k.lower().startswith("pv")}


async def async_fetch_user_device(session, token, region):
    """Dispositivo corrente da user/user/base (tblDevice), come lo legge l'app."""
    data = await async_fetch_api_data(session, token, region, "/user/user/base")
    if not isinstance(data, dict) or not isinstance(data.get("tblDevice"), dict):
        return None
    return data["tblDevice"]


def firmware_number(device):
    """softwareVersion "V4.1.0" -> 410, come UserCurrentDeviceBean.getVersion()."""
    version = str((device or {}).get("softwareVersion") or "")
    digits = version.upper().replace("V", "").replace(".", "")
    return int(digits) if digits.isdigit() else 0


def is_new_tou(device, region="EU"):
    """L'app USA usa l'editor TOU a piani stagionali (touSettings) invece delle fasce.

    L'app EU (com.eternalplanetenergy.epcube.eu) non ha questo editor: usa
    sempre le fasce orarie.
    """
    if region != "US":
        return False
    return str(device.get("devType")) == "2" or firmware_number(device) >= 408


def has_winter_mode(device, region="EU"):
    """Condizione con cui l'app della regione mostra la modalità invernale."""
    version = firmware_number(device)
    if region == "US":
        if str(device.get("winterModePermission")) != "1":
            return False
        if str(device.get("devType")) == "2":
            return version in (14, 15) or version >= 20
        return version in (401, 402) or version >= 410
    # App EU 3.1.1: solo sistemi monofase con firmware 1.1.8 o successivo
    three_phase = str(device.get("devType")) in ("2", "3")
    return not three_phase and version >= 118


async def async_fetch_slow_extras(session, token, region, dev_id, sg_sn, state):
    """Log blackout, guadagni, meteo, avvisi, rete e firmware, con cache in state per SLOW_EXTRAS_INTERVAL."""
    if state.extras is not None and time.monotonic() - state.extras_at < SLOW_EXTRAS_INTERVAL:
        return state.extras

    now = datetime.now()
    fetch = partial(async_fetch_api_data, state=state)
    (power_cuts, earning_day, earning_month, weather,
     warnings, faults, network, firmware, user_device, upgrade) = await asyncio.gather(
        fetch(
            session, token, region,
            f"/device/getDevPowerCutLog?devId={dev_id}&pageNo=1&pageSize={POWER_CUT_LOG_SIZE}",
        ),
        fetch(
            session, token, region,
            f"/device/earningsGraph?devId={dev_id}&scopeType=1&queryDateStr={now:%Y-%m-%d}",
        ),
        fetch(
            session, token, region,
            f"/device/earningsGraph?devId={dev_id}&scopeType=2&queryDateStr={now:%Y-%m}",
        ),
        fetch(
            session, token, region, f"/device/homeDeviceInfoWeather?sgSn={sg_sn}&type=1"
        ),
        # Elenco avvisi e guasti: nell'app EU la scheda 1 è "Warning", la 2 "Fault"
        fetch(
            session, token, region,
            f"/device/getAlertFaultList/{dev_id}/1?pageNo=1&pageSize={ALERT_LOG_SIZE}",
        ),
        fetch(
            session, token, region,
            f"/device/getAlertFaultList/{dev_id}/2?pageNo=1&pageSize={ALERT_LOG_SIZE}",
        ),
        fetch(session, token, region, f"/device/netWorkInfo?devId={dev_id}"),
        fetch(session, token, region, f"/user/user/queryFirmwareInfo?devId={dev_id}"),
        async_fetch_user_device(session, token, region),
        # Firmware disponibile (canale installatore): newSoftWareVersion sul gateway.
        # Solo lettura; usato dall'entità update per segnalare un aggiornamento.
        fetch(
            session, token, region,
            f"/device/checkUpgrade?devId={dev_id}&type=2&forcedUpgrade=0",
        ),
    )

    extras = {
        "power_cuts": power_cuts if isinstance(power_cuts, list) else None,
        "earning_today": _earning_total(earning_day),
        "earning_month": _earning_total(earning_month),
        "weather": weather if isinstance(weather, dict) else None,
        "warnings": warnings if isinstance(warnings, list) else None,
        "faults": faults if isinstance(faults, list) else None,
        "network": network if isinstance(network, dict) else None,
        "firmware": firmware if isinstance(firmware, dict) else None,
        "user_device": user_device,
        "upgrade": upgrade if isinstance(upgrade, dict) else None,
    }
    # Un endpoint che fallisce mantiene l'ultimo valore buono
    if state.extras:
        for key, value in extras.items():
            if value is None:
                extras[key] = state.extras.get(key)
    state.extras = extras
    state.extras_at = time.monotonic()
    return extras


SERIES_INTERVAL = 600  # seconds
# Dopo un errore si riprova prima, senza aspettare l'intero intervallo
SERIES_RETRY = 60  # seconds
# Un punto della serie giornaliera copre 5 minuti
SERIES_STEP_H = 5 / 60


def battery_energy_from_series(points):
    """Carica e scarica (kWh) integrando batteryPower della serie a 5 minuti.

    batteryPower è la potenza media misurata dal gateway nell'intervallo, in
    kW: positiva in scarica, negativa in carica. I campi
    batteryChargeElectricity/batteryDischargeElectricity della stessa serie
    restano invece sempre a zero.
    Restituisce (carica, scarica, (ora, kW) dell'ultimo punto completo): il
    punto più recente è l'intervallo in corso e può valere ancora 0. Quando si
    completa, la differenza entra nei totali al giro successivo.
    """
    charge = discharge = 0.0
    readings = []
    for point in points or []:
        reading = (point or {}).get("nodeVo") or {}
        try:
            power = float(reading.get("batteryPower"))
        except (TypeError, ValueError):
            continue
        if power < 0:
            charge -= power * SERIES_STEP_H
        else:
            discharge += power * SERIES_STEP_H
        readings.append((point.get("nodeName"), power))
    return charge, discharge, readings[-2] if len(readings) >= 2 else None


async def _async_series_day(session, token, region, dev_id, day, state):
    points = await async_fetch_api_data(
        session, token, region,
        f"/device/queryDataGraphV2?devId={dev_id}&queryDateStr={day:%Y-%m-%d}&scopeType=1",
        state=state,
    )
    return battery_energy_from_series(points) if isinstance(points, list) else None


async def async_fetch_battery_series(session, token, region, dev_id, state):
    """Carica/scarica batteria misurate di oggi, rilette al massimo ogni SERIES_INTERVAL.

    Aggiorna anche i totali cumulativi in state (apply_series). Se il giorno
    contabilizzato è finito, rilegge la sua serie completa per chiuderlo.
    """
    today = date.today()
    if (
        state.series is not None
        and state.series["day"] == today
        and time.monotonic() - state.series_at < SERIES_INTERVAL
    ):
        return state.series

    result = await _async_series_day(session, token, region, dev_id, today, state)
    if result is None:
        state.series_at = time.monotonic() - SERIES_INTERVAL + SERIES_RETRY
        return state.series if state.series and state.series["day"] == today else None

    closing = None
    if state.series_day is not None and state.series_day != today:
        previous = await _async_series_day(
            session, token, region, dev_id, state.series_day, state
        )
        if previous is not None:
            closing = (state.series_day, previous[0], previous[1])

    charge, discharge, last = result
    state.apply_series(today, charge, discharge, closing)
    state.series = {"day": today, "charge": charge, "discharge": discharge, "last": last}
    state.series_at = time.monotonic()
    return state.series


def _earning_total(data):
    if not isinstance(data, dict) or data.get("earningTotal") is None:
        return None
    try:
        return float(data["earningTotal"])
    except (TypeError, ValueError):
        return None
