"""mitmproxy: mostra nell'app EP Cube la lavatrice LG e la ChargePoint, con i dati di Home Assistant.

Esperimento: funziona solo sul telefono che passa dal proxy. Il cloud EP Cube
non sa nulla di questi dispositivi; le risposte le costruisce questo script.

Lavatrice LG come dispositivo "Home Connect":
- user/user/base: extendPermissions.device -> voce Home Connect in Partenariato;
- device/homeDeviceInfo: homeConnectAuth + homeConnectDevices -> carico in Home;
- extend/devices, extend/syncDevices: la lavatrice, con Smart Start = avvio
  remoto LG (binary_sensor.lavatrice_avvio_remoto);
- extend/device/plan: il lavaggio in corso (running/paused), altrimenti l'ultimo
  concluso (completed);
- extend/device/schedule/history: i lavaggi degli ultimi 7 giorni da sensor.lavatrice_stato_attuale;
- extend/device/switch: l'interruttore "EP Cube gestisce" viene ricordato in
  tools/epcube_sim_state.json (non avvia la lavatrice).

ChargePoint come caricatore EV:
- user/user/base: tblDevice.hasEvse = true (il permesso KEBA lo forza mitm_epcube_keba.py);
- device/homeDeviceInfo e device/refreshData: hasEvse, evseOnline e potenza EV
  -> icona Caricatore EV e flusso verso l'auto in Home;
- device/evse/homeInfo: stato, potenza, energia e durata della sessione;
- device/evse/getEvseSettings: nome, versione firmware, limiti di corrente;
- device/evse/getEvseMode: modalità di ricarica (quella scelta nell'app, ricordata);
- device/evse/chargeRecord: sessioni di ricarica dalla cronologia HA;
- device/evse/graphData: potenza del giorno, energia per giorno del mese o per mese dell'anno;
- comandi che agiscono davvero sulla ChargePoint tramite HA:
  startQuickCharge -> start_charging, stopCharger -> stop_charging,
  settings (maxChargeCurrent) -> charging_amperage_limit.

Il token di Home Assistant si legge da tools/ha_token.txt (escluso da git).

Uso:

    mitmweb --listen-port 8888 --ignore-hosts "192\\.168\\." \\
        -s tools/mitm_epcube_keba.py -s tools/mitm_epcube_sim.py
"""

import json
import threading
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from mitmproxy import ctx, http

HERE = Path(__file__).parent
HA_URL = "http://192.168.178.101:8123"
HA_TOKEN_FILE = HERE / "ha_token.txt"
LOG_FILE = HERE / "epcube_sim_log.jsonl"
STATE_FILE = HERE / "epcube_sim_state.json"

EPCUBE_HOSTS = ("epcube.com", "epcube-monitoring.com")
PLATFORM = "hc"
FAKE_PREFIX = "/hcfake"
TIME_FMT = "%Y-%m-%d %H:%M:%S"

WASHER_ID = "LG-LAVATRICE-1"
WASHER_NAME = "Lavatrice LG"
WASHER_ENTITIES = {
    "remote": "binary_sensor.lavatrice_avvio_remoto",
    "state": "sensor.lavatrice_stato_attuale",
    "remaining": "sensor.lavatrice_tempo_rimanente",
}
# Stati ThinQ in cui un lavaggio è in corso (gli altri: power_off, end, initial, sleep, error)
WASHER_ACTIVE = {"detecting", "running", "rinsing", "spinning", "drying", "steam_softening",
                 "cool_down", "refreshing", "pause", "rinse_hold", "reserved"}

EV_NAME = "ChargePoint Home"
EV_SN = "CP830-14053A"
EV_MODEL = "CP830"
EV_PREFIX = "cp_home_14053a_cp830_"
EV_ENTITIES = {
    "status": f"sensor.{EV_PREFIX}charging_status",
    "cable": f"sensor.{EV_PREFIX}charging_cable",
    "network": f"sensor.{EV_PREFIX}network",
    "power": f"sensor.{EV_PREFIX}power_output",      # kW
    "energy": f"sensor.{EV_PREFIX}energy_output",    # kWh della sessione, si azzera allo stacco
    "time": f"sensor.{EV_PREFIX}charging_time",      # s
    "amperage": f"select.{EV_PREFIX}charging_amperage_limit",
    "update": "update.chargepoint_update",
}
EV_BUTTON_START = f"button.{EV_PREFIX}start_charging"
EV_BUTTON_STOP = f"button.{EV_PREFIX}stop_charging"
EV_HISTORY_DAYS = 400

