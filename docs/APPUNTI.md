# EP Cube — appunti tecnici e stato del progetto

Riferimento di tutto quello che è stato scoperto e costruito sul sistema EP Cube,
così da non ripartire da zero in futuro. Aggiornato al 2026-10-24.

## Il sistema

| Dato | Valore |
|---|---|
| Modello | EP Cube monofase (1Phase, devType 0) |
| SG SN | `100100004001245250049` |
| RTU SN | `VD06000324208235` |
| devId (API) | `1572` |
| Firmware | **V1.3.0** (aggiornato da V1.2.2 il 2026-10-24) |
| Modulo Wi-Fi / RTU | V1.0.0.4 |
| MAC gateway (LAN) | `80:64:6f:dd:33:b4` |
| MAC gateway (BLE) | `80:64:6f:dd:33:b6` |
| IP gateway in LAN | `192.168.178.173` |
| Regione | EU |
| App ufficiale | EP Cube EU 3.1.1 (iOS) |

## Come il gateway parla col mondo

Due canali, entrambi **cifrati TLS**:

- **`15.188.7.73:8883`** — MQTT over TLS, broker su AWS Parigi (eu-west-3). È il
  canale principale: dati in tempo reale, comandi dal server, download firmware.
- **`43.132.171.166:22015`** — TLS, Tencent Cloud, canale secondario (telemetria/log).

L'app invece parla con il **cloud REST** su `monitoring-eu.epcube.com/api` (HTTPS).

Conseguenza pratica: il traffico del gateway si **cattura** (si vede con chi
parla e quanto) ma **non si legge** (TLS). Vedi la sezione "Sniffing".

## Dove leggere i dati dell'EP Cube (senza cloud)

1. **Bluetooth locale** — `tools/esphome_epcube_ble.yaml` (ESPHome su ESP32).
   Protocollo: JSON `{"RawModbus":"<frame RTU hex>"}` scritto su GATT
   `ee6d7171-...`, risposta in notifica su `ee6d7172-...`. Slave 0x64, funzione 03.
   Registri verificati contro il cloud (vedi `memory/project_ble_modbus.md`).

2. **API cloud** con il token dell'account. Esempi di endpoint:
   - `POST /device/send/query` `{devId, queryDataList:[{address,num}]}` — legge registri
   - `POST /device/send/set` `{devId, setDataList:[{address,values:[..]}]}` — scrive registri
   - `GET /user/user/base` — profilo + `tblDevice` (stato device, flag)
   - `GET /user/user/queryFirmwareInfo?devId=` — versione firmware
   - `GET /device/homeDeviceInfo?sgSn=` — stato live (online, SoC, guasti)

   Registro di controllo utile: `0515` = SoC batteria (serve da controprova "la
   lettura funziona").

## Integrazione Home Assistant

- **`Bobsilvio/epcube`** (`custom_components/epcube`) — integrazione cloud che
  crea i sensori. Versione 1.7.0. Dal 2026-10-24 ha anche il servizio
  `epcube.check_wallbox_support` (vedi sotto).

## La wallbox — stato e soluzione pronta

Obiettivo: far vedere nell'app EP Cube la wallbox di casa (ChargePoint), che l'app
non supporta nativamente — l'app integra **solo wallbox KEBA KeContact**.

### Come funziona la wallbox nell'EP Cube
Il gateway fa da **client Modbus TCP**: si collega alla porta **502** della KEBA e
ne legge i registri. Scoperta dall'app (schermata Caricatore EV):

- `1446` abilita server Modbus TCP, `1447` abilita ricerca automatica
- `1448`/`1449` IP manuale della wallbox (16-bit alto/basso)
- `141C` esito ricerca automatica, `141D` esito ricerca manuale
  (0 inattivo, 1 in corso/riuscita, 2 completata/fallita, 3 timeout)
- `140E` info caricatore, `144A` numero di serie, `141E` lista IP trovati

### Il blocco
Scrivendo `1446=1` e rileggendo dopo pochi secondi, il valore torna **0**: il
gateway accetta i comandi ma non li memorizza, la ricerca non parte mai. Vale sia
con V1.2.2 sia con **V1.3.0**.

Due cause possibili, **indistinguibili** dal test attuale:
1. il firmware non implementa la funzione wallbox sul monofase;
2. il server tiene `kebaAuthority = 0` sull'account (mai forzato lato server,
   solo lato app con mitmproxy).

