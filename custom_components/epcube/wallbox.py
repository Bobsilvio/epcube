"""Verifica se il gateway supporta davvero la funzione wallbox.

Il cloud risponde "Success" alle scritture dei registri della wallbox anche
quando il firmware non implementa la funzione: i valori vengono accettati e
subito dimenticati. L'unico modo per accorgersene è scrivere un registro e
rileggerlo poco dopo.

Il servizio scrive 1446 = 1 (abilita il server Modbus verso la wallbox), attende
e rilegge 1446-1449. Legge poi gli esiti della ricerca e il livello di carica
della batteria, che serve da controprova: se si legge il SoC ma non i registri
della wallbox, il problema è il firmware e non la comunicazione.
"""

from __future__ import annotations

import asyncio
import logging

from .const import get_base_url, USER_AGENT, STATS_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Registri della wallbox nello spazio del gateway
REG_TCP_SERVER = "1446"
REG_ESITO_AUTO = "141C"
REG_ESITO_MANUALE = "141D"
REG_SOC = "0515"

ATTESA_RILETTURA = 8  # secondi fra scrittura e rilettura

ESITI_AUTO = {0: "inattiva", 1: "in corso", 2: "completata", 3: "scaduta"}
ESITI_MANUALE = {0: "inattiva", 1: "riuscita", 2: "fallita"}


async def _async_invia(session, token, region, percorso, corpo=None):
    url = f"{get_base_url(region)}{percorso}"
    headers = {
        "accept": "*/*",
        "accept-language": "it-IT",
        "content-type": "application/json",
        "user-agent": USER_AGENT,
        "authorization": token,
    }
    async with asyncio.timeout(STATS_TIMEOUT):
        if corpo is None:
            async with session.get(url, headers=headers) as risposta:
                return await risposta.json(content_type=None)
        async with session.post(url, headers=headers, json=corpo) as risposta:
            return await risposta.json(content_type=None)


async def _async_leggi(session, token, region, dev_id, indirizzo, quantita=1):
    risposta = await _async_invia(session, token, region, "/device/send/query", {
        "devId": dev_id,
        "queryDataList": [{"address": indirizzo, "num": quantita}],
    })
    dati = (risposta or {}).get("data")
    if not dati:
        return None
    return dati[0].get("values")


async def _async_scrivi(session, token, region, dev_id, indirizzo, valore):
    risposta = await _async_invia(session, token, region, "/device/send/set", {
        "devId": dev_id,
        "setDataList": [{"address": indirizzo, "values": [valore]}],
    })
    return (risposta or {}).get("message") == "Success"


async def async_check_wallbox_support(session, token, region, dev_id,
                                      solo_lettura=False) -> dict:
    """Esegue la verifica e restituisce il risultato, pronto per il servizio."""
    risultato: dict = {"sola_lettura": solo_lettura}

    firmware = await _async_invia(
        session, token, region, f"/user/user/queryFirmwareInfo?devId={dev_id}"
    )
    info = (firmware or {}).get("data") or {}
    installato = info.get("firmwareVersion")
    risultato["firmware_installato"] = installato
    risultato["firmware_rtu"] = info.get("rtuVersion")

    # Il firmware ha due canali e possono non dire la stessa cosa:
    # checkUpgrade è quello dell'installatore, checkFirmarkVersion quello che
    # l'utente vede nell'app.
    aggiornamento = await _async_invia(
        session, token, region,
        f"/device/checkUpgrade?devId={dev_id}&type=2&forcedUpgrade=0",
    )
    disponibile = ((aggiornamento or {}).get("data") or {}).get("newSoftWareVersion")
    if disponibile and disponibile != installato:
        risultato["firmware_disponibile_installatore"] = disponibile

    utente = await _async_invia(
        session, token, region, f"/device/checkFirmarkVersion?devId={dev_id}"
    )
    dati_utente = (utente or {}).get("data") or {}
    # Nell'app hasNewVersion = "1" significa "nessun aggiornamento": il dialogo
    # mostra solo un pulsante di presa visione, senza avviare nulla.
    offerto = dati_utente.get("hasNewVersion") != "1"
    risultato["firmware_offerto_nell_app"] = offerto
    if dati_utente.get("tips"):
        risultato["firmware_messaggio_app"] = dati_utente["tips"]
    if disponibile and disponibile != installato and not offerto:
        risultato["nota_firmware"] = (
            f"La {disponibile} risulta destinata a questo gateway, ma l'app non la "
            "propone: la pubblicazione agli utenti finali è decisa dal server. "
            "Va chiesta all'installatore o all'assistenza EP Cube."
        )

    if not solo_lettura:
        accettata = await _async_scrivi(session, token, region, dev_id, REG_TCP_SERVER, 1)
        risultato["scrittura_accettata"] = accettata
        if accettata:
            await asyncio.sleep(ATTESA_RILETTURA)

    valori = await _async_leggi(session, token, region, dev_id, REG_TCP_SERVER, 4)
    if valori is None:
        risultato["errore"] = "registri della wallbox non leggibili"
        return risultato
    risultato["registri"] = {
        "1446_server_modbus": valori[0],
        "1447_ricerca_automatica": valori[1] if len(valori) > 1 else None,
        "1448_ip_wallbox_alto": valori[2] if len(valori) > 2 else None,
        "1449_ip_wallbox_basso": valori[3] if len(valori) > 3 else None,
    }

    esito_auto = await _async_leggi(session, token, region, dev_id, REG_ESITO_AUTO)
    esito_manuale = await _async_leggi(session, token, region, dev_id, REG_ESITO_MANUALE)
    if esito_auto:
        risultato["ricerca_automatica"] = ESITI_AUTO.get(esito_auto[0], esito_auto[0])
    if esito_manuale:
        risultato["ricerca_manuale"] = ESITI_MANUALE.get(esito_manuale[0], esito_manuale[0])

    soc = await _async_leggi(session, token, region, dev_id, REG_SOC)
    risultato["controllo_soc"] = soc[0] if soc else None
    if soc is None:
        risultato["errore"] = (
            "nemmeno il livello di carica è leggibile: problema di comunicazione, "
            "non di firmware"
        )
        return risultato

    memorizzato = bool(valori[0])
    risultato["supportata"] = None if solo_lettura else memorizzato
    if solo_lettura:
        risultato["esito"] = "Sola lettura: rilancia senza l'opzione per il verdetto."
    elif memorizzato:
        risultato["esito"] = (
            f"Il gateway ha memorizzato il registro: il firmware {installato} "
            "supporta la wallbox. La ricerca dall'app può funzionare."
        )
    else:
        testo = (
            f"Il gateway ha dimenticato il registro: il firmware {installato} "
            "non implementa la funzione wallbox."
        )
        if disponibile and disponibile != installato:
            testo += (f" Risulta disponibile la {disponibile}: se l'app non la "
                      "propone, chiedila all'installatore o all'assistenza.")
        risultato["esito"] = testo

    _LOGGER.info("Verifica wallbox: %s", risultato.get("esito"))
    return risultato
