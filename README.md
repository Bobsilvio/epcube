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
- 🔐 **Sign in with the EP Cube app's email and password**: the login captcha is solved automatically and the token is renewed when it expires. A manually generated Bearer token ([HERE](https://epcube-token.streamlit.app/)) is still supported

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
- Email and password of the EP Cube app (or a Bearer token from [HERE](https://github.com/Bobsilvio/epcube-token))

> The password is stored in Home Assistant's configuration (`.storage/core.config_entries`), like any other integration credential.

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
| `backup_power_reserve_soc` | Number | Backup reserve SoC % (mode=3 only) | current value |
| `self_consumption_reserve_soc` | Number | Self-consumption reserve SoC % (mode=1 only) | current value |
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
| `tou_type` | Integer | Tariff type | current value |
| `self_consumption_reserve_soc` | Integer | Self-consumption reserve SoC % | current value |
| `allow_charging_from_grid` | Integer | Allow charging from grid (0/1) | preserves current device setting |
| `daylight_saving_time` | Boolean | Enable daylight saving time support | `false` |
| `switch_to_mode` | Boolean | Switch to TOU mode after saving | `false` |
| `entry_id` | String | Config entry ID (auto-detected if not specified) | — |

Mapping to the **TOU time window** screen of the EP Cube app (EU): `off_peak_times` = *low-cost band*, `mid_peak_times` = *normal-cost band*, `peak_times` = *high-cost band*; the `_non_workday` lists and `active_week_non_workday` are the *weekend*, `active_week` the *workdays*. At most **3 slots per type**. On systems where the app uses seasonal tariff plans (gateway firmware 4.0.8 or later, when the server returns plans) the service stops with an error, because the slots would not be used.

The **TOU peak/mid-peak/off-peak start/end (HH:00)** numbers read the hour of the device's first slot and, when changed, update that slot (price and other slots unchanged) without changing mode. If the type has no slot yet, they create a one-hour slot.

The slot lists you pass replace the whole schedule: lists you leave out are emptied. Everything else (reserve SoC values, weather watch, winter mode, EV reserve) keeps its current value. Prices may use a comma (`0,31`): they are sent with a dot, as the app does. An invalid slot stops the call with an error instead of sending a partial schedule.

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
- **Non-Backup loads**: Power, energy
- **EV/Large appliance**: Power, energy
- **Generator**: Power, energy
- **Statistics**: EP Cube contribution ratio (self-sufficiency), reducing deforestation (trees), standard coal saved
- **TOU configuration**: Time slots, active days, reserve SoC values
- **Diagnostics**: System status, firmware, connectivity
- **Revenue**: today and this month, as calculated by the EP Cube cloud
- **Last power cut**: start time of the last outage, with the last 10 outages in the attributes
- **Weather**: the forecast shown in the app's home screen
- **PV strings**: power of each PV string (PV1–PV6), in kW

If something looks wrong, download the diagnostics (Settings → Devices & services → EP Cube → ⋮ → Download diagnostics) and attach it to the issue: credentials, serial numbers and location are redacted.

Sensor names follow the wording of the official EP Cube app.

### Status and settings

| Entity | What it does |
|---|---|
| `binary_sensor` **Off-grid** | On during a grid outage (the system runs on battery) |
| `binary_sensor` **Grid** | On when the grid is present |
| `binary_sensor` **Winter mode active** | On while the winter mode is charging the battery |
| `switch` **Winter mode** | Enables winter mode: when temperature and SoC are too low, EP Cube charges to the target SoC |
| `number` **Winter mode target SoC** | Target SoC for winter mode |
| `switch` **Weather watch** | Charges the batteries ahead of extreme weather events |
| `select` **Operating mode** | Self-consumption, Time of use, Backup and, if the system supports it, **Dynamic tariff** |
| `number` **Target price** / **Target sell price** | Dynamic tariff thresholds (saved without changing mode) |
| `switch` **Allow charging via grid** | Grid charging (TOU off-peak and Backup mode) |
| `switch` **Off-grid notification** / `number` **Off-grid notification SoC** | The app notifies you when, during an outage, the battery drops to this SoC |
| `number` **Sleep mode SoC** | Below this SoC (5–30%) the system enters sleep mode |
| `switch` **Indicator light** | The light on the right side of the hybrid inverter |
| `switch` **Automatic firmware update** | Automatic firmware updates |
| `number` **EV/Large appliance reserve SoC** | Only on systems with an EV charger or large appliance |
| `sensor` **Last warning** / **Last fault** | Latest entries of the app's "Alert & Warning" page, with the suggested solution |
| `sensor` **Wi-Fi**, **Firmware** | Gateway Wi-Fi status and firmware versions (diagnostic) |

Winter mode and weather watch entities are created only if the system exposes those settings; winter mode also follows the app's own condition (permission and gateway firmware). Each setting is written the way your region's app does it: in the EU winter mode uses `settingWinterProtect` and grid charging is part of the mode (`switchMode`, sent in full); sleep mode, indicator light and winter mode SoC exist only in the US app. The TOU schedule and reserve SoC values are never touched.

### Detecting a power cut

During an outage (or when the breaker between the grid and EP Cube trips) `status` and `gridLight` both go to **0**, and back to 1 when the grid returns; then `gridPowerFailureNum` increases by one. Seen from the cloud, an outage and a tripped breaker look the same. Use the **Off-grid** binary sensor:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.epcube_off_grid
    to: "on"
```

### What the numeric values mean

Some API fields are numeric codes. The meanings come from the official Android apps (EU 3.1.1 and North America 2.6.2); ✅ marks values also confirmed on a real (EU) system's data, *unverified* those that appear neither in the app nor in the data.

| Field | Value | Meaning |
|---|---|---|
| `workStatus` (Operating mode) | 1 | Self-consumption |
| | 2 | Time of Use |
| | 3 | Backup |
| | 6 | Utility VPP program (e.g. Hawaii BYOD+): mode cannot be changed |
| | 2 + `touType` 1 | *Dynamic tariff* (EU app): charges from the grid below the target price |
| `systemStatus` (Gateway status) | 1 | Fault |
| | 2 | Idle ✅ (about a minute on wake-up, in the morning) |
| | 4 | Running ✅ |
| | 6 | Low power ✅: sleep mode, at night when the battery reaches its minimum SoC |
| | 7 | Under protection |
| | 0, 3, 5 | Self-test, standby, not powered — from EP Cube support, *unverified* |
| `status` | 0 | Off-grid (grid outage) ✅ |
| | 1 | Grid-connected ✅ |
| `touType` | 0 | Time of use with fixed slots (with `workStatus` 2) |
| | 1 | Dynamic tariff (with `workStatus` 2) |
| `isOnline` | 1 / 0 | Gateway connected / not connected to the cloud |
| `isAlert`, `isFault` | 1 / 0 | Warning / fault present — they stay 0 during outages ✅ |
| `systemSpecialWorkMode` | 6 | Winter mode active ("Backup (winter mode)") |
| `gridLight` | 1 | Grid present ✅ |
| | 0 | Grid absent ✅ (changes together with `status`) |
| `generatorLight` | 1 | Generator running |
| `evLight` | 2, 4 | EV charger / large appliance active |
| `backupLoadsMode` (new firmware) / `backUpType` (older firmware) | 0 | Partial backup: some loads are not backed up ("Non-Backup" node in the app) |
| | 1 | Whole-home backup |
| `networking` | 3 | 4G |
| | 0, 1, 2 | Offline, Wi-Fi, Ethernet — *unverified* |
| `gridPowerFailureNum` | counter | Number of grid outages since installation: it goes up by one **when the grid comes back** ✅. Do not trigger on a fixed value |
| `offGridPowerSupplyTime` | — | Stays 0 even during outages ✅: it is not the outage duration |
| `winterProtect` (EU, `getSwitchMode`) | 85 | Winter mode off ✅ |
| | 170 | Winter mode on (EU app) |
| `winterProtect` (US, `getSettingsData`) | 0 / 1 | Winter mode off / on |
| `weatherWatch`, `allowChargingXiaGrid` | "0" / "1" | Off / on |

---

## 📜 Disclaimer

This project is not affiliated with or endorsed by EP Cube or Canadian Solar.
Use at your own risk. The API used is not officially documented or supported.
