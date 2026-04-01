[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

## Supportami / Support Me

Se ti piace il mio lavoro e vuoi che continui nello sviluppo delle card, puoi offrirmi un caffè.\
If you like my work and want me to continue developing the cards, you can buy me a coffee.


[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

Non dimenticare di seguirmi sui social:\
Don't forget to follow me on social media:

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)

[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)

[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)

# EP Cube Integration for Home Assistant

Custom Home Assistant integration for monitoring the EP Cube energy storage system using the **unofficial API** (the same used by the official iOS/Android apps).

---

## 🔧 Features

- 📡 **Live data** with configurable update interval (default: 30 seconds)
- 📊 Access to **daily, monthly, and yearly statistics**
  - Disabled by default to reduce load
  - Can be enabled individually or all at once via configuration
- 🎛️ **Modalità operative** (Autoconsumo, Tariffazione, Backup) con controllo da Home Assistant
- 📅 **Service TOU** per gestire gli orari di tariffazione direttamente da Home Assistant
- ⚙️ Built-in **configuration and diagnostic entities**
- 🧩 Fully integrated with Home Assistant UI (config flow, device info, icons)
- 🔐 Requires a **valid Bearer token** (token generation via reverse engineering, [HERE](https://epcube-token.streamlit.app/))

---

## 📦 Installation via HACS

1. Open Home Assistant
2. Go to **HACS > Integrations > Custom repositories**
3. Add: `https://github.com/Bobsilvio/epcube` with type `Integration`
4. Search for `EPCube` and install it
5. Restart Home Assistant
6. Go to **Settings > Devices & Services** and add the integration

## 📦 Installation simple
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

---

## ⚠️ Requirements

- EP Cube account
- Bearer token ([HERE](https://github.com/Bobsilvio/epcube-token))

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
| `backup_power_reserve_soc` | Numero | SoC riserva backup % (solo mode=3) | `50` |
| `self_consumption_reserve_soc` | Numero | SoC riserva autoconsumo % (solo mode=1) | `5` |
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
| `tou_type` | Intero | Tipo tariffazione | `0` |
| `self_consumption_reserve_soc` | Intero | SoC riserva autoconsumo % | `5` |
| `allow_charging_from_grid` | Intero | Permetti ricarica da rete (0/1) | mantiene impostazione attuale del dispositivo |
| `daylight_saving_time` | Booleano | Attiva supporto ora legale | `false` |
| `switch_to_mode` | Booleano | Passa a modalità Tariffazione | `false` |
| `entry_id` | Stringa | ID configurazione (auto se non specificato) | — |

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

L'integrazione crea automaticamente sensori diagnostici che mostrano le fasce orarie configurate:

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
- **Carichi Backup**: Potenza, Energia
- **Carichi Principali**: Potenza, Energia
- **EV**: Potenza, Energia
- **Generatore**: Potenza, Energia
- **Statistiche**: Alberi equivalenti, CO₂ risparmiata
- **Configurazione TOU**: Fasce orarie, giorni attivi, SoC riserve
- **Diagnostica**: Stato sistema, firmware, connettività

---

## 📜 Disclaimer

This project is not affiliated with or endorsed by EP Cube or Canadian Solar.
Use at your own risk. The API used is not officially documented or supported.