POLL_SECONDS = 15
HISTORY_SECONDS = 300


# ---------------------------------------------------------------- Home Assistant

class HomeAssistant:
    """Legge stati e cronologia da HA in un thread, così il proxy non aspetta mai."""

    def __init__(self):
        self.token = HA_TOKEN_FILE.read_text().strip() if HA_TOKEN_FILE.exists() else ""
        self.states = {}
        self.washer_cycles = []
        self.ev_status = []    # [(datetime, stato)]
        self.ev_energy = []    # [(datetime, kWh)]
        self.ev_power = []     # [(datetime, kW)]
        self._history_at = 0.0
        if self.token:
            threading.Thread(target=self._loop, daemon=True).start()
        else:
            ctx.log.warn("[sim] tools/ha_token.txt mancante: uso solo valori fissi")

    def _request(self, path, body=None):
        req = urllib.request.Request(
            HA_URL + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read() or b"null")

    def _history(self, entity_id, days):
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).isoformat()
        # Senza end_time HA restituisce solo le 24 ore dopo start
        data = self._request(
            f"/api/history/period/{quote(start)}?end_time={quote(now.isoformat())}"
            f"&filter_entity_id={entity_id}&minimal_response&no_attributes"
        )
        return [(datetime.fromisoformat(x["last_changed"]).astimezone(), x["state"])
                for x in (data[0] if data else [])]

    def _loop(self):
        wanted = set(WASHER_ENTITIES.values()) | set(EV_ENTITIES.values())
        while True:
            try:
                self.states = {s["entity_id"]: s for s in self._request("/api/states")
                               if s["entity_id"] in wanted}
                if time.monotonic() - self._history_at > HISTORY_SECONDS:
                    self._refresh_history()
                    self._history_at = time.monotonic()
            except Exception as err:  # noqa: BLE001 - un errore di rete non deve fermare il proxy
                ctx.log.warn(f"[sim] Home Assistant non raggiungibile: {err}")
            time.sleep(POLL_SECONDS)

    def _refresh_history(self):
        cycles, on_since = [], None
        for changed, state in self._history(WASHER_ENTITIES["state"], 7):
            active = state in WASHER_ACTIVE
            if active and on_since is None:
                on_since = changed
            elif not active and on_since is not None:
                cycles.append((on_since, changed))
                on_since = None
        if on_since is not None:
            cycles.append((on_since, None))
        self.washer_cycles = cycles
        self.ev_status = self._history(EV_ENTITIES["status"], EV_HISTORY_DAYS)
        self.ev_energy = _numeric(self._history(EV_ENTITIES["energy"], EV_HISTORY_DAYS))
        self.ev_power = _numeric(self._history(EV_ENTITIES["power"], EV_HISTORY_DAYS))

    def call(self, domain, service, data):
        """Chiama un servizio HA; restituisce True se è andato a buon fine."""
        try:
            self._request(f"/api/services/{domain}/{service}", data)
            ctx.log.info(f"[sim] HA {domain}.{service} {data}")
            return True
        except Exception as err:  # noqa: BLE001
            ctx.log.warn(f"[sim] HA {domain}.{service} fallito: {err}")
            return False

    def state(self, entity_id, default=None):
        s = self.states.get(entity_id)
        return s["state"] if s else default

    def attr(self, entity_id, name, default=None):
        s = self.states.get(entity_id)
        return (s.get("attributes") or {}).get(name, default) if s else default

    def number(self, entity_id, default=0.0):
        try:
            return float(self.state(entity_id))
        except (TypeError, ValueError):
            return default


def _numeric(rows):
    out = []
    for changed, state in rows:
        try:
            out.append((changed, float(state)))
        except ValueError:
            pass
    return out


HA = None


def load(loader):
    global HA
    HA = HomeAssistant()


# ---------------------------------------------------------------- utilità

def _is_epcube(flow: http.HTTPFlow) -> bool:
    return any(h in flow.request.pretty_host for h in EPCUBE_HOSTS)


