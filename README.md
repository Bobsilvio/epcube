[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

## Support Me

If you like my work and want me to keep developing it, you can buy me a coffee.

[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

Don't forget to follow me on social media:

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)
[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)
[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)

# EP Cube Integration for Home Assistant

> 🇮🇹 [Documentazione in italiano](README_IT.md)

Custom Home Assistant integration for monitoring the EP Cube energy storage system using the **unofficial API** (the same used by the official iOS/Android apps).

---

## 🔧 Features

- 📡 **Live data** with configurable update interval (default: 30 seconds)
- 📊 **Daily, monthly, and yearly statistics**
  - Disabled by default to reduce load
  - Can be enabled individually or all at once via configuration
- 🎛️ **Operating modes** (Self-consumption, Time of Use, Backup) controllable from Home Assistant
- 📅 **TOU service** to manage time-of-use schedules directly from Home Assistant
- ⚙️ Built-in **configuration and diagnostic entities**
- 🧩 Fully integrated with the Home Assistant UI (config flow, device info, icons)
- 🔐 Requires a **valid Bearer token** (token generation via reverse engineering, [HERE](https://epcube-token.streamlit.app/))

---

## 📦 Installation via HACS

1. Open Home Assistant
2. Go to **HACS > Integrations > Custom repositories**
3. Add: `https://github.com/Bobsilvio/epcube` with type `Integration`
4. Search for `EPCube` and install it
5. Restart Home Assistant
6. Go to **Settings > Devices & Services** and add the integration

## 📦 Quick Install
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

---

## ⚠️ Requirements

- EP Cube account
- Bearer token ([HERE](https://github.com/Bobsilvio/epcube-token))

---

## 🎯 Operating Modes

The integration supports 3 operating modes for the EP Cube device:

### 1. **Self-consumption** (Mode 1)
- Maximizes self-consumption of solar energy
- Battery charges when there is excess solar production
- Configurable: Self-consumption Reserve SoC (default: 5%)

### 2. **Time of Use (TOU)** (Mode 2) ⭐
- Configures different price time slots (peak, mid-peak, off-peak)
- Supports daylight saving time with separate schedules
- Supports separate schedules for weekdays and weekends
- **Fully controllable from Home Assistant via the `set_tou_schedule` service**

### 3. **Backup** (Mode 3)
- Prioritises backup power in case of a blackout
- Configurable: Backup Reserve SoC (default: 50%)

---

## 🔧 Service: Change Operating Mode

The `epcube.set_operating_mode` service switches between **Self-consumption** and **Backup**.
For **TOU** mode use `epcube.set_tou_schedule` instead (see next section).

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `mode` | String | Mode: `"1"` = Self-consumption, `"3"` = Backup | `"1"` |
| `backup_power_reserve_soc` | Number | Backup reserve SoC % (mode=3 only) | `50` |
| `self_consumption_reserve_soc` | Number | Self-consumption reserve SoC % (mode=1 only) | `5` |
| `entry_id` | String | Config entry ID (auto-detected if not specified) | — |

### Examples

```yaml
# Activate Backup mode with 54% reserve SoC
service: epcube.set_operating_mode
data:
  mode: "3"
  backup_power_reserve_soc: 54
```

```yaml
# Activate Self-consumption mode with 5% reserve SoC
service: epcube.set_operating_mode
data:
  mode: "1"
  self_consumption_reserve_soc: 5
```

---

## 📅 TOU Service (Time of Use)

The `epcube.set_tou_schedule` service lets you configure the time-of-use schedule of your EP Cube directly from Home Assistant.

### Time Slot Format

Each time slot is a **string** in the format `"HH:MM_HH:MM_price"`:

```
"08:00_13:00_0.31"   →  from 08:00 to 13:00, price 0.31 €/kWh
"20:00_23:00_0.25"   →  from 20:00 to 23:00, price 0.25 €/kWh
```

> ⚠️ **Both start and end times are required.** The service will return an error if either is missing.

### Basic Usage

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

### Available Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `peak_times` | List of strings | Peak time slots | `[]` |
| `mid_peak_times` | List of strings | Mid-peak time slots | `[]` |
| `off_peak_times` | List of strings | Off-peak time slots | `[]` |
| `peak_times_non_workday` | List of strings | Peak slots (weekend/holidays) | `[]` |
| `mid_peak_times_non_workday` | List of strings | Mid-peak slots (weekend/holidays) | `[]` |
| `off_peak_times_non_workday` | List of strings | Off-peak slots (weekend/holidays) | `[]` |
| `daylight_peak_times` | List of strings | Peak slots (daylight saving time) | `[]` |
| `daylight_mid_peak_times` | List of strings | Mid-peak slots (DST) | `[]` |
| `daylight_off_peak_times` | List of strings | Off-peak slots (DST) | `[]` |
| `active_week` | List of integers | Workday days (1=Mon … 5=Fri) | `[1,2,3,4,5]` |
| `active_week_non_workday` | List of integers | Weekend/holiday days (6=Sat, 7=Sun) | `[6,7]` |
| `daylight_active_week` | List of integers | Workday days (DST) | `[1,2,3,4,5]` |
| `daylight_active_week_non_workday` | List of integers | Weekend days (DST) | `[6,7]` |
| `tou_type` | Integer | Tariff type | `0` |
| `self_consumption_reserve_soc` | Integer | Self-consumption reserve SoC % | `5` |
| `allow_charging_from_grid` | Integer | Allow charging from grid (0/1) | preserves current device setting |
| `daylight_saving_time` | Boolean | Enable daylight saving time support | `false` |
| `switch_to_mode` | Boolean | Switch to TOU mode after saving | `false` |
| `entry_id` | String | Config entry ID (auto-detected if not specified) | — |

### Practical Examples

#### Example 1: Weekday and weekend schedules
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

#### Example 2: Schedule with Daylight Saving Time
```yaml
service: epcube.set_tou_schedule
data:
  # Winter schedule
  peak_times:
    - "08:00_13:00_0.31"
    - "20:00_23:00_0.31"
  off_peak_times:
    - "00:00_08:00_0.15"
    - "13:00_20:00_0.15"
    - "23:00_24:00_0.15"
  # Summer schedule (DST)
  daylight_peak_times:
    - "09:00_14:00_0.31"
    - "21:00_24:00_0.31"
  daylight_off_peak_times:
    - "00:00_09:00_0.15"
    - "14:00_21:00_0.15"
  daylight_saving_time: true
  switch_to_mode: true
```

#### Example 3: Automation — Automatic seasonal switch
```yaml
automation:
  - id: 'tou_winter_schedule'
    alias: 'Winter TOU Schedule'
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

## 👁️ TOU Schedule Sensors

The integration automatically creates configuration entities showing the active time slots:

- `sensor.epcube_orari_picco` (Peak times)
- `sensor.epcube_orari_semi_picco` (Mid-peak times)
- `sensor.epcube_orari_fuori_picco` (Off-peak times)
- `sensor.epcube_orari_luce_picco` (DST peak times)
- `sensor.epcube_orari_luce_semi_picco` (DST mid-peak times)
- `sensor.epcube_orari_luce_fuori_picco` (DST off-peak times)

---

## 🌍 Supported Regions

| Region | Endpoint |
|--------|----------|
| 🇪🇺 EU | `https://monitoring-eu.epcube.com/api` |
| 🇺🇸 US | `https://epcube-monitoring.com/app-api` |
| 🇯🇵 JP | `https://monitoring-jp.epcube.com/api` |

---

## 📊 Available Sensors

The integration automatically creates sensors for:
- **Battery**: SoC, energy in/out (total and daily), instantaneous power
- **Solar**: Power, energy (AC/DC)
- **Grid**: Power, energy (imported/exported)
- **Backup loads**: Power, energy
- **Main loads**: Power, energy
- **EV charger**: Power, energy
- **Generator**: Power, energy
- **Statistics**: Equivalent trees, CO₂ saved
- **TOU configuration**: Time slots, active days, reserve SoC values
- **Diagnostics**: System status, firmware, connectivity

---

## 📜 Disclaimer

This project is not affiliated with or endorsed by EP Cube or Canadian Solar.
Use at your own risk. The API used is not officially documented or supported.
