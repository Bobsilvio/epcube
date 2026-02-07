# EP Cube Integration for Home Assistant

Custom Home Assistant integration for monitoring the EP Cube energy storage system using the **unofficial API** (the same used by the official iOS/Android apps).

---

## 🔧 Features

- 📡 **Live data** updates every 5 seconds  
- 📊 Access to **monthly, weekly, and yearly statistics**  
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
- Configurable: SoC Autoconsumo Riservato (default: 15%)

### 2. **Tariffazione (Time of Use)** (Mode 2) ⭐
- Configura diversi orari di prezzo (picco, semi-picco, fuori picco)
- Supporta ora legale con orari differenti
- **Gestibile direttamente da Home Assistant con il service dedicato**

### 3. **Backup** (Mode 3)
- Priorità al backup in caso di blackout
- Configurable: SoC Backup Riservato (default: 50%)

---

## 🔧 Service TOU (Time of Use)

### Cos'è?

Il service `epcube.set_tou_schedule` permette di configurare gli orari di tariffazione del tuo EP Cube direttamente da Home Assistant, senza usare l'app ufficiale.

### Utilizzo

Accedi a **Developer Tools > Services** e chiama il service:

```yaml
service: epcube.set_tou_schedule
data:
  peak_times:              # Orari di Picco (obbligatorio)
    - [8, 13]              # 08:00-13:00
    - [20, 23]             # 20:00-23:00
  mid_peak_times:          # Orari Semi-Picco (opzionale)
    - [13, 18]
  off_peak_times:          # Orari Fuori Picco (opzionale)
    - [0, 8]
    - [18, 20]
    - [23, 24]
  switch_to_mode: true     # Cambia automaticamente a modalità Tariffazione
```

### Parametri Disponibili

| Parametro | Tipo | Descrizione | Obbligatorio |
|-----------|------|-------------|--------------|
| `peak_times` | Liste | Orari di picco | ✅ |
| `mid_peak_times` | Liste | Orari semi-picco | ❌ |
| `off_peak_times` | Liste | Orari fuori picco | ❌ |
| `daylight_peak_times` | Liste | Orari picco (ora legale) | ❌ |
| `daylight_mid_peak_times` | Liste | Orari semi-picco (ora legale) | ❌ |
| `daylight_off_peak_times` | Liste | Orari fuori picco (ora legale) | ❌ |
| `active_week` | Lista | Giorni lavorativi attivi (1-5=Lun-Ven) | ❌ |
| `active_week_non_workday` | Lista | Giorni festivi attivi (6-7=Sab-Dom) | ❌ |
| `daylight_saving_time` | Booleano | Abilita correzione ora legale | ❌ |
| `ev_charger_reserve_soc` | Numero | SoC caricabatterie EV (0-100) | ❌ |
| `entry_id` | Stringa | ID della configurazione (auto se non specificato) | ❌ |

### Esempi Pratici

#### Esempio 1: Tariffazione Invernale
```yaml
service: epcube.set_tou_schedule
data:
  peak_times:
    - [8, 13]
    - [20, 23]
  mid_peak_times:
    - [13, 18]
  off_peak_times:
    - [0, 8]
    - [18, 20]
    - [23, 24]
  switch_to_mode: true
```

#### Esempio 2: Tariffazione con Ora Legale
```yaml
service: epcube.set_tou_schedule
data:
  # Orari invernali
  peak_times: [[8, 13], [20, 23]]
  off_peak_times: [[0, 8], [18, 20], [23, 24]]
  
  # Orari estivi (ora legale)
  daylight_peak_times: [[9, 14], [21, 24]]
  daylight_off_peak_times: [[0, 9], [19, 21], [24, 24]]
  
  daylight_saving_time: true
  switch_to_mode: true
```

#### Esempio 3: Automazione - Cambio Automatico Stagionale
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
        peak_times: [[8, 13], [20, 23]]
        off_peak_times: [[0, 8], [18, 20], [23, 24]]
        switch_to_mode: true
