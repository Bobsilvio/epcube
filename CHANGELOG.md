# Changelog

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
