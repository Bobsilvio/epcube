# Traduzioni dei nomi dei campi API messi in italiano
# Usato per visualizzare i nomi sensori in modo leggibile

FIELD_TRANSLATIONS = {
    # === Status e Connettività ===
    "status": "Stato",
    "isonline": "Online",
    "signallevel": "Livello Segnale",
    "networking": "Tipo Connessione",
    "isalert": "Allarme Attivo",
    "isfault": "Guasto Presente",
    "faultwarningtype": "Tipo Avviso Guasto",
    
    # === Modalità e Impostazioni ===
    "workstatus": "Modalità Operativa",
    "systemstatus": "Stato Sistema",
    "backuploadsmode": "Modalità Carico Backup",
    "backuptype": "Tipo Backup",
    "toutype": "Tipo Tariffazione",
    "systemspecialworkmode": "Modalità Speciale Sistema",
    
    # === Batteria ===
    "batterysoc": "SoC Batteria",
    "batterycurrentelectricity": "Energia Batteria",
    "batterypacknum": "Numero Celle Batteria",
    
    # === Energia Solare ===
    "solarpower": "Potenza Solare",
    "solarelectricity": "Energia Solare",
    "solardcpower": "Potenza DC Solare",
    "solardcelectricity": "Energia DC Solare",
    "solaracpower": "Potenza AC Solare",
    "solaracelectricity": "Energia AC Solare",
    "solarflow": "Flusso Solare",
    
    # === Rete Elettrica ===
    "gridpower": "Potenza Rete",
    "gridelectricity": "Energia Rete",
    "gridelectricityfrom": "Energia Ricevuta da Rete",
    "gridelectricityto": "Energia Immessa in Rete",
    "gridtotalpower": "Potenza Totale Rete",
    "gridhalfpower": "Potenza Mezza Rete",
    "gridpowera": "Potenza Rete Fase A",
    "gridpowerb": "Potenza Rete Fase B",
    "gridpowerc": "Potenza Rete Fase C",
    "gridlight": "Indicatore Rete",
    "gridpowerfailurenum": "Numero Interruzioni Rete",
    "off_on_grid_hint": "Suggerimento Rete",
    
    # === Generatore ===
    "generatorpower": "Potenza Generatore",
    "generatorelectricity": "Energia Generatore",
    "generatorflowpower": "Flusso Generatore",
    "generatorlight": "Indicatore Generatore",
    
    # === Backup ===
    "backuppower": "Potenza Backup",
    "backupelectricity": "Energia Backup",
    "backupflowpower": "Flusso Potenza Backup",
    "backuppowera": "Potenza Backup Fase A",
    "backuppowerb": "Potenza Backup Fase B",
    "backuppowerc": "Potenza Backup Fase C",
    "backuppowerreservesoc": "SoC Backup Riservato",
    "offgridpowersupplytime": "Tempo Alimentazione Off-Grid",
    
    # === Carico Non-Backup ===
    "nonbackuppower": "Potenza Carico Principale",
    "nonbackupelectricity": "Energia Carico Principale",
    "nonbackupflowpower": "Flusso Carico Principale",
    
    # === Auto Consumo ===
    "selfhelprate": "Tasso Autoconsumo",
    "selfconsumptioinreservesoc": "SoC Autoconsumo Riservato",
    "allowchargingxiagrid": "Permetti Ricarica da Rete",
    
    # === Veicolo Elettrico ===
    "evpower": "Potenza EV",
    "evelectricity": "Energia EV",
    "evflowpower": "Flusso EV",
    "evlight": "Indicatore EV",
    "evchargerreservesoc": "SoC Caricabatterie EV",
    
    # === Tariffazione TOU ===
    "peaktimelist": "Orari di Picco",
    "midpeaktimelist": "Orari Semi-Picco",
    "offpeaktimelist": "Orari Fuori Picco",
    "peaktimelistnonworkday": "Orari Picco (Non Lavoro)",
    "midpeaktimelistnonworkday": "Orari Semi-Picco (Non Lavoro)",
    "offpeaktimelistnonworkday": "Orari Fuori Picco (Non Lavoro)",
    "daylight": "Giorno Luce",
    "daylightsavingtime": "Ora Legale",
    "isdaylightsaving": "In Ora Legale",
    "daytype": "Tipo Giorno",
    "activeweek": "Giorni Attivi (Lavorativi)",
    "activeweeknonworkday": "Giorni Attivi (Non Lavorativi)",
    "daylightactiveweek": "Giorni Luce Attivi (Lavorativi)",
    "daylightactiveweeknonworkday": "Giorni Luce Attivi (Non Lavorativi)",
    "daylightpeaktimelist": "Orari Luce Picco",
    "daylightmidpeaktimelist": "Orari Luce Semi-Picco",
    "daylightoffpeaktimelist": "Orari Luce Fuori Picco",
    "daylightpeaktimelistnonworkday": "Orari Luce Picco (Non Lavoro)",
    "daylightmidpeaktimelistnonworkday": "Orari Luce Semi-Picco (Non Lavoro)",
    "daylightoffpeaktimelistnonworkday": "Orari Luce Fuori Picco (Non Lavoro)",
    
    # === Sostenibilità ===
    "treenum": "Alberi Piantati",
    "coal": "Equivalente Carbone Risparmiato",
    "earningyesterday": "Guadagno Ieri",
    
    # === Informazioni Dispositivo ===
    "devid": "ID Dispositivo",
    "devtype": "Tipo Dispositivo",
    "name": "Nome Dispositivo",
    "sgsn": "Serial Number SG",
    "rtusn": "Serial Number RTU",
    "snitems": "Serial Numbers Componenti",
    "modeltype": "Modello",
    "version": "Versione Firmware",
    "softwareversion": "Versione Software",
    "payloadversion": "Versione Payload",
    "isnewdevice": "Dispositivo Nuovo",
    "ressnumber": "Numero Risorse",
    
    # === Batteria INFO ===
    "batterycapacity": "Capacità Batteria",
    
    # === Data e Timezone ===
    "defcreatetime": "Ora Creazione (Dispositivo)",
    "deftimezone": "Timezone Dispositivo",
    "fromcreatetime": "Data Creazione (Rete)",
    "fromtimezone": "Timezone Rete",
    "fromtype": "Tipo Fonte Data",
    
    # === Altro ===
    "onlysave": "Solo Salvataggio",
    "weatherwatch": "Controllo Meteo",
    "heatpumpsettingspermission": "Permesso Pompa Calore",
    "homeconnectauth": "Autenticazione Home Connect",
    "existssg": "Esiste SG",
}

