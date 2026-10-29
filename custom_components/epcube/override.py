"""Override temporanei della batteria tramite la riserva di Autoconsumo.

In Autoconsumo la batteria non scende sotto selfConsumptioinReserveSoc. Alzando
la riserva sopra il SoC attuale la batteria smette di scaricarsi e si ricarica
col surplus solare (forza carica); abbassandola può scaricarsi fino al nuovo
valore (forza scarica); fissandola al SoC attuale resta ferma (mantieni).
Non è una carica da rete: quella dipende da allowChargingXiaGrid.

Alla scadenza viene ripristinata la riserva precedente. L'override è salvato su
disco: se Home Assistant era spento alla scadenza, il ripristino avviene al
riavvio; se il ripristino fallisce si riprova dopo RESTORE_RETRY.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import async_post_switch_mode, async_read_switch_mode_field
from .const import DOMAIN
from .payload import build_switch_mode_payload

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
RESTORE_RETRY = timedelta(minutes=5)

CHARGE = "charge"
DISCHARGE = "discharge"
HOLD = "hold"

# workStatus dell'Autoconsumo: l'unica modalità in cui conta questa riserva
SELF_CONSUMPTION = "1"
RESERVE_FIELD = "selfConsumptioinReserveSoc"


@dataclass(slots=True)
class Override:
    kind: str
    target_soc: int
    ends_at: datetime | None
    previous_reserve: str | None

    def as_dict(self):
        return {
            "kind": self.kind,
            "target_soc": self.target_soc,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "previous_reserve": self.previous_reserve,
        }

    @classmethod
    def from_dict(cls, raw):
        if not raw or not raw.get("kind"):
            return None
        ends_at = raw.get("ends_at")
        return cls(
            kind=raw["kind"],
            target_soc=raw.get("target_soc"),
            ends_at=dt_util.parse_datetime(ends_at) if ends_at else None,
            previous_reserve=raw.get("previous_reserve"),
        )


class OverrideManager:
    def __init__(self, hass, entry, coordinator):
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.override")
        self.active = None
        self._cancel_timer = None
        # Valori dei number "SoC obiettivo override" e "Durata override",
        # usati quando l'override parte dal menu invece che da un servizio
        self.settings = {"target_soc": 80, "duration": 120}

    async def async_load(self):
        """Riprende un override salvato; se è già scaduto ripristina subito."""
        self.active = Override.from_dict(await self._store.async_load())
        if self.active is None:
            return
        if self.active.ends_at is not None and self.active.ends_at <= dt_util.utcnow():
            _LOGGER.info("Override %s scaduto mentre HA era spento: ripristino", self.active.kind)
            try:
                await self.async_clear()
            except HomeAssistantError as err:
                _LOGGER.warning("Ripristino della riserva non riuscito: %s", err)
        else:
            self._arm(self.active.ends_at)

    @callback
    def async_unload(self):
        # L'override resta su disco: dopo il reload va comunque ripristinato
        self._disarm()

    async def async_start(self, kind, target_soc=None, duration=None):
        data = self._data()
        if str(data.get("workstatus")) != SELF_CONSUMPTION:
            raise ServiceValidationError(
                "Gli override della batteria agiscono sulla riserva di Autoconsumo: "
                "passa prima alla modalità Autoconsumo"
            )
        if kind == HOLD:
            try:
                target_soc = int(float(data.get("batterysoc")))
            except (TypeError, ValueError) as err:
                raise HomeAssistantError("SoC della batteria non disponibile, riprova tra poco") from err
        if target_soc is None:
            raise ServiceValidationError("Serve il SoC obiettivo (target_soc)")

        # La riserva da ripristinare è quella di prima del primo override:
        # rilanciarne un altro non deve salvare la riserva dell'override
        previous = (
            self.active.previous_reserve
            if self.active is not None
            else str(data.get("selfconsumptioinreservesoc"))
        )
        await self._async_write_reserve(target_soc)

        ends_at = dt_util.utcnow() + duration if duration else None
        self.active = Override(kind, int(target_soc), ends_at, previous)
        await self._store.async_save(self.active.as_dict())
        self._arm(ends_at)
        self.coordinator.async_update_listeners()
        _LOGGER.info(
            "Override %s: riserva %s%% fino a %s", kind, target_soc, ends_at or "annullamento"
        )

    async def async_start_from_settings(self, kind):
        """Avvia l'override con SoC e durata scelti nei number dell'integrazione."""
        minutes = self.settings["duration"]
        await self.async_start(
            kind,
            target_soc=self.settings["target_soc"],
            duration=timedelta(minutes=minutes) if minutes else None,
        )

    async def async_clear(self):
        """Termina l'override e rimette la riserva precedente."""
        override = self.active
        if override is None:
            return
        self._disarm()
        if override.previous_reserve not in (None, "None"):
            try:
                await self._async_write_reserve(int(float(override.previous_reserve)))
            except HomeAssistantError:
                _LOGGER.warning(
                    "Ripristino riserva %s%% non riuscito, riprovo tra %s",
                    override.previous_reserve, RESTORE_RETRY,
                )
                self._arm(dt_util.utcnow() + RESTORE_RETRY)
                raise
        self.active = None
        await self._store.async_remove()
        self.coordinator.async_update_listeners()
        _LOGGER.info("Override %s terminato, riserva %s%% ripristinata",
                     override.kind, override.previous_reserve)

    def _data(self):
        return (self.coordinator.data or {}).get("data") or {}

    async def _async_write_reserve(self, soc):
        data = self._data()
        if not data.get("devid"):
            raise HomeAssistantError("Dati EP Cube non ancora disponibili, riprova tra poco")
        # Payload completo: fasce TOU e altre riserve restano invariate
        payload = build_switch_mode_payload(
            data, current=self.coordinator.data.get("switch_mode"),
            **{RESERVE_FIELD: str(int(soc))},
        )
        if not await async_post_switch_mode(self.hass, self.entry, payload, f"riserva {soc}%"):
            raise HomeAssistantError("Il server EP Cube ha rifiutato la nuova riserva (vedi log)")
        applied = await async_read_switch_mode_field(self.hass, self.entry, data["devid"], RESERVE_FIELD)
        await self.coordinator.async_request_refresh()
        if applied is not None and str(applied) != str(int(soc)):
            raise HomeAssistantError(
                f"Il gateway ha accettato la richiesta ma la riserva è rimasta {applied}%"
            )

    @callback
    def _arm(self, ends_at):
        self._disarm()
        if ends_at is None:
            return

        async def _expired(_now):
            try:
                await self.async_clear()
            except HomeAssistantError as err:
                _LOGGER.warning("Fine override: %s", err)

        self._cancel_timer = async_track_point_in_utc_time(self.hass, _expired, ends_at)

    @callback
    def _disarm(self):
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None
