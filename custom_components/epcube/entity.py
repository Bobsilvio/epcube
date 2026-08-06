"""Aggancio di entità e device alla singola config entry.

Fino alla 1.5.x ogni entità usava un unique_id globale (`epcube_<campo>`) e un
unico device `("epcube", "epcube_device")`. Con due EP Cube sullo stesso Home
Assistant la seconda config entry produceva gli stessi unique_id della prima:
Home Assistant scartava le entità duplicate, così il secondo sistema restava
con poche entità che mostravano i valori del primo (issue #25).

Qui l'identità diventa per-entry: `epcube_<sn>_<campo>` e device `("epcube", sn)`.
Le installazioni esistenti vengono migrate in-place, quindi gli entity_id e lo
storico restano quelli di prima.
"""

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

# Identificatore del device unico usato fino alla 1.5.x
LEGACY_DEVICE_ID = "epcube_device"


def entry_sn(entry: ConfigEntry) -> str:
    """Serial number dell'impianto della entry (fallback: entry_id)."""
    return str(entry.data.get("sn") or entry.entry_id)


def unique_id_prefix(entry: ConfigEntry) -> str:
    return f"epcube_{entry_sn(entry)}_"


def legacy_unique_id(unique_id: str, entry: ConfigEntry) -> str:
    """unique_id nella forma globale usata fino alla 1.5.x."""
    return "epcube_" + unique_id.removeprefix(unique_id_prefix(entry))


def bind_entities_to_entry(entities, entry: ConfigEntry):
    """Riscrive unique_id e device_info delle entità con l'identità della entry."""
    prefix = unique_id_prefix(entry)
    sn = entry_sn(entry)

    for entity in entities:
        unique_id = getattr(entity, "_attr_unique_id", None)
        if unique_id and not unique_id.startswith(prefix):
            entity._attr_unique_id = prefix + unique_id.removeprefix("epcube_")

        device_info = getattr(entity, "_attr_device_info", None)
        if device_info:
            device_info = dict(device_info)
            device_info["identifiers"] = {(DOMAIN, sn)}
            entity._attr_device_info = device_info

    return entities


@callback
def async_migrate_entry_identifiers(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Porta entità e device di una installazione esistente sui nuovi id.

    Va chiamata prima del setup delle piattaforme: rinominando gli id nel
    registry le entità mantengono entity_id, impostazioni e storico.
    """
    prefix = unique_id_prefix(entry)
    sn = entry_sn(entry)

    ent_reg = er.async_get(hass)
    migrated = 0
    for registry_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if registry_entry.unique_id.startswith(prefix):
            continue

        new_unique_id = prefix + registry_entry.unique_id.removeprefix("epcube_")
        if ent_reg.async_get_entity_id(
            registry_entry.domain, registry_entry.platform, new_unique_id
        ):
            _LOGGER.warning(
                "unique_id %s già presente: %s non migrato",
                new_unique_id, registry_entry.entity_id,
            )
            continue

        ent_reg.async_update_entity(registry_entry.entity_id, new_unique_id=new_unique_id)
        migrated += 1

    if migrated:
        _LOGGER.info("Migrate %d entità di %s su unique_id per-impianto", migrated, sn)

    # Il device legacy viene rinominato solo se appartiene a questa sola entry:
    # in un'installazione con due EP Cube è condiviso e va lasciato svuotare
    dev_reg = dr.async_get(hass)
    legacy_device = dev_reg.async_get_device(identifiers={(DOMAIN, LEGACY_DEVICE_ID)})
    if legacy_device is None:
        return

    if legacy_device.config_entries != {entry.entry_id}:
        return

    if dev_reg.async_get_device(identifiers={(DOMAIN, sn)}) is not None:
        return

    dev_reg.async_update_device(legacy_device.id, new_identifiers={(DOMAIN, sn)})
    _LOGGER.info("Device legacy epcube_device migrato su %s", sn)