# Modalità operative
OPERATION_MODES = {
    "1": "Autoconsumo",
    "2": "Tariffazione",
    "3": "Backup",
}

# Stato sistema
SYSTEM_STATUS = {
    "0": "Offline",
    "1": "Online",
    "2": "Durante attivazione",
    "3": "Guasto",
    "4": "Normale",
    "5": "Timeout",
}

# Tipo backup
BACKUP_TYPE = {
    "0": "Nessuno",
    "1": "Connesso",
    "2": "Off-Grid",
}

# Modalità carico backup
BACKUP_LOADS_MODE = {
    "0": "Tutti i carichi",
    "1": "Solo carichi prioritari",
}

# Tipo connessione
NETWORKING_TYPE = {
    "0": "Offline",
    "1": "Wi-Fi",
    "2": "Ethernet",
    "3": "4G/LTE",
}

# Tipo fonte data
FROM_TYPE = {
    "0": "Locale",
    "1": "Cloud",
    "2": "Sincronizzato",
}

def translate_field_name(field_name: str) -> str:
    """Traduce il nome di un campo API in italiano."""
    field_lower = field_name.lower()
    return FIELD_TRANSLATIONS.get(field_lower, field_name)

def translate_status_value(field_name: str, value) -> str:
    """Traduce il valore di uno stato in italiano."""
    field_lower = field_name.lower()
    value_str = str(value)
    
    if field_lower == "workstatus":
        return OPERATION_MODES.get(value_str, value_str)
    elif field_lower == "systemstatus":
        return SYSTEM_STATUS.get(value_str, value_str)
    elif field_lower == "backuptype":
        return BACKUP_TYPE.get(value_str, value_str)
    elif field_lower == "backuploadsmode":
        return BACKUP_LOADS_MODE.get(value_str, value_str)
    elif field_lower == "networking":
        return NETWORKING_TYPE.get(value_str, value_str)
    elif field_lower == "fromtype":
        return FROM_TYPE.get(value_str, value_str)
    elif field_lower in ["isonline", "isalert", "isfault", "isnewdevice", "existssg"]:
        return "Sì" if value in ["1", 1, True, "true"] else "No"
    
    return value_str
