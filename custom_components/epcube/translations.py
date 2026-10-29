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
    "systemstatus": "Stato Gateway",
    "backuploadsmode": "Modalità Carico Backup",
    "backuptype": "Tipo Backup",
    "toutype": "Tipo Tariffazione",
    "systemspecialworkmode": "Modalità Speciale Sistema",
    
    # === Batteria ===
    "batterysoc": "SoC Batteria",
    "batterycurrentelectricity": "Energia Batteria",
    "batterypacknum": "Moduli Batteria",
    
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
    "backupelectricity": "Energia Carichi di backup",
    "backupflowpower": "Flusso Potenza Backup",
    "backuppowera": "Potenza Backup Fase A",
    "backuppowerb": "Potenza Backup Fase B",
    "backuppowerc": "Potenza Backup Fase C",
    "backuppowerreservesoc": "SoC Backup Riservato",
    "offgridpowersupplytime": "Tempo Alimentazione Off-Grid",
    
    # === Carico Non-Backup ===
    "nonbackuppower": "Potenza Carico Principale",
    "nonbackupelectricity": "Energia Carichi Non-Backup",
    "nonbackupflowpower": "Flusso Carico Principale",
    
    # === Auto Consumo ===
    "selfhelprate": "Rapporto di contributo EP CUBE",
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
    "treenum": "Riduzione della deforestazione (alberi)",
    "coal": "Carbone risparmiato",
    "earningyesterday": "Guadagno Ieri",
    
    # === Informazioni Dispositivo ===
    "devid": "ID Dispositivo",
    "devtype": "Tipo Dispositivo",
    "name": "Nome Dispositivo",
    "sgsn": "Serial Number SG",
    "rtusn": "Serial Number RTU",
    "snitems": "Serial Numbers Componenti",
    "modeltype": "Modello",
    "version": "Codice versione (build)",
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

    # === Valuta ===
    "unitdefault": "Unità Valuta",
    "unitsmallest": "Unità Valuta Minima",
    "unitmulti": "Moltiplicatore Valuta",
    "earningyesterday": "Guadagno Ieri",

    # === Informazioni da deviceList ===
    "devicesystemtype": "Tipo Sistema",
    "systemcapacity": "Capacità Sistema",
    "batterytype": "Tipo Batteria (Modulo)",
    "lastconnecttime": "Ultima Connessione",
    "lat": "Latitudine",
    "lon": "Longitudine",
    "addressinfo": "Indirizzo Installazione",
    "isparallel": "Sistema Parallelo",
    "hybridnum": "Numero Ibridi",
    "dynamicpriceauth": "Prezzo Dinamico Abilitato",
    "softwareversion": "Versione Software",

    # === Campi dell'app Android 2.6.2 ===
    "chargingpowerfromgridlimit": "Limite potenza ricarica da rete",
    "drycontactinputdevicetype": "Tipo dispositivo contatto pulito",
    "dynamicprice": "Prezzo attuale tariffa dinamica",
    "eebuspromptmsg": "Messaggio EEBUS",
    "enwgeegenable": "EnWG/EEG abilitato",
    "heatpumpsettingstip": "Info pompa di calore",
    "heatpumpworkmode": "Modalità pompa di calore",
    "homeconnectdevices": "Dispositivi Home Connect",
    "pvtopowertogridlimits": "Limite immissione FV in rete",
    "dynamicchargeprice": "Prezzo target tariffa dinamica",
    "dynamicdischargeprice": "Prezzo target di vendita",
    "dynamicpricebinding": "Area prezzi tariffa dinamica",
    "intelligentmodechargingsoc": "SoC carica modalità intelligente",
    "intelligentmodedischargesoc": "SoC scarica modalità intelligente",
    "sellingmodedischargesoc": "SoC scarica modalità vendita",
    "quickchargestatus": "Stato ricarica rapida",
    "lowelectricitypricetime": "Orario prezzo basso",
    "evseworkstatus": "Stato caricatore EV (EVSE)",
    "id": "ID Record Cloud",
    "filters": "Filtri VPP",
    "toucurrenttimes": "Fasce TOU Correnti",
    "tousettings": "Impostazioni TOU (nuova app)",
    "gridstandard": "Normativa di Rete (codice)",
    "lpptimeduration": "Durata LPP",
    "lpctimeduration": "Durata LPC",
    "wintermode": "Modalità invernale (codice)",
    "winterprotect": "Protezione Invernale",
    "charginglimitsoc": "SoC Limite Ricarica",
    "hasevse": "Caricatore EV (EVSE) Presente",
    "evseonline": "Caricatore EV (EVSE) Online",
    "dynamicpricetips": "Info Prezzo Dinamico",
    "batterypower": "Potenza Batteria (API)",
    "dailyelectricitysales": "Vendite Elettricità Giornaliere",
    "hasev": "EV/Grandi Carichi Presente",
    "hasgenerator": "Generatore Esterno Presente",
    "smarthomeelectricity": "Energia Smart Home",
    "smarthomepower": "Potenza Smart Home",
    "timeleft": "Tempo rimanente (off-grid)",
    "vppcode": "Programma VPP",
    "backupaftermode": "Modalità Dopo il Backup",
    "backupdurationhour": "Durata Backup (Ore)",
    "backupdurationminute": "Durata Backup (Minuti)",
    "backupendtime": "Fine Backup",
    "exporteverything": "Esporta Tutto",
    "ja122025enabled": "Modalità JA12 (Title 24)",
    "ja122025enabledsoc": "SoC Riserva JA12",
    "ja12effectivedate": "Data Attivazione JA12",
    "newapptou": "Formato TOU Nuova App",
    "sellingenable": "Esportazione Solare DC",
}

# Mappa numero -> chiave di traduzione HA per il sensore enum
SYSTEM_STATUS_OPTIONS = {
    "0": "self_test",
    "1": "fault",
    "2": "idle",
    "3": "standby",
    "4": "running",
    "5": "not_powered",
    "6": "low_power",
    "7": "under_protection",
}

def translate_field_name(field_name: str) -> str:
    """Traduce il nome di un campo API in italiano."""
    field_lower = field_name.lower()
    return FIELD_TRANSLATIONS.get(field_lower, field_name)


# Testi che l'integrazione scrive come valore di un sensore: seguono la lingua
# di Home Assistant (inglese per le lingue non elencate)
LOCAL_TEXTS = {
    "it": {
        "none": "Nessuno",
        "not_configured": "Non configurato",
        "days": ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"],
    },
    "en": {
        "none": "None",
        "not_configured": "Not configured",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    },
}


def local_text(hass, key):
    language = (hass.config.language or "en").split("-")[0].lower()
    return LOCAL_TEXTS.get(language, LOCAL_TEXTS["en"])[key]
