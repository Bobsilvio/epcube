# Esempi di utilizzo del service set_tou_schedule

# === ESEMPIO 1: Tariffazione semplice ===
# Usa nel Developer Tools > Services in Home Assistant

service: epcube.set_tou_schedule
data:
  peak_times:
    - - 8
      - 13
    - - 20
      - 23
  mid_peak_times:
    - - 13
      - 18
  off_peak_times:
    - - 0
      - 8
    - - 18
      - 20
    - - 23
      - 24
  switch_to_mode: true

---

# === ESEMPIO 2: Tariffazione con Ora Legale ===
service: epcube.set_tou_schedule
data:
  peak_times:
    - - 8
      - 13
    - - 20
      - 23
  mid_peak_times:
    - - 13
      - 18
  off_peak_times:
    - - 0
      - 8
    - - 18
      - 20
  daylight_peak_times:
    - - 9
      - 14
    - - 21
      - 24
  daylight_mid_peak_times:
    - - 14
      - 19
  daylight_off_peak_times:
    - - 0
      - 9
    - - 19
      - 24
  daylight_saving_time: true
  switch_to_mode: true

---

# === ESEMPIO 3: In un'automazione YAML ===
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
          - [8, 13]
          - [20, 23]
        mid_peak_times:
          - [13, 18]
        off_peak_times:
          - [0, 8]
          - [18, 20]
          - [23, 24]
        switch_to_mode: true
        
---

# === ESEMPIO 4: Con template (da config.yaml) ===
# Utile per utilizzare variabili o template

service: epcube.set_tou_schedule
target: {}
data:
  peak_times: "{{ state_attr('input_text.peak_times', 'value') | from_json }}"
  off_peak_times: "{{ state_attr('input_text.off_peak_times', 'value') | from_json }}"
  switch_to_mode: "{{ state_attr('input_boolean.auto_switch_tou', 'value') }}"

---

# === ESEMPIO 5: Modalità Lavoro (Home Assistant UI) ===
# Nel file automations.yaml della UI
alias: Tariffazione Feriale
description: Cambia gli orari di tariffazione per giorni feriali
trigger:
  - platform: time
    at: "06:00:00"
    weekday:
      - mon
      - tue
      - wed
      - thu
      - fri
condition: []
action:
  - service: epcube.set_tou_schedule
    data:
      peak_times:
        - - 8
          - 12
        - - 15
          - 18
        - - 20
          - 23
      off_peak_times:
        - - 0
          - 8
        - - 12
          - 15
        - - 18
          - 20
        - - 23
          - 24
      active_week:
        - 1
        - 2
        - 3
        - 4
        - 5
mode: single
