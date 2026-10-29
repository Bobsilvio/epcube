[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

## Support Me

If you like my work and want me to keep developing it, you can buy me a coffee.

[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)
[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)
[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)

# EP Cube for Home Assistant

🇮🇹 [Versione italiana](README_IT.md)

Brings your EP Cube storage system into Home Assistant: battery, solar, grid and consumption. You can also control it like the app does: change mode, reserves and tariff windows, and force the battery. It uses the same cloud as the official app.

---

## Installation

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

1. In HACS add the custom repository `https://github.com/Bobsilvio/epcube` (type *Integration*) and install **EPCube**
2. Restart Home Assistant
3. **Settings → Devices & services → Add integration → EP Cube**
4. Pick your account's region (EU, US or JP) and enter your **EP Cube app email and password**

With email and password the login renews itself.

From **⋮ → Options** you can change how many seconds between reads (default 5) and turn on the annual, monthly and total counters.

---

## How often values update

| Data | How often |
|---|---|
| Power (solar, grid, house, battery), SoC, grid presence | every 5 seconds (or what you set in the options) |
| Today's and yesterday's energy (solar, import, export, consumption) | every 5 seconds |
| Mode, reserves, tariff windows | every 5 seconds |
| **Battery charge and discharge** | **every 10 minutes** |
| Firmware, warnings and faults, outages, weather, Wi-Fi | every 15 minutes, or right away with the **Check for updates** button |

---

## Controls

Everything is controlled from the device page (**Settings → Devices & services → EP Cube**), *Configuration* section, or from a dashboard card. No YAML needed.

| Entity | What it does |
|---|---|
| **Operating mode** | Self-consumption, Time of use, Backup (and Dynamic tariff when your system has it) |
| **Self-consumption reserve SoC** | In Self-consumption the battery does not go below this level |
| **Backup reserve SoC** | In Backup the battery keeps this much charge for outages |
| **Allow charging via grid** | Lets the battery charge from the grid (in Time of use and Backup) |
| **Peak-rate / Mid-rate / Off-peak hours** and **… price** | The Time of use windows, [see below](#time-of-use-tariff-windows) |
| **Battery override** | Force charge, Force discharge or Hold for a while, [see below](#battery-override) |
| **Check for updates** | Reads firmware, warnings and outages right away |

Changing one value leaves the others alone.

On some systems grid charging is locked by the installer: then the switch reports an error instead of pretending it worked.

### Time of use (tariff windows)

Uses the battery according to the price of energy: in general it charges when energy is cheap and is used when energy is expensive.

**How to set it up:**

1. For each window type (peak, mid, off-peak) write the hours in **… hours**, separated by commas:

   ```
   08:00-13:00, 20:00-23:00
   ```

   At most 3 windows per type. If the format is wrong Home Assistant does not accept the text. To remove all windows of a type, empty the box.
2. Optionally set the price in **… price** (it applies to every window of that type).
3. Choose **Operating mode → Time of use**.

Saving hours and prices does not change mode: you can prepare them first and switch when you want.

Hours and prices apply to weekdays (Monday-Friday). Weekend and daylight-saving windows are set from the app or with the `epcube.set_tou_schedule` action ([examples](ESEMPI_TOU_SERVICE.md)).

If your EP Cube runs the firmware with seasonal plans (4.0.8 or later), these entities show as unavailable: Time of use can then only be set from the app.

### Battery override

Forces the battery for a while, for example to keep it charged before a storm.

1. Set **Override target SoC** (the level) and **Override duration** (minutes; 0 = until you cancel it)
2. Pick what to do in **Battery override**:

| Choice | What happens |
|---|---|
| **Force charge** | The battery stops discharging and charges from solar up to the target SoC. It does not charge from the grid |
| **Force discharge** | The battery may power the house down to the target SoC |
| **Hold** | The battery stays at its current level |
| **None** | Cancels right away |

Works only in **Self-consumption** mode. When it ends the previous reserve comes back by itself, even if Home Assistant restarts in between.

---

## Energy dashboard

In **Settings → Dashboards → Energy**:

| Entry | Sensor |
|---|---|
| Solar production | **Solar Energy (Daily)** |
| Grid consumption | **Energy from Grid** |
| Return to grid | **Energy to Grid** |
| Energy into the battery | **Total Energy Stored** |
| Energy out of the battery | **Total Energy Discharged** |

---

## Automations

The controls above work in automations like any entity (`select.select_option`, `number.set_value`, `text.set_value`). There are also dedicated actions:

| Action | What it does |
|---|---|
| `epcube.force_charge`, `epcube.force_discharge`, `epcube.hold_battery`, `epcube.clear_battery_override` | Battery override with SoC and duration written in the automation |
| `epcube.set_operating_mode` | Changes mode and reserve in one go |
| `epcube.set_tou_schedule` | Sets every window, weekend and daylight saving included ([examples](ESEMPI_TOU_SERVICE.md)) |

```yaml
# At 18:00 keep the battery charged for 2 hours
triggers:
  - trigger: time
    at: "18:00:00"
actions:
  - action: epcube.hold_battery
    data:
      duration: 120
```

```yaml
# Detect a power cut
triggers:
  - trigger: state
    entity_id: binary_sensor.epcube_off_grid
    to: "on"
```

Seen from the cloud, a power cut and a tripped breaker between the grid and EP Cube look the same.

---

## Sensors

- **Battery**: SoC, power, status (charging / discharging / idle), charge and discharge today and in total
- **Solar**: power and energy, plus voltage and current for each string
- **Grid**: power, energy imported and exported, grid presence, outages
- **House**: total consumption, backup and non-backup loads
- **Yesterday**: energy produced, imported, exported and consumed
- **Diagnostics**: firmware, Wi-Fi, last warning and fault, last outage, weather

<details>
<summary>What the numeric codes mean</summary>

| Field | Value | Meaning |
|---|---|---|
| Operating mode (`workStatus`) | 1 / 2 / 3 | Self-consumption / Time of use / Backup |
| | 6 | Utility program, cannot be changed |
| System status (`systemStatus`) | 2 | Idle (a minute while waking up) |
| | 4 | Running |
| | 6 | Low power: at night, battery at minimum |
| | 1 / 7 | Fault / Protection |
| `status` | 0 / 1 | Power cut / Connected to the grid |
| `isOnline` | 0 / 1 | Gateway offline / connected to the cloud |
| `isAlert`, `isFault` | 0 / 1 | Nothing / Warning or fault present |
| `gridLight` | 0 / 1 | Grid absent / present |
| `backupLoadsMode` | 0 / 1 | Partial backup / Whole-home backup |
| `networking` | 1 / 3 | Wi-Fi / 4G |
| Winter mode (`winterProtect`) | 85 / 170 | Off / On |
| Grid outages (`gridPowerFailureNum`) | counter | Goes up by one when the grid comes back |

</details>

---

## Troubleshooting

- **"Token expired" right after setup**: almost always the wrong region. An account exists on only one of EU, US or JP.
- **A control reports an error**: read the message, it usually says why (wrong mode, feature locked by the installer).
- **Reporting a problem**: **Settings → Devices & services → EP Cube → ⋮ → Download diagnostics** and attach it. Credentials, serial numbers and location are redacted.

---

## Disclaimer

Not affiliated with or endorsed by EP Cube or Canadian Solar. The API is undocumented and unsupported: use at your own risk.
