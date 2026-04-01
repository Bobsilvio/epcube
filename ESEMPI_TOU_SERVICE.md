# Esempi di utilizzo dei service EP Cube

> **Formato orari TOU**: ogni fascia è una stringa `"HH:MM_HH:MM_prezzo"`
> Esempio: `"08:00_13:00_0.31"` = dalle 8:00 alle 13:00 al prezzo 0.31 €/kWh

---

## set_tou_schedule — Tariffazione (Mode 2)

### ESEMPIO 1: Tariffazione semplice
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

---

### ESEMPIO 2: Tariffazione con Ora Legale
```yaml
service: epcube.set_tou_schedule
data:
  # Orari invernali
  peak_times:
    - "08:00_13:00_0.31"
    - "20:00_23:00_0.31"
  mid_peak_times:
    - "13:00_18:00_0.25"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "18:00_20:00_0.15"
  # Orari estivi (ora legale)
  daylight_peak_times:
    - "09:00_14:00_0.31"
    - "21:00_24:00_0.31"
  daylight_mid_peak_times:
    - "14:00_19:00_0.25"
  daylight_off_peak_times:
    - "00:00_09:00_0.15"
    - "19:00_21:00_0.15"
  daylight_saving_time: true
  switch_to_mode: true
```

---

### ESEMPIO 3: Automazione — cambio stagionale automatico
```yaml
automation:
  - id: 'set_tou_winter'
    alias: 'Imposta Tariffazione Invernale'
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
        mid_peak_times:
          - "13:00_18:00_0.25"
        off_peak_times:
          - "00:00_08:00_0.15"
          - "18:00_20:00_0.15"
          - "23:00_24:00_0.15"
        switch_to_mode: true
```

---

### ESEMPIO 4: Tariffazione feriale vs festiva
```yaml
service: epcube.set_tou_schedule
data:
  # Giorni lavorativi
  peak_times:
    - "08:00_12:00_0.31"
    - "15:00_18:00_0.31"
    - "20:00_23:00_0.31"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "12:00_15:00_0.15"
    - "18:00_20:00_0.15"
    - "23:00_24:00_0.15"
  active_week: [1, 2, 3, 4, 5]
  # Giorni festivi — tutto fuori picco
  off_peak_times_non_workday:
    - "00:00_24:00_0.15"
  active_week_non_workday: [6, 7]
  switch_to_mode: true
```

---

## set_operating_mode — Autoconsumo (Mode 1) e Backup (Mode 3)

### ESEMPIO 5: Attiva modalità Backup
```yaml
service: epcube.set_operating_mode
data:
  mode: "3"
  backup_power_reserve_soc: 54
```

### ESEMPIO 6: Attiva modalità Autoconsumo
```yaml
service: epcube.set_operating_mode
data:
  mode: "1"
  self_consumption_reserve_soc: 5
```

### ESEMPIO 7: Automazione — Backup di notte, Autoconsumo di giorno
```yaml
automation:
  - alias: "Backup di notte"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      service: epcube.set_operating_mode
      data:
        mode: "3"
        backup_power_reserve_soc: 60

  - alias: "Autoconsumo di giorno"
    trigger:
      platform: time
      at: "06:00:00"
    action:
      service: epcube.set_operating_mode
      data:
        mode: "1"
        self_consumption_reserve_soc: 5
```
