"""Costruzione del payload per /device/switchMode.

L'API EP Cube tratta i campi ASSENTI dal payload come "riporta al valore di
default": un payload parziale azzera silenziosamente le fasce TOU e i SoC di
riserva (issue #18 e #31). L'unico modo sicuro di cambiare un singolo valore è
rispedire l'intera configurazione corrente con quel campo sostituito.

Questo modulo è l'unica definizione del payload completo: select, switch e
number la riusano passando solo i campi da cambiare. Non importa nulla di Home
Assistant di proposito, così resta verificabile in isolamento.
"""

# Giorni di default se il coordinator non ha ancora la configurazione
DEFAULT_ACTIVE_WEEK = ["1", "2", "3", "4", "5"]
DEFAULT_ACTIVE_WEEK_NON_WORKDAY = ["6", "7"]


def build_switch_mode_payload(data, work_status=None, only_save="0", **overrides):
    """Payload switchMode completo a partire dai dati del coordinator.

    data: dizionario del coordinator (chiavi minuscole)
    work_status: modalità da impostare; se None resta quella corrente
    only_save: "1" salva senza cambiare modalità, "0" applica la modalità
    overrides: campi da sostituire, con i nomi camelCase attesi dall'API
    """
    if work_status is None:
        work_status = data.get("workstatus", "1")

    payload = {
        "devId": data.get("devid"),
        "workStatus": str(work_status),
        "weatherWatch": "0",
        "onlySave": str(only_save),
        # Fasce TOU: vanno rispedite sempre, anche cambiando modalità
        "touType": data.get("toutype", 0),
        "peakTimeList": data.get("peaktimelist", []),
        "midPeakTimeList": data.get("midpeaktimelist", []),
        "offPeakTimeList": data.get("offpeaktimelist", []),
        "peakTimeListNonWorkDay": data.get("peaktimelistnonworkday", []),
        "midPeakTimeListNonWorkDay": data.get("midpeaktimelistnonworkday", []),
        "offPeakTimeListNonWorkDay": data.get("offpeaktimelistnonworkday", []),
        "dayLightPeakTimeList": data.get("daylightpeaktimelist", []),
        "dayLightMidPeakTimeList": data.get("daylightmidpeaktimelist", []),
        "dayLightOffPeakTimeList": data.get("daylightoffpeaktimelist", []),
        # L'API richiede array di stringhe; il coordinator può restituire interi
        "activeWeek": [str(d) for d in data.get("activeweek") or DEFAULT_ACTIVE_WEEK],
        "activeWeekNonWorkDay": [
            str(d) for d in data.get("activeweeknonworkday") or DEFAULT_ACTIVE_WEEK_NON_WORKDAY
        ],
        "dayLightActiveWeek": [
            str(d) for d in data.get("daylightactiveweek") or DEFAULT_ACTIVE_WEEK
        ],
        "dayLightActiveWeekNonWorkDay": [
            str(d)
            for d in data.get("daylightactiveweeknonworkday") or DEFAULT_ACTIVE_WEEK_NON_WORKDAY
        ],
        "dayLightSavingTime": data.get("daylightsavingtime", False),
        # SoC di riserva e carica da rete: senza questi il server li riazzera
        "selfConsumptioinReserveSoc": str(data.get("selfconsumptioinreservesoc", 5)),
        "backupPowerReserveSoc": str(data.get("backuppowerreservesoc", 50)),
        "allowChargingXiaGrid": str(data.get("allowchargingxiagrid", "1")),
    }

    payload.update(overrides)
    return payload
