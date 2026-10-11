# Changelog

## v1.7.0

### Added
- **Sign in with email and password**: the setup now offers the EP Cube app's
  credentials as the main option. The integration solves the login captcha by
  itself (same flow as [epcube-token](https://github.com/Bobsilvio/epcube-token),
  without opencv) and stores the resulting token.
- **Automatic token renewal**: when the server rejects the token (401/403) the
  integration logs in again with the stored credentials and retries, both for
  polling and for writes. A failed captcha is retried on the next poll, at most
  once a minute.
- **Reauthentication flow**: if the credentials are rejected, or a pasted token
  expires and no credentials are stored, Home Assistant asks to sign in again
  instead of failing silently. Existing token-only installs can also add email
  and password from the integration options.

- **Winter mode and weather watch**: new `switch` entities, plus a `number`
  for the winter mode target SoC. They read `/device/getSettingsData` and write
  through `/device/saveSettings`, the endpoints of the official app's settings
  page. Created only when the system exposes those settings.
- **Binary sensors**: off-grid (grid outage), grid present, winter mode active.
- **Revenue, last power cut and weather sensors**, from `earningsGraph`,
  `getDevPowerCutLog` and `homeDeviceInfoWeather`, refreshed every 15 minutes.
- **Per-string PV power** (PV1–PV6, kW) from `getSolarPvPower`, for the
  strings the system reports.
- **Dynamic tariff** (EU app): new "Tariffa dinamica" option in the operating
  mode select, shown when the system supports it, plus numbers for the target
  buy and sell prices. Mode codes come from the official EU app 3.1.1:
  dynamic tariff is `workStatus` 2 with `touType` "1".
- **More settings**: sleep mode SoC, off-grid notification (and its SoC),
  indicator light, automatic firmware update, EV/large appliance reserve SoC.
- **Last warning / last fault sensors** from the app's "Alert & Warning" page,
  plus Wi-Fi and firmware diagnostic sensors.
- **Translated names for every entity**: the operating mode select, the SoC
  and TOU numbers and the TOU sensors had fixed Italian names (some shown as
  "EPCUBE EPCUBE ..."). Entity IDs and select options are unchanged.
- **Diagnostics download**: besides the coordinator data it queries once the
  app endpoints not integrated yet (alarms, network, firmware, warranty, ...),
  so their real responses can be checked. Credentials, token, serial numbers
  and location are redacted.
- **Names for every field the API returns**: fields that showed up with their
  raw API key (`gridstandard`, `timeleft`, `smarthomepower`, ...) now have a
  name. Objects and lists (`filters`, `touSettings`) are no longer turned into
  sensors.
- **README table of numeric codes**: what `workStatus`, `systemStatus`,
  `status`, `gridLight`, `backupLoadsMode`, `networking` and the other numeric
  fields mean, taken from the official Android app.

### Fixed
- **TOU service could reset other settings**: `set_tou_schedule` built its own
  partial `switchMode` payload, so every call dropped the backup reserve SoC and
  reset the self-consumption reserve to 5% unless passed explicitly. It now
  sends the full current configuration, like the other write paths.
- **`set_operating_mode` dropped the other reserve SoC** (e.g. switching to
  self-consumption reset the backup reserve).
- **Every mode/SoC change turned weather watch off**: the `switchMode` payload
  always sent `weatherWatch: "0"`. All `switchMode` writes now echo back the
  whole configuration read from `getSwitchMode` (including EV reserve, winter
  mode and charging limit on the EU backend), changing only what was asked.
- **TOU schedule sensors always showed "Non configurato"**: they expected a
  different format than the `HH:MM_HH:MM_price` strings the API returns.
- **TOU prices with a decimal comma** (`0,30`) were sent as-is; they are now
  normalized to a dot like the app does, and malformed slots are rejected with
  an error shown in Home Assistant instead of only a log line. Service failures
  are now reported to the caller.
- **Data not loading on recent Home Assistant versions**: the API calls used
  `async_timeout` as a plain context manager, which recent versions of the
  library reject and current Home Assistant no longer ships. They now use
  `asyncio.timeout`.
- **`backupLoadsMode` / `backUpType` mapping was inverted**: 0 means partial
  backup (some loads are not backed up), 1 whole-home backup.
- **Misleading sensor names**: `selfhelprate` is the EP Cube contribution ratio
  (self-sufficiency), not the self-consumption rate; `coal` is standard coal
  saved, not CO₂; `batterypacknum` counts battery modules, not cells. Names now
  follow the official app (entity IDs are unchanged).
- Writes that the server rejects inside an HTTP 200 response are now reported
  as failures instead of successes.

- **TOU hour numbers did nothing**: the "TOU ... (HH:00)" numbers only kept a
  local value. They now show the hour of the device's first slot and update
  that slot when changed.
- **Sensors meant to be disabled by default were created enabled**: the
  registry pre-creation ignored the integration's default. Only affects newly
  created entities.
- **List and object values** (TOU slots, active days, VPP filters) stay
  sensors as before; states longer than Home Assistant's 255-character limit
  are truncated, with the full value in an attribute.

### Changed
- `set_tou_schedule` follows the app: at most 3 slots per type, and it refuses
  to write slots on systems that use the app's seasonal tariff plans.
- **EU winter mode** uses the EU app's own endpoint (`settingWinterProtect`,
  values 170 on / 85 off), and grid charging is saved through `switchMode` in
  the EU as the EU app does (the US app uses `saveSettings`).
