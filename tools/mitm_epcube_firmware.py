"""mitmproxy: fa comparire l'aggiornamento V1.3.0 nella schermata firmware dell'app.

Sul canale utente il server risponde "già l'ultima versione" (o "aggiornamento in
corso"), quindi l'app non mostra il pulsante per aggiornare. Questo script
riscrive quella risposta perche' il pulsante compaia.

Attenzione: premere il pulsante dice al SERVER di avviare l'aggiornamento vero
del gateway. Due esiti possibili:
- il server accetta -> l'aggiornamento parte davvero (irreversibile: il gateway
  deve restare in rete e alimentato per tutto il processo);
- il server rifiuta il codice-task non valido -> non parte nulla, e nel log qui
  sotto si vede l'errore.

Il download del firmware lo fa il gateway, non il telefono: non passa da questo
proxy. Va catturato a parte con tcpdump sul router.

Tutte le chiamate firmware finiscono in tools/epcube_fw_log.jsonl.

Uso:

    mitmweb --listen-port 8888 --ignore-hosts "192\\.168\\." -s tools/mitm_epcube_firmware.py
"""

import json
import time
from pathlib import Path

from mitmproxy import ctx, http

EPCUBE_HOSTS = ("epcube.com", "epcube-monitoring.com")
LOG_FILE = Path(__file__).with_name("epcube_fw_log.jsonl")

# Versioni da mostrare. newVerNum / task vengono dal canale installatore
# (checkUpgrade type=2): softWareVersion V1.2.2 -> V1.3.0, newVersion 022802450225.
CURRENT_VER = "V1.2.2"
NEW_VER = "V1.3.0"
TASK_ID = "022802450225"   # tentativo: identificativo del firmware lato installatore


def _is_epcube(flow: http.HTTPFlow) -> bool:
    return any(h in flow.request.pretty_host for h in EPCUBE_HOSTS)


def _json(content: bytes):
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def _log(kind: str, flow: http.HTTPFlow) -> None:
    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "method": flow.request.method,
        "path": flow.request.path,
        "query": dict(flow.request.query),
        "request": _json(flow.request.content) or flow.request.get_text(strict=False),
        "status": flow.response.status_code if flow.response else None,
        "response": _json(flow.response.content) if flow.response else None,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def response(flow: http.HTTPFlow) -> None:
    if flow.response is None or not _is_epcube(flow):
        return
    path = flow.request.path.split("?")[0]

    # L'app nasconde il pulsante di aggiornamento agli utenti "normali"
    # (userType == "2"): la schermata dice solo "contatta l'installatore".
    # Riscrivendo userType, l'app mostra la UI installatore con il pulsante.
    if path.endswith("/user/user/base") or path.endswith("/user/login"):
        body = _json(flow.response.content)
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("userType") == "2":
            data["userType"] = "1"
            flow.response.text = json.dumps(body, ensure_ascii=False)
            ctx.log.info("[fw] userType 2 -> 1: sblocco la UI installatore")
        return

    # Schermata utente: forza "aggiornamento disponibile" cosi' compare il pulsante.
    # Nell'app hasNewVersion diverso da "1" attiva il ramo con il pulsante che avvia.
    if path.endswith("/device/checkFirmarkVersion"):
        body = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Success",
            "status": 200,
            "data": {
                "currentVerNum": CURRENT_VER,
                "newVerNum": NEW_VER,
                "hasNewVersion": "0",
                "tips": f"Nuova versione {NEW_VER} disponibile.",
                "upgradeTaskId": TASK_ID,
            },
            "pattern": "yyyy-MM-dd HH:mm:ss",
        }
        flow.response.text = json.dumps(body, ensure_ascii=False)
        ctx.log.info("[fw] checkFirmarkVersion riscritta: mostro V1.3.0 disponibile")
        _log("checkFirmarkVersion(riscritta)", flow)
        return

    # Il pulsante avvia qui: registriamo cosa risponde davvero il server.
    if path.endswith("/device/upgrade"):
        _log("upgrade(risposta server)", flow)
        messaggio = (_json(flow.response.content) or {}).get("message")
        ctx.log.info(f"[fw] upgrade -> {flow.response.status_code} {messaggio}")
        return

    # Diagnostica: ogni POST verso device/ (per non perdere il comando di avvio,
    # qualunque endpoint usi) e le chiamate note del firmware.
    if flow.request.method == "POST" and "/device/" in path:
        _log("POST-device", flow)
        ctx.log.info(f"[fw] POST {path} -> {flow.response.status_code}")
    elif any(p in path for p in ("/device/checkUpgrade", "/device/submitUpgrade",
                                 "/user/user/queryFirmwareInfo")):
        _log("firmware", flow)