```

#### Esempio 4: Script - Cambio Rapido da Pulsante
```yaml
script:
  set_tou_peak_hours:
    alias: "Imposta Tariffazione Picco"
    sequence:
      - service: epcube.set_tou_schedule
        data:
          peak_times: [[8, 13], [20, 23]]
          off_peak_times: [[0, 8], [18, 20], [23, 24]]
          switch_to_mode: true
```

#### Esempio 5: Usa i Number Entities per Configurare gli Orari
Ora l'integrazione fornisce i number entities per impostare gli orari:
- `number.epcube_tou_picco_inizio` (0-23, formato HH:00)
- `number.epcube_tou_picco_fine` (0-23, formato HH:00)
- `number.epcube_tou_semi_picco_inizio` (0-23, formato HH:00)
- `number.epcube_tou_semi_picco_fine` (0-23, formato HH:00)
- `number.epcube_tou_fuori_picco_inizio` (0-23, formato HH:00)
- `number.epcube_tou_fuori_picco_fine` (0-23, formato HH:00)

**Formato**: Inserisci un numero da 0 a 23 che rappresenta l'ora:
- `0` = 00:00 (mezzanotte)
- `8` = 08:00 (mattina)
- `13` = 13:00 (pomeriggio)
- `20` = 20:00 (sera)
- `23` = 23:00 (quasi mezzanotte)

**Automazione che usa i number entities:**
```yaml
automation:
  - id: 'apply_tou_from_numbers'
    alias: 'Applica TOU dai Number Entities'
    trigger:
      platform: event
      event_type: call_service
      event_data:
        domain: epcube
        service: apply_tou_from_ui
    action:
      - service: epcube.set_tou_schedule
        data:
          peak_times:
            - - "{{ (states('number.epcube_tou_picco_inizio') | int(0)) }}"
              - "{{ (states('number.epcube_tou_picco_fine') | int(1)) }}"
          mid_peak_times:
            - - "{{ (states('number.epcube_tou_semi_picco_inizio') | int(0)) }}"
              - "{{ (states('number.epcube_tou_semi_picco_fine') | int(1)) }}"
          off_peak_times:
            - - "{{ (states('number.epcube_tou_fuori_picco_inizio') | int(0)) }}"
              - "{{ (states('number.epcube_tou_fuori_picco_fine') | int(1)) }}"
          switch_to_mode: true
```

---

## 👁️ Visualizza gli Orari TOU Attuali

L'integrazione crea automaticamente sensori diagnostici che mostrano gli orari configurati:

- **Orari di Picco**: `sensor.epcube_orari_di_picco`
- **Orari Semi-Picco**: `sensor.epcube_orari_semi_picco`
- **Orari Fuori Picco**: `sensor.epcube_orari_fuori_picco`
- **Orari Luce - Picco**: `sensor.epcube_orari_luce_picco`
- **Orari Luce - Semi-Picco**: `sensor.epcube_orari_luce_semi_picco`
- **Orari Luce - Fuori Picco**: `sensor.epcube_orari_luce_fuori_picco`
- **Giorni Attivi (Lavorativi)**: `sensor.epcube_giorni_attivi_lavorativi`
- **Giorni Attivi (Festivi)**: `sensor.epcube_giorni_attivi_festivi`

Visualizza questi sensori nella dashboard di Home Assistant per controllare sempre la configurazione TOU attuale!

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
- **Battery**: SoC, Energia in/out (totale e giornaliera)
- **Solar**: Potenza, Energia (AC/DC)
- **Grid**: Potenza, Energia (ricevuta/ceduta)
- **Backup**: Potenza, Energia
- **EV**: Potenza, Energia
- **Generator**: Potenza, Energia
- **Statistics**: Alberi piantati, CO₂ risparmiata

---

## 📜 Disclaimer

This project is not affiliated with or endorsed by EP Cube or Canadian Solar.  
Use at your own risk. The API used is not officially documented or supported.