Per isolarle serve che EP Cube abiliti `kebaAuthority` (vedi `richiesta-epcube-wallbox.md`).

### La soluzione, già pronta e testata
**`~/italysat/epcube_wallboxbridge`** — integrazione HA separata (NON dentro
`epcube`, per non farla sovrascrivere dagli aggiornamenti). Apre un server Modbus
TCP sulla porta 502 di Home Assistant e risponde come una KEBA KeContact, con i
dati della ChargePoint presi dalle entità HA. Mappa registri dalla "KeContact P30
Modbus TCP Programmers Guide V1.04". Testata con client Modbus: stato, potenza,
correnti, energia tutti corretti. In sola lettura di default; i comandi (avvio,
stop, limite corrente) si attivano con `allow_control`.

Già **installata** in `/config/custom_components/epcube_wallboxbridge`. Appena
EP Cube abilita la funzione, nell'app basta mettere l'IP di Home Assistant come
indirizzo della wallbox e il gateway la trova.

### Verifica rapida del supporto wallbox
- `python3 tools/verifica_wallbox.py` — scrive `1446=1`, rilegge, dà il verdetto.
- oppure il servizio HA `epcube.check_wallbox_support` (stessa logica, in `wallbox.py`).

## Elettrodomestici (es. lavatrice)

L'app EP Cube integra **solo Home Connect** (Bosch, Siemens, Gaggenau, Neff), via
cloud-a-cloud (cloud EP Cube ↔ cloud Bosch). Una LG non può comparirci: non è in
quel cloud e non si può fingere verso Bosch. Niente da fare lato app.
La lavatrice LG è già integrata in Home Assistant (LG ThinQ) e si gestisce da lì.

(Esisteva una prova con mitmproxy che iniettava la lavatrice e la ChargePoint
nelle schermate dell'app: funzionava solo col telefono dietro il proxy, come
vetrina. Non è una soluzione stabile e non è stata resa permanente.)

## Firmware — aggiornamento e download

### Aggiornare (quando serve)
Sul canale utente l'app **nasconde** il pulsante di aggiornamento: mostra solo
"contatta l'installatore" (`UpdateActivity`, `userTypeIsNormal()` = `userType=="2"`).

Sblocco con mitmproxy (`tools/mitm_epcube_firmware.py`): riscrive
`data.userType "2"->"1"` nelle risposte di `/user/user/base` e `/user/login`.
Riaprendo l'app compare il menu installatore con il pulsante "Aggiornamento".
Premendolo l'app chiama `device/checkUpgrade?type=2&forcedUpgrade=1` e avvia l'OTA.

In alternativa (più semplice): **chiedere a EP Cube/installatore** di pushare la
versione — lo fanno su richiesta.

**Attenzione:** l'OTA è irreversibile, dura 40-50 minuti, il gateway deve restare
in rete e alimentato per tutto il tempo. Interromperlo può bloccare l'inverter.
Prima di avviarlo: verificare gateway online, SoC decente, nessun guasto
(`homeDeviceInfo`).

### Scaricare il file firmware — NON fattibile via software
Il file non è ottenibile dalla rete:
- l'app non lo scarica mai (lo fa il gateway);
- il download avviene via MQTT TLS, cifrato;
- `getOssDownloadLink` risponde 404;
- `submitUpgrade`/`upgrade` mandano solo "avvia", nessun URL.