- Winter mode entities follow the visibility rule of the app for the system's
  region (EU: single-phase systems with gateway firmware 1.1.8 or later).
- Mode changes set `touType` like the app, so leaving the dynamic tariff
  really switches it off.
- The "allow charging from grid" switch now writes only its own setting
  (`saveSettings` type 10) instead of the full `switchMode` payload.
- The `set_tou_schedule` and `set_operating_mode` services now use the shared
  `switchMode` writer, and honour a token updated through the options flow.
- New requirements: `numpy` and `Pillow` (both already shipped with Home
  Assistant).

## v1.6.2

### Fixed
- **SOC reserve sliders silently resetting the rest of the configuration**
  ([#31](https://github.com/Bobsilvio/epcube/issues/31)): the two SOC reserve
  `number` entities sent a partial `switchMode` payload, and the vendor API
  treats any missing field as "reset to default" — the same failure mode as
  [#18](https://github.com/Bobsilvio/epcube/issues/18). Changing one slider
  could wipe the TOU schedule and the other reserve. All write paths now build
  the full payload from a single shared definition.

### Changed
- The `switchMode` POST is now implemented once instead of three times: the
  SOC entities inherit the timeout and retry handling they never had, and every
  write path uses Home Assistant's shared HTTP session and honours a token
  updated through the options flow.

## v1.6.1

### Fixed
- **`sensor.epcube_battery_power` never settling at zero**
  ([#20](https://github.com/Bobsilvio/epcube/issues/20)): the value is estimated
  from solar, grid and load, and those are not sampled at the same instant, so
  an idle battery still showed a few tens of watts. Values below 100 W are now
  reported as 0.

## v1.6.0

> ## ⚠️ READ THIS BEFORE UPDATING — ENTITY IDENTIFIERS CHANGE
>
> Entities are no longer identified globally (`epcube_<field>`) but per system
> (`epcube_<serial>_<field>`), and the device is now identified by its serial
> number instead of the shared `epcube_device`.
>
> **Single EP Cube:** the update migrates your existing entities in place.
> Entity IDs, names, history and dashboards stay exactly as they are. Nothing
> to do.
>
> **Two or more EP Cubes:** the second system finally gets its own entities.
> Since the first system already owns entity IDs like
> `sensor.epcube_batterysoc`, Home Assistant gives the second one
> `sensor.epcube_batterysoc_2`. Rename the second device from the UI if you
> want clearer IDs, and update any dashboard or automation that pointed at it.
>
> If anything looks wrong after the update, reload the integration once before
> reporting it — the migration runs at setup.

### Fixed
- **Multiple EP Cubes on one Home Assistant** ([#25](https://github.com/Bobsilvio/epcube/issues/25)):
  every entity used a global `unique_id` and all config entries shared a single
  device, so the second system collided with the first. Home Assistant dropped
  the duplicates, leaving the second EP Cube with a handful of entities showing
  the first system's values. Identity is now per config entry, with an in-place
  migration for existing installs.

## v1.5.2

### Fixed
- **All sensors stuck until a reload** ([#26](https://github.com/Bobsilvio/epcube/issues/26)):
  TOU fields such as `lowElectricityPriceTime` hold strings like `"23:00_07:00_"`,
  but their name contains "electricity" so they were published as energy sensors
  in kWh. Home Assistant raised a `ValueError` while pushing the state and the
  exception aborted the whole listener cycle, freezing every other sensor.
  Text values now get no numeric class, with a runtime guard as a safety net.

## v1.5.1

### Fixed
- **JP region timeouts** ([#27](https://github.com/Bobsilvio/epcube/issues/27)):
  the statistics endpoints shared the master timeout, so one hanging call threw
  away the live payload that had already been fetched. Supplementary endpoints
  now have their own shorter budget (`STATS_TIMEOUT`) and a failing one is
  logged and skipped instead of taking the whole update down.
- **"Unknown error" when setting up with the wrong region**
  ([#28](https://github.com/Bobsilvio/epcube/issues/28)): the US and JP servers
  return HTTP 200 with the real status in the body, so a token generated for
  another region crashed the config flow instead of reporting itself. The config
  flow now reads the body status and ships actual error messages (they were
  missing from the translations entirely, which is why everything showed up as
  "Unknown error occurred").

## v1.5.0

### Changed
- **`sensor.epcube_systemstatus`** ([#30](https://github.com/Bobsilvio/epcube/issues/30)):
  this is the gateway status (0-7), and the previous mapping was wrong. It is
  now an enum sensor named "Gateway Status" with translated states: Self-test,
  Fault, Idle, Standby, Running, Not Powered, Low Power, Under Protection.
  **Breaking:** the state is a text value instead of the raw number.