def _json(content: bytes):
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def _log(kind: str, flow: http.HTTPFlow, extra=None) -> None:
    entry = {
        "time": time.strftime(TIME_FMT),
        "kind": kind,
        "method": flow.request.method,
        "path": flow.request.path,
        "request": _json(flow.request.content) or flow.request.get_text(strict=False),
    }
    if extra is not None:
        entry["extra"] = extra
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _ok(flow: http.HTTPFlow, data, **extra) -> None:
    """Risposta nel formato BaseBean dell'API EP Cube."""
    body = {"timestamp": time.strftime(TIME_FMT), "message": "Success", "status": 200,
            "data": data, "pattern": "yyyy-MM-dd HH:mm:ss", **extra}
    flow.response = http.Response.make(
        200, json.dumps(body, ensure_ascii=False), {"Content-Type": "application/json;charset=UTF-8"}
    )


def _read_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _update_state(**values):
    state = _read_state()
    state.update(values)
    STATE_FILE.write_text(json.dumps(state))
    return state


def _fmt(moment):
    return moment.strftime(TIME_FMT) if moment else ""


# ---------------------------------------------------------------- lavatrice

def _washer_smart_start():
    return "on" if HA.state(WASHER_ENTITIES["remote"]) == "on" else "off"


def _washer_device():
    return {
        "platform": PLATFORM,
        "deviceId": WASHER_ID,
        "deviceName": WASHER_NAME,
        "deviceType": "Washer",
        "enabled": _washer_smart_start(),
        "pictureUrl": "",
        "toggleSubscribe": _read_state().get("toggleSubscribe", 1),
    }


