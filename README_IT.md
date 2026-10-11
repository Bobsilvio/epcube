[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

## Supportami

Se ti piace il mio lavoro e vuoi che continui nello sviluppo, puoi offrirmi un caffè.

[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

Non dimenticare di seguirmi sui social:

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)
[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)
[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)

# EP Cube Integration for Home Assistant

Integrazione custom per Home Assistant per monitorare il sistema di accumulo EP Cube tramite **API non ufficiale** (la stessa usata dalle app iOS/Android ufficiali).

---

## 🔧 Funzionalità

- 📡 **Dati live** con intervallo di aggiornamento configurabile (default: 30 secondi)
- 📊 **Statistiche** giornaliere, mensili e annuali
  - Disabilitate di default per ridurre il carico
  - Abilitabili singolarmente o tutte insieme dalla configurazione
- 🎛️ **Modalità operative** (Autoconsumo, Tariffazione, Backup) con controllo da Home Assistant
- 📅 **Service TOU** per gestire gli orari di tariffazione direttamente da Home Assistant
- ⚙️ **Entità di configurazione e diagnostica** integrate
- 🧩 Completamente integrato con la UI di Home Assistant (config flow, device info, icone)
- 🔐 **Accesso con email e password dell'app EP Cube**: il captcha del login viene risolto in automatico e il token si rinnova quando scade. Resta possibile usare un Bearer token generato a mano ([QUI](https://epcube-token.streamlit.app/))

---

## 📦 Installazione tramite HACS

1. Apri Home Assistant
2. Vai su **HACS > Integrazioni > Repository personalizzati**
3. Aggiungi: `https://github.com/Bobsilvio/epcube` con tipo `Integrazione`
4. Cerca `EPCube` e installalo
5. Riavvia Home Assistant
6. Vai su **Impostazioni > Dispositivi e servizi** e aggiungi l'integrazione

## 📦 Installazione rapida
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

---

## ⚠️ Requisiti

- Account EP Cube
- Email e password dell'app EP Cube (oppure un Bearer token da [QUI](https://github.com/Bobsilvio/epcube-token))

> La password viene salvata nella configurazione di Home Assistant (`.storage/core.config_entries`), come le credenziali di qualsiasi altra integrazione.

---

## 🎯 Modalità Operative

L'integrazione supporta 3 modalità di funzionamento del dispositivo EP Cube:

### 1. **Autoconsumo** (Mode 1)
- Massimizza l'autoconsumo dell'energia solare
- La batteria carica quando c'è eccesso di solare
- Configurabile: SoC Riserva Autoconsumo (default: 5%)

### 2. **Tariffazione (Time of Use)** (Mode 2) ⭐
- Configura diverse fasce orarie di prezzo (picco, semi-picco, fuori picco)
- Supporta ora legale con orari differenti
- Supporta fasce separate per giorni lavorativi e festivi
- **Gestibile direttamente da Home Assistant con il service `set_tou_schedule`**

### 3. **Backup** (Mode 3)
- Priorità al backup in caso di blackout
- Configurabile: SoC Backup Riservato (default: 50%)

---

## 🔧 Service: Cambio Modalità Operativa

Il service `epcube.set_operating_mode` permette di passare tra **Autoconsumo** e **Backup**.
Per la modalità **Tariffazione** usa invece `epcube.set_tou_schedule` (vedi sezione successiva).

### Parametri

| Parametro | Tipo | Descrizione | Default |
|-----------|------|-------------|---------|
| `mode` | Stringa | Modalità: `"1"` = Autoconsumo, `"3"` = Backup | `"1"` |
| `backup_power_reserve_soc` | Numero | SoC riserva backup % (solo mode=3) | valore attuale |
| `self_consumption_reserve_soc` | Numero | SoC riserva autoconsumo % (solo mode=1) | valore attuale |
| `entry_id` | Stringa | ID configurazione (auto se non specificato) | — |

### Esempi

```yaml
# Attiva modalità Backup con SoC riserva 54%
service: epcube.set_operating_mode
data:
  mode: "3"
  backup_power_reserve_soc: 54
```

```yaml
# Attiva modalità Autoconsumo con SoC riserva 5%
service: epcube.set_operating_mode
data:
  mode: "1"
  self_consumption_reserve_soc: 5
```

---

## 📅 Service TOU (Time of Use)

Il service `epcube.set_tou_schedule` permette di configurare gli orari di tariffazione del tuo EP Cube direttamente da Home Assistant.

### Formato Orari

Ogni fascia oraria è una **stringa** nel formato `"HH:MM_HH:MM_prezzo"`:

```
"08:00_13:00_0.31"   →  dalle 08:00 alle 13:00, prezzo 0.31 €/kWh
"20:00_23:00_0.25"   →  dalle 20:00 alle 23:00, prezzo 0.25 €/kWh
```

> ⚠️ **Inizio e fine sono obbligatori.** Se manca uno dei due, il service restituisce errore.

### Utilizzo

```yaml
service: epcube.set_tou_schedule
data:
  peak_times:
    - "08:00_13:00_0.31"
    - "20:00_23:00_0.31"
  mid_peak_times:
    - "13:00_18:00_0.25"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "18:00_20:00_0.15"
    - "23:00_24:00_0.15"
  switch_to_mode: true
```

### Parametri Disponibili

| Parametro | Tipo | Descrizione | Default |
|-----------|------|-------------|---------|
| `peak_times` | Lista stringhe | Fasce orarie picco | `[]` |
| `mid_peak_times` | Lista stringhe | Fasce semi-picco | `[]` |
| `off_peak_times` | Lista stringhe | Fasce fuori picco | `[]` |
| `peak_times_non_workday` | Lista stringhe | Fasce picco (giorni festivi) | `[]` |
| `mid_peak_times_non_workday` | Lista stringhe | Fasce semi-picco (festivi) | `[]` |
| `off_peak_times_non_workday` | Lista stringhe | Fasce fuori picco (festivi) | `[]` |
| `daylight_peak_times` | Lista stringhe | Fasce picco (ora legale) | `[]` |
| `daylight_mid_peak_times` | Lista stringhe | Fasce semi-picco (ora legale) | `[]` |
| `daylight_off_peak_times` | Lista stringhe | Fasce fuori picco (ora legale) | `[]` |
| `active_week` | Lista interi | Giorni lavorativi (1=Lun … 5=Ven) | `[1,2,3,4,5]` |
| `active_week_non_workday` | Lista interi | Giorni festivi (6=Sab, 7=Dom) | `[6,7]` |
| `daylight_active_week` | Lista interi | Giorni lavorativi (ora legale) | `[1,2,3,4,5]` |
| `daylight_active_week_non_workday` | Lista interi | Giorni festivi (ora legale) | `[6,7]` |
| `tou_type` | Intero | Tipo tariffazione | valore attuale |
| `self_consumption_reserve_soc` | Intero | SoC riserva autoconsumo % | valore attuale |
| `allow_charging_from_grid` | Intero | Permetti ricarica da rete (0/1) | mantiene impostazione attuale del dispositivo |
| `daylight_saving_time` | Booleano | Attiva supporto ora legale | `false` |
| `switch_to_mode` | Booleano | Passa a modalità Tariffazione | `false` |
| `entry_id` | Stringa | ID configurazione (auto se non specificato) | — |

Corrispondenza con la schermata **Finestra temporale TOU** dell'app EP Cube (EU): `off_peak_times` = *Fascia costo basso*, `mid_peak_times` = *Fascia costo normale*, `peak_times` = *Fascia costo alto*; le liste `_non_workday` e `active_week_non_workday` sono il *Fine settimana*, `active_week` i *Giorni lavorativi*. Al massimo **3 fasce per tipo**. Sui sistemi in cui l'app usa i piani tariffari stagionali (firmware del gateway 4.0.8 o successivo, quando il server restituisce i piani) il servizio si ferma con un errore, perché le fasce non verrebbero usate.

I number **TOU picco/semi-picco/fuori picco inizio/fine (HH:00)** leggono l'ora della prima fascia del dispositivo e, se li cambi, aggiornano quella fascia (prezzo e altre fasce invariati) senza cambiare modalità. Se il tipo non ha ancora fasce, ne creano una di un'ora.

Le liste di fasce che passi sostituiscono l'intero piano: quelle non indicate vengono svuotate. Tutto il resto (SoC di riserva, weather watch, winter mode, riserva EV) mantiene il valore attuale. Il prezzo può usare la virgola (`0,31`): viene inviato col punto, come fa l'app. Una fascia non valida blocca la chiamata con un errore, invece di inviare un piano a metà.

### Esempi Pratici

#### Esempio 1: Tariffazione con fasce feriali e festive separate
```yaml
service: epcube.set_tou_schedule
data:
  peak_times:
    - "08:00_13:00_0.31"
    - "20:00_23:00_0.31"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "13:00_20:00_0.15"
    - "23:00_24:00_0.15"
  active_week: [1, 2, 3, 4, 5]
  off_peak_times_non_workday:
    - "00:00_24:00_0.15"
  active_week_non_workday: [6, 7]
  switch_to_mode: true
```

#### Esempio 2: Tariffazione con Ora Legale
```yaml
service: epcube.set_tou_schedule
data:
  # Orari invernali
  peak_times:
    - "08:00_13:00_0.31"
    - "20:00_23:00_0.31"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "13:00_20:00_0.15"
    - "23:00_24:00_0.15"
  # Orari estivi (ora legale)
  daylight_peak_times:
    - "09:00_14:00_0.31"
    - "21:00_24:00_0.31"
  daylight_off_peak_times:
    - "00:00_09:00_0.15"
    - "14:00_21:00_0.15"
  daylight_saving_time: true
  switch_to_mode: true
```

#### Esempio 3: Automazione — Cambio Automatico Stagionale
```yaml
automation:
  - id: 'tou_winter_schedule'
    alias: 'Tariffazione Invernale'
    trigger:
      platform: time
      at: '03:00:00'
    condition:
      - condition: template
        value_template: '{{ now().month < 4 or now().month > 10 }}'
    action:
      service: epcube.set_tou_schedule
      data:
        peak_times:
          - "08:00_13:00_0.31"
          - "20:00_23:00_0.31"
        off_peak_times:
          - "00:00_08:00_0.15"
          - "13:00_20:00_0.15"
          - "23:00_24:00_0.15"
        switch_to_mode: true
```

---

## 👁️ Sensori Orari TOU

L'integrazione crea automaticamente sensori di configurazione che mostrano le fasce orarie impostate:

- `sensor.epcube_orari_picco`
- `sensor.epcube_orari_semi_picco`
- `sensor.epcube_orari_fuori_picco`
- `sensor.epcube_orari_luce_picco`
- `sensor.epcube_orari_luce_semi_picco`
- `sensor.epcube_orari_luce_fuori_picco`

---

## 🌍 Regioni Supportate

| Regione | Endpoint |
|---------|----------|
| 🇪🇺 EU | `https://monitoring-eu.epcube.com/api` |
| 🇺🇸 US | `https://epcube-monitoring.com/app-api` |
| 🇯🇵 JP | `https://monitoring-jp.epcube.com/api` |

---

## 📊 Sensori Disponibili

L'integrazione crea automaticamente sensori per:
- **Batteria**: SoC, Energia in/out (totale e giornaliera), potenza istantanea
- **Fotovoltaico**: Potenza, Energia (AC/DC)
- **Rete**: Potenza, Energia (prelevata/immessa)
- **Carichi di backup**: Potenza, Energia
- **Carichi Non-Backup**: Potenza, Energia
- **EV/Grandi carichi**: Potenza, Energia
- **Generatore**: Potenza, Energia
- **Statistiche**: Contributo EP Cube (autosufficienza), riduzione della deforestazione (alberi), carbone risparmiato
- **Configurazione TOU**: Fasce orarie, giorni attivi, SoC riserve
- **Diagnostica**: Stato sistema, firmware, connettività
- **Guadagno**: oggi e nel mese, calcolato dal cloud EP Cube
- **Ultimo blackout**: inizio dell'ultima interruzione di rete, con le ultime 10 negli attributi
- **Meteo**: la previsione mostrata nella Home dell'app
- **Stringhe FV**: potenza di ogni stringa (PV1–PV6), in kW

Se qualcosa non torna, scarica la diagnostica (Impostazioni → Dispositivi e servizi → EP Cube → ⋮ → Scarica diagnostica) e allegala alla segnalazione: credenziali, serial number e posizione vengono oscurati.

I nomi dei sensori seguono i termini dell'app ufficiale EP Cube.

### Stato e impostazioni

| Entità | Cosa fa |
|---|---|
| `binary_sensor` **Off-grid (blackout)** | Acceso durante un'interruzione di rete (il sistema va a batteria) |
| `binary_sensor` **Rete** | Acceso quando la rete è presente |
| `binary_sensor` **Winter mode attivo** | Acceso mentre il winter mode sta caricando la batteria |
| `switch` **Modalità invernale** | Attiva la modalità invernale: con temperatura e SoC troppo bassi, EP Cube carica fino al SoC obiettivo |
| `number` **SoC obiettivo winter mode** | SoC obiettivo del winter mode |
| `switch` **Vigilanza meteo** | Carica le batterie in previsione di eventi meteo estremi |
| `select` **Modalità** | Autoconsumo, Tariffazione, Backup e, se l'impianto la supporta, **Tariffa dinamica** |
| `number` **Prezzo target** / **Prezzo target di vendita** | Soglie della tariffa dinamica (salvate senza cambiare modalità) |
| `switch` **Consentire la ricarica tramite rete** | Ricarica da rete (fasce fuori picco TOU e modalità Backup) |
| `switch` **Notifica off-grid** / `number` **SoC notifica off-grid** | Durante un blackout l'app avvisa quando la batteria scende a questo SoC |
| `number` **SoC sleep mode** | Sotto questo SoC (5–30%) il sistema va in sleep mode |
| `switch` **Luce indicatore** | La luce sul lato destro dell'inverter ibrido |
| `switch` **Aggiornamento firmware automatico** | Aggiornamenti automatici del firmware |
| `number` **SoC riserva EV/grandi carichi** | Solo su impianti con caricatore EV o grandi carichi |
| `sensor` **Ultimo avviso** / **Ultimo guasto** | Ultime voci della pagina "Alert & Warning" dell'app, con la soluzione suggerita |
| `sensor` **Wi-Fi**, **Firmware** | Stato del Wi-Fi del gateway e versioni firmware (diagnostica) |

Le entità di modalità invernale e weather watch vengono create solo se il sistema espone quelle impostazioni; la modalità invernale segue anche la stessa condizione dell'app (permesso e firmware del gateway). Ogni impostazione si salva come fa l'app della tua regione: in EU la modalità invernale usa `settingWinterProtect` e la ricarica da rete fa parte della modalità (`switchMode`, rispedita completa); sleep mode, luce indicatore e SoC della modalità invernale esistono solo nell'app USA. In nessun caso vengono toccati orari TOU o riserve SoC.

### Accorgersi di un blackout

Durante un blackout (o quando scatta il magnetotermico tra rete ed EP Cube) `status` e `gridLight` vanno entrambi a **0** e tornano a 1 quando torna la rete; a quel punto `gridPowerFailureNum` aumenta di uno. Visti dal cloud, blackout e magnetotermico scattato sono indistinguibili. Usa il binary sensor **Off-grid**:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.epcube_off_grid
    to: "on"
```

### Cosa significano i valori numerici

Alcuni campi dell'API sono codici numerici. I significati vengono dalle app Android ufficiali (EU 3.1.1 e Nord America 2.6.2); ✅ indica i valori confermati anche sui dati di un impianto reale (EU), *non verificati* quelli che non compaiono né nell'app né nei dati.

| Campo | Valore | Significato |
|---|---|---|
| `workStatus` (Modalità operativa) | 1 | Autoconsumo |
| | 2 | Tariffazione (Time of Use) |
| | 3 | Backup |
| | 6 | Programma VPP del gestore (es. Hawaii BYOD+): modalità non modificabile |
| | 2 + `touType` 1 | *Tariffa dinamica* (app EU): sotto il prezzo target carica dalla rete |
| `systemStatus` (Stato gateway) | 1 | Guasto |
| | 2 | Inattivo ✅ (circa un minuto al risveglio, al mattino) |
| | 4 | In funzione ✅ |
| | 6 | Bassa potenza ✅: sleep mode, di notte quando la batteria arriva al SoC minimo |
| | 7 | In protezione |
| | 0, 3, 5 | Autotest, standby, non alimentato — dal supporto EP Cube, *non verificati* |
| `status` | 0 | Off-grid (blackout) ✅ |
| | 1 | Collegato alla rete ✅ |
| `touType` | 0 | Tempo di utilizzo a fasce (con `workStatus` 2) |
| | 1 | Tariffa dinamica (con `workStatus` 2) |
| `isOnline` | 1 / 0 | Gateway collegato al cloud / non collegato |
| `isAlert`, `isFault` | 1 / 0 | Avviso / guasto presente — restano 0 durante i blackout ✅ |
| `systemSpecialWorkMode` | 6 | Winter mode attivo ("Backup (winter mode)") |
| `gridLight` | 1 | Rete presente ✅ |
| | 0 | Rete assente ✅ (cambia insieme a `status`) |
| `generatorLight` | 1 | Generatore in funzione |
| `evLight` | 2, 4 | Caricatore EV / grandi carichi attivo |
| `backupLoadsMode` (firmware nuovi) / `backUpType` (firmware precedenti) | 0 | Backup parziale: alcuni carichi non sono sotto backup (nodo "Non-Backup" nell'app) |
| | 1 | Backup intera casa |
| `networking` | 3 | 4G |
| | 0, 1, 2 | Offline, Wi-Fi, Ethernet — *non verificati* |
| `gridPowerFailureNum` | contatore | Numero di blackout dall'installazione: aumenta di uno **quando la rete torna** ✅. Non usarlo con un valore fisso come trigger |
| `offGridPowerSupplyTime` | — | Resta 0 anche durante i blackout ✅: non indica la durata |
| `winterProtect` (EU, `getSwitchMode`) | 85 | Modalità invernale spenta ✅ |
| | 170 | Modalità invernale accesa (app EU) |
| `winterProtect` (USA, `getSettingsData`) | 0 / 1 | Modalità invernale spenta / accesa |
| `weatherWatch`, `allowChargingXiaGrid` | "0" / "1" | Spento / acceso |

---

## 📜 Disclaimer

Questo progetto non è affiliato né approvato da EP Cube o Canadian Solar.
Usare a proprio rischio. L'API utilizzata non è documentata né supportata ufficialmente.