L'unica via per avere il binario è il **dump fisico della flash** del gateway
(programmatore SOIC-8/eMMC), ed è possibile che sia cifrato anche in flash.

Per **studiare** una versione senza il binario: confrontare registri e risposte
API prima/dopo l'aggiornamento (reverse engineering funzionale).

## Sniffing — come si fa

### Telefono (traffico dell'app)
L'app passa da **mitmproxy** perché sul telefono si installa il certificato CA.

```bash
mitmweb --listen-port 8888 --ignore-hosts "192\.168\." -s tools/<script>.py
```

iPhone: Wi-Fi → (i) → Proxy HTTP → Manuale → IP del Mac, porta 8888.
`--ignore-hosts "192\.168\."` evita che mitmproxy tocchi (e rompa) il traffico
locale. **Non** usare `--mode wireguard`: va in crash sul QUIC di altre app.

Script disponibili in `tools/`:
- `mitm_epcube_keba.py` — forza `kebaAuthority=1` (mostra la sezione wallbox)
- `mitm_epcube_firmware.py` — sblocca il menu installatore (userType) per aggiornare
- `mitm_epcube_sim.py` — inietta lavatrice/ChargePoint nell'app (esperimento)

### Gateway (traffico del dispositivo)
Il gateway non accetta proxy né certificati: si cattura solo passivamente dal
router (GL-MT6000, OpenWrt). Serve `tcpdump` sul router (`opkg install tcpdump`)
e `tshark` sul Mac (`brew install wireshark`).

```bash
# disabilitare prima il flow offloading sul router, o si perdono i pacchetti:
uci set firewall.@defaults[0].flow_offloading='0'
uci set firewall.@defaults[0].flow_offloading_hw='0'
uci commit firewall && /etc/init.d/firewall restart
# (riattivarli con '1' quando finito)

# cattura su file dal Mac:
ssh root@192.168.178.1 "tcpdump -i br-lan -s0 -U -w - host 192.168.178.173" > ~/Downloads/gw.pcap
# analisi:
tshark -r ~/Downloads/gw.pcap -T fields -e ip.dst -e tcp.dstport
```

Il contenuto resta cifrato (TLS): si vedono destinazioni, porte, volumi e tempi,
non i dati.

## File e dove stanno

| Percorso | Cosa |
|---|---|
| `custom_components/epcube/` | integrazione HA principale (v1.7.0) |
| `custom_components/epcube/wallbox.py` | servizio `check_wallbox_support` |
| `~/italysat/epcube_wallboxbridge/` | integrazione ponte Modbus/KEBA (separata) |
| `tools/verifica_wallbox.py` | verifica supporto wallbox da terminale |
| `tools/esphome_epcube_ble.yaml` | lettura locale BLE |
| `tools/mitm_epcube_*.py` | script mitmproxy |
| `docs/richiesta-epcube-wallbox.md` | messaggio per l'assistenza |
| `~/.claude/.../memory/project_ble_modbus.md` | registri BLE/Modbus e cronologia |

## Prossimi passi

1. **Inviare la richiesta a EP Cube** (`docs/richiesta-epcube-wallbox.md`):
   abilitare `kebaAuthority`, e chiedere se la wallbox è supportata sul monofase.
2. Quando `kebaAuthority` è attivo, rilanciare `verifica_wallbox.py`:
   - `1446` resta 1 → il ponte `epcube_wallboxbridge` entra in gioco, basta mettere
     l'IP di HA come wallbox nell'app;
   - `1446` torna 0 → è il firmware, serve una versione che la implementi.
3. (Opzionale) dump fisico della flash se si vuole il binario del firmware.

## Sicurezza / igiene

- Il token HA usato per le prove va **revocato** se è stato condiviso in chiaro
  (HA → profilo → Sicurezza). Gli script leggono il token dal file di config HA
  o da `tools/ha_token.txt` (escluso da git).
