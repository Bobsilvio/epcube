#!/usr/bin/env python3
"""Verifica se il gateway EP Cube supporta davvero la funzione wallbox.

Il gateway accetta i comandi che configurano la wallbox e risponde "Success"
anche quando il firmware non implementa la funzione: le scritture finiscono nel
vuoto. L'unico modo per saperlo è scrivere un registro e rileggerlo poco dopo.

Lo script:
1. mostra il firmware installato e quello eventualmente disponibile;
2. scrive 1446 = 1 (abilita il server Modbus verso la wallbox);
3. aspetta qualche secondo e rilegge 1446-1449;
4. legge gli esiti della ricerca (141C, 141D) e il SoC come controllo.

Se dopo la scrittura il registro vale 1, il firmware supporta la wallbox.
Se torna 0, la funzione non c'è: nessun emulatore può farla funzionare.

Uso:

    python3 tools/verifica_wallbox.py
    python3 tools/verifica_wallbox.py --solo-lettura    # non scrive nulla
    EPCUBE_TOKEN="Bearer ..." python3 tools/verifica_wallbox.py

Senza token esplicito viene cercato nella configurazione di Home Assistant, se
la cartella /config è montata sul computer.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URLS = {
    "EU": "https://monitoring-eu.epcube.com/api",
    "US": "https://epcube-monitoring.com/app-api",
    "JP": "https://monitoring-jp.epcube.com/api",
}
USER_AGENT = "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)"
TIMEOUT = 25
PAUSA = 1.5          # fra una chiamata e l'altra, per non stressare il server
ATTESA_RILETTURA = 8  # secondi fra scrittura e rilettura

# Registri della wallbox nello spazio del gateway
REG_TCP_SERVER = "1446"
REG_AUTO_SCAN = "1447"
REG_IP_ALTO = "1448"
REG_IP_BASSO = "1449"
REG_ESITO_AUTO = "141C"
REG_ESITO_MANUALE = "141D"
REG_SOC = "0515"      # batteria: serve solo a dimostrare che la lettura funziona

ESITI = {0: "inattivo", 1: "in corso", 2: "completata", 3: "scaduta"}
ESITI_MANUALE = {0: "inattivo", 1: "riuscita", 2: "fallita"}

PERCORSI_STORAGE = (
    "/Volumes/config/.storage/core.config_entries",
    "/config/.storage/core.config_entries",
    os.path.expanduser("~/homeassistant/.storage/core.config_entries"),
)


class Api:
    def __init__(self, token, region):
        self.base = BASE_URLS.get(region.upper(), BASE_URLS["EU"])
        self.headers = {
            "authorization": token,
            "accept": "*/*",
            "accept-language": "it-IT",
            "content-type": "application/json",
            "user-agent": USER_AGENT,
        }

    def _chiama(self, percorso, corpo=None):
        richiesta = urllib.request.Request(
            self.base + percorso,
            data=json.dumps(corpo).encode() if corpo is not None else None,
            headers=self.headers,
            method="POST" if corpo is not None else "GET",
        )
        try:
            with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
                return json.loads(risposta.read())
        except urllib.error.HTTPError as err:
            return {"status": err.code, "message": err.read()[:200].decode("utf8", "replace")}
        except (urllib.error.URLError, OSError, ValueError) as err:
            return {"status": 0, "message": str(err)}

    def leggi(self, dev_id, indirizzo, quantita=1):
        risposta = self._chiama("/device/send/query", {
            "devId": dev_id,
            "queryDataList": [{"address": indirizzo, "num": quantita}],
        })
        dati = risposta.get("data")
        if not dati:
            return None, risposta.get("message", "nessuna risposta")
        return dati[0].get("values"), None

    def scrivi(self, dev_id, indirizzo, valore):
        risposta = self._chiama("/device/send/set", {
            "devId": dev_id,
            "setDataList": [{"address": indirizzo, "values": [valore]}],
        })
        return risposta.get("message") == "Success", risposta.get("message")

    def firmware(self, dev_id):
        return self._chiama(f"/user/user/queryFirmwareInfo?devId={dev_id}").get("data") or {}

    def aggiornamento(self, dev_id, tipo=2):
        return self._chiama(
            f"/device/checkUpgrade?devId={dev_id}&type={tipo}&forcedUpgrade=0"
        ).get("data") or {}


def trova_configurazione():
    """Token, regione e devId dalla configurazione di Home Assistant, se raggiungibile."""
    for percorso in PERCORSI_STORAGE:
        file = Path(percorso)
        if not file.is_file():
            continue
        try:
            voci = json.loads(file.read_text())["data"]["entries"]
        except (OSError, ValueError, KeyError):
            continue
        for voce in voci:
            if voce.get("domain") != "epcube":
                continue
            opzioni = voce.get("options") or {}
            dati = voce.get("data") or {}
            token = opzioni.get("token") or dati.get("token")
            if token:
                return token, opzioni.get("region") or dati.get("region", "EU"), file
    return None, "EU", None


def intestazione(testo):
    print(f"\n{testo}\n{'-' * len(testo)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dev-id", default="1572",
                        help="identificativo usato dall'app (predefinito: 1572)")
    parser.add_argument("--token", help="token EP Cube, con o senza 'Bearer '")
    parser.add_argument("--region", default=None, help="EU, US o JP")
    parser.add_argument("--solo-lettura", action="store_true",
                        help="non scrive nulla: legge soltanto lo stato attuale")
    args = parser.parse_args()

    token = args.token or os.environ.get("EPCUBE_TOKEN")
    regione, origine = args.region or "EU", None
    if not token:
        token, regione_trovata, origine = trova_configurazione()
        regione = args.region or regione_trovata
    if not token:
        print("Token non trovato. Passalo con --token, oppure monta la cartella "
              "/config di Home Assistant.", file=sys.stderr)
        return 2
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
    if origine:
        print(f"Token letto da {origine}")

    api = Api(token, regione)
    dev_id = args.dev_id

    intestazione("Firmware")
    info = api.firmware(dev_id)
    installato = info.get("firmwareVersion", "?")
    print(f"  installato      {installato}")
    print(f"  modulo RTU      {info.get('rtuVersion', '?')}")
    print(f"  aggiornamento automatico: "
          f"{'attivo' if info.get('aotuUpdateFirmware') == '1' else 'disattivo'}")
    time.sleep(PAUSA)

    disponibile = api.aggiornamento(dev_id).get("newSoftWareVersion")
    if disponibile and disponibile != installato:
        print(f"  DISPONIBILE     {disponibile}  (da installare dall'app)")
    else:
        print("  nessun aggiornamento proposto dal server")

    intestazione("Registri della wallbox")
    if not args.solo_lettura:
        ok, messaggio = api.scrivi(dev_id, REG_TCP_SERVER, 1)
        print(f"  scrittura {REG_TCP_SERVER} = 1 -> "
              f"{'accettata dal cloud' if ok else 'rifiutata: ' + str(messaggio)}")
        if ok:
            print(f"  attendo {ATTESA_RILETTURA} secondi, poi rileggo...")
            time.sleep(ATTESA_RILETTURA)

    valori, errore = api.leggi(dev_id, REG_TCP_SERVER, 4)
    if errore:
        print(f"  lettura fallita: {errore}")
        return 1
    etichette = ("1446 server Modbus", "1447 ricerca automatica",
                 "1448 IP wallbox (alto)", "1449 IP wallbox (basso)")
    for etichetta, valore in zip(etichette, valori):
        print(f"  {etichetta:<26} {valore}")
    memorizzato = bool(valori and valori[0])
    time.sleep(PAUSA)

    esito_auto, _ = api.leggi(dev_id, REG_ESITO_AUTO)
    time.sleep(PAUSA)
    esito_manuale, _ = api.leggi(dev_id, REG_ESITO_MANUALE)
    if esito_auto:
        print(f"  141C ricerca automatica    {esito_auto[0]} "
              f"({ESITI.get(esito_auto[0], '?')})")
    if esito_manuale:
        print(f"  141D ricerca manuale       {esito_manuale[0]} "
              f"({ESITI_MANUALE.get(esito_manuale[0], '?')})")
    time.sleep(PAUSA)

    intestazione("Controllo")
    soc, _ = api.leggi(dev_id, REG_SOC)
    if soc:
        print(f"  SoC batteria               {soc[0]} %   <- la lettura funziona")
    else:
        print("  SoC non leggibile: il problema è nella comunicazione, non nel firmware")
        return 1

    intestazione("Esito")
    if args.solo_lettura:
        print("  Sola lettura: per il verdetto rilancia senza --solo-lettura.")
    elif memorizzato:
        print(f"  Il gateway HA MEMORIZZATO il registro: il firmware {installato}")
        print("  supporta la wallbox. Ora la ricerca dall'app può funzionare e il")
        print("  ponte su Home Assistant entra in gioco.")
    else:
        print(f"  Il gateway ha DIMENTICATO il registro: il firmware {installato}")
        print("  non implementa la funzione wallbox. Nessun emulatore può aggirarlo.")
        if disponibile and disponibile != installato:
            print(f"  Prova ad aggiornare alla {disponibile} e rilancia questo script.")
        else:
            print("  Serve un firmware che la supporti: vedi docs/richiesta-epcube-wallbox.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