def _remaining_minutes():
    """sensor.lavatrice_tempo_rimanente può essere 'H:MM:SS', minuti o una data."""
    raw = HA.state(WASHER_ENTITIES["remaining"])
    if not raw or raw in ("unknown", "unavailable"):
        return None
    if ":" in raw and "T" not in raw:
        parts = [int(p) for p in raw.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        return parts[0] * 60 + parts[1] + parts[2] / 60
    try:
        return float(raw)
    except ValueError:
        try:
            end = datetime.fromisoformat(raw)
            return max((end - datetime.now(end.tzinfo)).total_seconds() / 60, 0)
        except ValueError:
            return None


def _washer_real_cycles():
    # Gli stati che rimbalzano per pochi secondi non sono lavaggi
    return [c for c in HA.washer_cycles
            if c[1] is None or c[1] - c[0] >= timedelta(minutes=2)]


def _washer_plan():
    """Piano mostrato dall'app: lavaggio in corso, altrimenti l'ultimo concluso."""
    state = HA.state(WASHER_ENTITIES["state"])
    cycles = _washer_real_cycles()
    plan = None
    if state in WASHER_ACTIVE:
        current = next((c for c in cycles if c[1] is None), None)
        start = current[0] if current else datetime.now().astimezone()
        minutes = _remaining_minutes()
        end = (datetime.now().astimezone() + timedelta(minutes=minutes)
               if minutes is not None else start + timedelta(hours=2))
        window = {"start": _fmt(start), "end": _fmt(end)}
        plan = {"status": "paused" if state == "pause" else "running",
                "preferenceTime": window, "scheduledTime": dict(window)}
    else:
        done = [c for c in cycles if c[1] is not None]
        if done:
            start, end = done[-1]
            window = {"start": _fmt(start), "end": _fmt(end)}
            plan = {"status": "completed", "preferenceTime": window, "scheduledTime": dict(window)}
    return [{"deviceId": WASHER_ID, "name": WASHER_NAME,
             "smartStart": _washer_smart_start(), "plan": plan}]


def _washer_history():
    rows = []
    for i, (start, end) in enumerate(reversed(_washer_real_cycles())):
        rows.append({"id": str(i + 1), "platform": PLATFORM, "deviceId": WASHER_ID,
                     "start": _fmt(start), "end": _fmt(end),
                     "status": "completed" if end else "running"})
    return rows


# ---------------------------------------------------------------- ChargePoint

def _ev_online():
    return HA.state(EV_ENTITIES["network"]) == "Connected"


def _ev_power_w():
    return HA.number(EV_ENTITIES["power"]) * 1000 if _ev_online() else 0.0


def _ev_charge_status():
    """Codici dell'app: 0 avvio, 1 libero, 2 in preparazione, 3 in carica, 4 guasto, 5 in pausa."""
    status = (HA.state(EV_ENTITIES["status"]) or "").lower()
    if not _ev_online():
        return 1
    if "fault" in status or "error" in status:
        return 4
    if status == "charging" or _ev_power_w() > 0:
        return 3
    if HA.state(EV_ENTITIES["cable"]) == "Plugged In":
        return 5
    return 1


def _ev_mode():
    return _read_state().get("evseWorkStatus", "1")


def _ev_home_info():
    return {
        "name": EV_NAME,
        "status": 1,
        "workStatus": 1,
        "gridStatus": "1",
        "evseOnline": _ev_online(),
        "evseWorkStatus": _ev_mode(),
        "quickChargeStatus": _read_state().get("quickChargeStatus", 0),
        "stopStatus": 0,
        "chargeStatus": _ev_charge_status(),
        "chargePower": round(_ev_power_w(), 1),                               # W
        "chargeElectric": round(HA.number(EV_ENTITIES["energy"]) * 1000, 1),  # Wh
        "chargeTime": int(HA.number(EV_ENTITIES["time"])),                    # s
        "timestamp": time.strftime(TIME_FMT),
    }


def _ev_amperage_options():
    options = HA.attr(EV_ENTITIES["amperage"], "options") or []
    return sorted(int(o) for o in options if str(o).isdigit())


def _ev_settings(dev_id):
    options = _ev_amperage_options()
    state = _read_state()
    first_seen = HA.ev_status[0][0] if HA.ev_status else None
    return {
        "devId": dev_id,
        "name": EV_NAME,
        "sn": EV_SN,
        "firmwareVersion": HA.attr(EV_ENTITIES["update"], "installed_version") or "--",
        "hardwareVersion": EV_MODEL,
        "installTime": _fmt(first_seen),
        "maxRatedCurrent": options[-1] if options else 32,                    # A
        "maxChargeCurrent": int(HA.number(EV_ENTITIES["amperage"], 16) * 1000),  # mA
        "failsafeTimeout": state.get("failsafeTimeout", 10),
        "failsafeCurrent": state.get("failsafeCurrent", 6000),               # mA
        "batteryBoost": state.get("batteryBoost", 0),
    }


def _ev_mode_info(dev_id):
    return {
        "devId": dev_id,
        "evseWorkStatus": _ev_mode(),
        "quickChargeStatus": _read_state().get("quickChargeStatus", 0),
        # Tutti valorizzati: l'app iOS va in crash se questi campi sono null
        "scheduleModeData": [],
        "chargingLimitSoc": 100,
        "backupPowerReserveSoc": "50",
        "selfConsumptioinReserveSoc": "10",
        "sellingLimit": 0,
        "sellingLimitPower": "0",
        "dynamicChargePrice": "0",
        "dynamicDischargePrice": "0",
    }


def _ev_sessions():
    """Sessioni dalla cronologia: dal primo stato di carica dopo 'Available' al ritorno ad 'Available'."""
    sessions, current, charging_since = [], None, None
    now = datetime.now().astimezone()
    for changed, state in HA.ev_status:
        if state in ("unavailable", "unknown"):
            continue
        if state == "Available":
            if current is not None:
                if charging_since:
                    current["charging"] += (changed - charging_since).total_seconds()
                    charging_since = None
                current["end"] = changed
                sessions.append(current)
                current = None
            continue
        if current is None:
            current = {"start": changed, "end": None, "charging": 0.0}
        if state == "Charging" and charging_since is None:
            charging_since = changed
        elif state != "Charging" and charging_since is not None:
            current["charging"] += (changed - charging_since).total_seconds()
            charging_since = None
    if current is not None:
        if charging_since:
            current["charging"] += (now - charging_since).total_seconds()
        sessions.append(current)
    for s in sessions:
        end = s["end"] or now
        values = [v for t, v in HA.ev_energy if s["start"] <= t <= end]
        s["energy_kwh"] = max(values) if values else 0.0
    return sessions


def _ev_charge_records(dev_id, page_no, page_size):
    sessions = list(reversed(_ev_sessions()))
    rows = []
    for i, s in enumerate(sessions):
        rows.append({
            "id": str(len(sessions) - i),
            "devId": dev_id,
            "evseSn": EV_SN,
            "startTime": _fmt(s["start"]),
            "endTime": _fmt(s["end"]),
            "chargeElectric": round(s["energy_kwh"] * 1000, 1),   # Wh
            "chargeTime": int(s["charging"]),                     # s
            "chargeStatus": 3 if s["end"] is None else 1,
            "chargeNum": len(sessions) - i,
            "timestamp": _fmt(s["end"] or s["start"]),
        })
    first = (page_no - 1) * page_size
    page = {"pageNo": page_no, "pageSize": page_size,
            "pageTotal": (len(rows) + page_size - 1) // page_size}
    return rows[first:first + page_size], page


def _ev_energy_by(key):
    """kWh caricati raggruppati per key(datetime), dagli incrementi di energy_output."""
    totals, prev = defaultdict(float), None
    for changed, value in HA.ev_energy:
        if prev is not None and value >= prev:
            totals[key(changed)] += value - prev
        prev = value
    return totals


def _ev_graph(scope, day_str):
    """scopeType 1 = potenza del giorno, 2 = energia per giorno del mese, 3 = per mese dell'anno."""
    try:
        ref = datetime.strptime(day_str[:10], "%Y-%m-%d")
    except ValueError:
        ref = datetime.now()
    points = []
    if scope == "1":
        day = ref.date()
        for changed, kw in HA.ev_power:
            if changed.date() == day:
                points.append({"nodeName": changed.strftime("%H:%M"), "scopeType": scope,
                               "nodeVo": {"chargePower": round(kw * 1000, 1),
                                          "chargeElectric": None, "chargeTime": None}})
        totals = _ev_energy_by(lambda t: t.date())
        total_kwh = totals.get(day, 0.0)
        in_period = lambda t: t.date() == day  # noqa: E731
    elif scope == "2":
        totals = _ev_energy_by(lambda t: t.date())
        month_days = [d for d in totals if d.year == ref.year and d.month == ref.month]
        for d in sorted(month_days):
            points.append({"nodeName": d.strftime("%d"), "scopeType": scope,
                           "nodeVo": {"chargeElectric": round(totals[d] * 1000, 1),
                                      "chargePower": None, "chargeTime": None}})
        total_kwh = sum(totals[d] for d in month_days)
        in_period = lambda t: (t.year, t.month) == (ref.year, ref.month)  # noqa: E731
    else:
        totals = _ev_energy_by(lambda t: (t.year, t.month))
        months = [m for m in totals if m[0] == ref.year]
        for m in sorted(months):
            points.append({"nodeName": f"{m[1]:02d}", "scopeType": scope,
                           "nodeVo": {"chargeElectric": round(totals[m] * 1000, 1),
                                      "chargePower": None, "chargeTime": None}})
        total_kwh = sum(totals[m] for m in months)
        in_period = lambda t: t.year == ref.year  # noqa: E731
    # Durata: tempo con potenza > 0 nel periodo (anche per sessioni iniziate prima)
    charging_s = 0.0
    for (t0, kw), (t1, _) in zip(HA.ev_power, HA.ev_power[1:]):
        if kw > 0 and in_period(t0):
            charging_s += (t1 - t0).total_seconds()
    return {"graphData": points, "totalChargeElectric": round(total_kwh * 1000, 1),
            "totalChargeTime": str(int(charging_s))}


def _ev_set_amperage(milliamps):
    options = _ev_amperage_options()
    if not options:
        return False
    amps = min(max(round(milliamps / 1000), options[0]), options[-1])
    return HA.call("select", "select_option",
                   {"entity_id": EV_ENTITIES["amperage"], "option": str(amps)})


def _handle_evse(flow: http.HTTPFlow, path: str) -> None:
    query = flow.request.query
    body = _json(flow.request.content) or {}
    dev_id = str(query.get("devId") or body.get("devId") or path.rsplit("/", 1)[-1])
    if path.endswith("/homeInfo"):
        _ok(flow, _ev_home_info())
    elif path.endswith("/getEvseSettings"):
        _ok(flow, _ev_settings(dev_id))
    elif path.endswith("/getEvseMode"):
        _ok(flow, _ev_mode_info(dev_id))
    elif "/chargeRecord/" in path:
        page_no = int(query.get("pageNo", 1))
        page_size = int(query.get("pageSize", 10))
        rows, page = _ev_charge_records(dev_id, page_no, page_size)
        _ok(flow, rows, page=page)
    elif path.endswith("/graphData"):
        _ok(flow, _ev_graph(str(query.get("scopeType", "1")), query.get("queryDateStr", "")))
    elif path.endswith("/getStopAfterQueryStatus"):
        _ok(flow, 0)
    elif path.endswith("/startQuickCharge"):
        _update_state(quickChargeStatus=1)
        HA.call("button", "press", {"entity_id": EV_BUTTON_START})
        _ok(flow, None)
    elif path.endswith("/stopCharger"):
        _update_state(quickChargeStatus=0)
        HA.call("button", "press", {"entity_id": EV_BUTTON_STOP})
        _ok(flow, "")
    elif path.endswith("/switchMode"):
        mode = body.get("evseWorkStatus")
        if mode is not None:
            _update_state(evseWorkStatus=str(mode), quickChargeStatus=0)
        _ok(flow, "")
    elif path.endswith("/settings"):
        values = {k: body[k] for k in ("failsafeTimeout", "failsafeCurrent", "batteryBoost")
                  if k in body}
        if values:
            _update_state(**values)
        if body.get("maxChargeCurrent") is not None:
            _ev_set_amperage(float(body["maxChargeCurrent"]))
        _ok(flow, None)
    else:
        # add, unbind, ...: confermati senza fare nulla
        _ok(flow, None)


# ---------------------------------------------------------------- hook mitmproxy

def request(flow: http.HTTPFlow) -> None:
    if not _is_epcube(flow) or HA is None:
        return
    path = flow.request.path.split("?")[0]

    # Finto login Home Connect: rimanda subito a redirect_uri?code=...
    if path.startswith(FAKE_PREFIX + "/auth"):
        target = f"{flow.request.query.get('redirect_uri', '')}?code=simulato&state=epcube"
        html = ("<!doctype html><meta name=viewport content='width=device-width'>"
                "<body style='font-family:sans-serif;background:#111;color:#eee;padding:24px'>"
                "<h3>Home Connect simulato</h3><p>Collegamento della lavatrice LG...</p>"
                f"<p><a style='color:#8cdfa5' href='{target}'>Continua</a></p>"
                f"<script>setTimeout(function(){{location.href={json.dumps(target)};}},800)</script>")
        flow.response = http.Response.make(200, html, {"Content-Type": "text/html; charset=utf-8"})
        return
    if path.startswith(FAKE_PREFIX + "/done"):
        flow.response = http.Response.make(200, "ok", {"Content-Type": "text/plain"})
        return

    if "/extend/" in path:
        _log("extend", flow)
        if path.endswith("/extend/auth/getPlatform"):
            host = flow.request.pretty_host
            redirect = quote(f"https://{host}{FAKE_PREFIX}/done", safe="")
            _ok(flow, {"platform": PLATFORM, "clientId": "simulato", "state": "epcube",
                       "fullAuthUrl": f"https://{host}{FAKE_PREFIX}/auth?redirect_uri={redirect}"})
        elif path.endswith("/extend/devices") or path.endswith("/extend/syncDevices"):
            _ok(flow, [_washer_device()])
        elif path.endswith("/extend/device/plan"):
            _ok(flow, _washer_plan())
        elif path.endswith("/extend/device/schedule/history"):
            _ok(flow, _washer_history())
        elif path.endswith("/extend/device/switch"):
            current = _read_state().get("toggleSubscribe", 1)
            state = _update_state(toggleSubscribe=0 if current == 1 else 1)
            ctx.log.info(f"[sim] EP Cube gestisce la lavatrice: {state['toggleSubscribe']}")
            _ok(flow, None)
        else:
            _ok(flow, None)
        return

    if "/device/evse/" in path:
        _log("evse", flow)
        _handle_evse(flow, path)


def response(flow: http.HTTPFlow) -> None:
    if flow.response is None or not _is_epcube(flow) or HA is None:
        return
    path = flow.request.path.split("?")[0]
    if not path.endswith(("/user/user/base", "/device/homeDeviceInfo", "/device/refreshData")):
        return
    body = _json(flow.response.content)
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        return
    data = body["data"]
    ev_flow = round(_ev_power_w() / 10, 1)  # l'API usa decine di watt

    if path.endswith("/user/user/base"):
        perms = data.get("extendPermissions")
        if not isinstance(perms, dict):
            perms = data["extendPermissions"] = {}
        perms["device"] = [{"extendPlatform": PLATFORM, "hasPermission": "1"}]
        if isinstance(data.get("tblDevice"), dict):
            data["tblDevice"]["hasEvse"] = True
    elif path.endswith("/device/homeDeviceInfo"):
        data["homeConnectAuth"] = "1"
        data["homeConnectDevices"] = [{"extendPlatform": PLATFORM, "name": WASHER_NAME,
                                       "deviceType": "Washer", "enabled": _washer_smart_start()}]
        data["hasEvse"] = True
        data["evseOnline"] = _ev_online()
        data["evPower"] = ev_flow
        data["evFlowPower"] = ev_flow
        data["evLight"] = 1 if ev_flow > 0 else 0
    else:  # device/refreshData
        data["evFlowPower"] = ev_flow
    flow.response.text = json.dumps(body, ensure_ascii=False)