- `tools/*.log`, `tools/*.jsonl`, `tools/ha_token.txt`, i `.pcap`: dati di lavoro,
  tenerli fuori dai repo pubblici.

---

## Aggiornamento 2026-10-24 (sessione analisi completa)

### Firmware aggiornato a V1.3.0
Sbloccato il menu installatore via mitmproxy (`userType 2->1`), avviato l'OTA dall'app.
Il firmware arriva cifrato via MQTT TLS (non catturabile). V1.3.0 **non** sblocca la
wallbox: scrivendo `1446=1` e rileggendo, torna `0` come con V1.2.2.

### Wallbox registrata lato server (hasEvse=True) — SENZA kebaAuthority
Scoperta chiave: i registri `1446-1449` sono solo il canale di *ricerca* (volatile).
La wallbox vera si registra con `POST /device/evse/add`:
```
{devId, name, evseSn, model, maxRatedCurrent, maxChargeCurrent, ip,
 failsafeTimeout, failsafeCurrent, batteryBoost, pictures}
```
Chiamato con `ip=192.168.178.101` (il bridge) → Success → `hasEvse=True`, permanente,
senza `kebaAuthority`. `evse/homeInfo` e `getEvseSettings` ora rispondono.
Rimozione: `GET /device/evse/unbind?devId=1572`.

### Ma l'app richiede ANCHE kebaAuthority per mostrarla
Condizione UI (EU 3.1.1 e 3.2.0, identiche):
- Home: `hasEvse && haveKeba()`
- Partnership: `llKeba` visibile se `haveKeba()`
- `haveKeba() = kebaAuthority == "1"`

Quindi senza `kebaAuthority` l'app non mostra la wallbox, anche se registrata.
Con mitmproxy che forza `kebaAuthority=1` → la ChargePoint compare nell'app
("Disconnesso", perché il gateway non apre la connessione Modbus al bridge).
Con `sim.py` (riscrive `evse/homeInfo` dai dati HA) → compare "Connessa" con potenza
ed energia reali. Entrambe sono vetrine: richiedono mitmproxy + proxy sul telefono.

### kebaAuthority non attivabile da nessun comando
Cercato esaustivamente:
- Ogni occorrenza "keba" nell'app EU: solo flag letto, UI (llKeba, text_keba, logo),
  setter interno Kotlin. ZERO endpoint.
- ~45 endpoint nascosti plausibili provati su monitoring-eu.epcube.com → tutti 404.
- pcap del gateway: TLS cifrato (cert Amazon/Starfield, `eu.epcube-monitoring.com`),
  niente in chiaro. Nessun programma decifra senza le chiavi (nel gateway).
- App US 2.6.2 (`com.eternalplanetenergy.epcube`): è pre-wallbox (niente kebaAuthority).
  Usa un backend "a moduli" (`device/v2/userModuleAuthority` GET, `saveDeviceModuleRc`
  POST, `ModuleAuthorityBean{code,type,value}`) → 404 sul server EU, con ogni variante.
  Due architetture diverse: US = moduli v2, EU = flag in tblDevice.

Conclusione: `kebaAuthority` vive nel backend EU e lo scrive solo EP Cube (supporto o
account installatore reale). Nessuna via tecnica dal lato cliente.

### Stato finale persistente (verificato a mitmproxy SPENTO)
`hasEvse=True`, `kebaAuthority=0`, firmware `V1.3.0`. La registrazione della wallbox
resta; la visibilità nell'app dipende da `kebaAuthority` (vetrina mitmproxy o EP Cube).

### Il giorno che si vuole la soluzione permanente
Basta che EP Cube (o l'installatore col suo account) attivi la funzione wallbox /
`kebaAuthority`. Poi: `tools/verifica_wallbox.py` conferma se i registri restano, e se
il gateway apre la connessione Modbus al bridge `epcube_wallboxbridge` (IP di HA come
indirizzo wallbox nell'app). A quel punto niente più mitmproxy.
