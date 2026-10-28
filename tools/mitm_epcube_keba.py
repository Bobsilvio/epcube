"""mitmproxy: mostra la sezione wallbox (KEBA) nell'app EP Cube e registra le chiamate EV.

Uso (stessa configurazione WireGuard dello sniffing):

    mitmweb --mode wireguard -s tools/mitm_epcube_keba.py

Cosa fa, solo sul traffico del tuo telefono:
- nella risposta di user/user/base imposta tblDevice.kebaAuthority = "1",
  il flag con cui l'app EU decide se mostrare la funzione wallbox;
- registra in tools/epcube_ev_log.jsonl richiesta e risposta di ogni chiamata
  che riguarda la wallbox (device/send/query, device/send/set, ...).

Non modifica nient'altro e non invia nulla di suo.
"""

import json
import time
from pathlib import Path

from mitmproxy import ctx, http

EPCUBE_HOSTS = ("epcube.com", "epcube-monitoring.com")
LOG_FILE = Path(__file__).with_name("epcube_ev_log.jsonl")
# Chiamate da registrare: comandi Modbus inoltrati al gateway e dati wallbox
EV_PATHS = ("/device/send/", "evse", "Evse", "keba", "Keba", "evCharge", "EvCharge", "ev/",
            "Firmware", "firmware", "upgrade", "Upgrade")


def _is_epcube(flow: http.HTTPFlow) -> bool:
    return any(h in flow.request.pretty_host for h in EPCUBE_HOSTS)


def _json(content: bytes):
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


TRACE_FILE = Path(__file__).with_name("epcube_trace.log")


def _shape(value, depth=0):
    """Struttura di un JSON (chiavi e tipi), senza i valori."""
    if depth > 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: _shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def response(flow: http.HTTPFlow) -> None:
    if flow.response is None:
        return
    # Diagnostica: host e percorso di ogni chiamata, per vedere cosa passa dal proxy
    with TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {flow.response.status_code} "
                f"{flow.request.pretty_host}{flow.request.path.split('?')[0]}\n")
    if not _is_epcube(flow):
        return
    path = flow.request.path
    if "/user/user/base" in path:
        with TRACE_FILE.open("a", encoding="utf-8") as f:
            f.write("  struttura: " + json.dumps(_shape(_json(flow.response.content))) + "\n")

    if "/user/user/base" in path:
        body = _json(flow.response.content)
        device = (body or {}).get("data", {}) if isinstance(body, dict) else {}
        device = device.get("tblDevice") if isinstance(device, dict) else None
        if isinstance(device, dict):
            before = device.get("kebaAuthority")
            device["kebaAuthority"] = "1"
            flow.response.text = json.dumps(body, ensure_ascii=False)
            ctx.log.info(f"[keba] user/user/base: kebaAuthority {before!r} -> '1'")
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event": "kebaAuthority riscritto",
                    "before": before,
                    "tblDevice": device,
                }, ensure_ascii=False) + "\n")

    if any(p in path for p in EV_PATHS):
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": flow.request.method,
            "path": path,
            "request": _json(flow.request.content) or flow.request.get_text(strict=False),
            "status": flow.response.status_code,
            "response": _json(flow.response.content) or flow.response.get_text(strict=False),
        }
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        ctx.log.info(f"[keba] {flow.request.method} {path} -> {flow.response.status_code}")


# --- Sonda di sola lettura: verifica se il gateway ha davvero i registri wallbox ---
# Alla prima query dell'app riusa la sua autorizzazione per LEGGERE (mai scrivere):
# - 1446..1449 appena scritti dall'app (se il gateway li conosce, tornano i valori)
# - registri info/esito della wallbox
# - 0515 (=1301, SoC) come controllo di un registro sicuramente esistente
# - 7F00 inesistente, per vedere come risponde il cloud a un registro sconosciuto
# Il token resta in memoria; nel file finiscono solo indirizzi e risposte.
import threading
import urllib.request

PROBE_FILE = Path(__file__).with_name("epcube_probe.jsonl")
PROBES = [("1446", 4), ("141C", 2), ("140E", 18), ("144A", 8),
          ("0515", 1)]
_probe_done = False


def _probe(url, headers, dev_id):
    for address, num in PROBES:
        body = json.dumps({"devId": dev_id,
                           "queryDataList": [{"address": address, "num": num}]}).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = _json(resp.read())
        except Exception as err:  # noqa: BLE001 - diagnostica
            result = {"errore": str(err)}
        with PROBE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.strftime("%H:%M:%S"), "address": address,
                                "num": num, "response": result}, ensure_ascii=False) + "\n")
        time.sleep(2)
    ctx.log.info("[probe] letture completate, vedi tools/epcube_probe.jsonl")


def request(flow: http.HTTPFlow) -> None:
    global _probe_done
    if _probe_done or not _is_epcube(flow) or "/device/send/query" not in flow.request.path:
        return
    auth = flow.request.headers.get("authorization")
    body = _json(flow.request.content) or {}
    if not auth or not body.get("devId"):
        return
    _probe_done = True
    headers = {"authorization": auth, "content-type": "application/json",
               "user-agent": flow.request.headers.get("user-agent", "")}
    url = flow.request.pretty_url.split("?")[0]
    threading.Thread(target=_probe, args=(url, headers, str(body["devId"])), daemon=True).start()
    ctx.log.info("[probe] avviata sonda di sola lettura")
