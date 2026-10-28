DOMAIN = "epcube"
DEFAULT_SCAN_INTERVAL = 5
PLATFORMS = ["sensor", "binary_sensor", "select", "number", "switch", "update"]

CONF_SCALE_POWER = "scale_power"

# Credenziali dell'app EP Cube, usate per rinnovare il token in automatico
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

CONF_ENABLE_TOTAL = "enable_total"
CONF_ENABLE_ANNUAL = "enable_annual"
CONF_ENABLE_MONTHLY = "enable_monthly"

# HTTP Configuration
USER_AGENT = "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)"
HTTP_TIMEOUT = 30  # seconds
HTTP_CONNECT_TIMEOUT = 10  # seconds
# Budget più stretto per gli endpoint supplementari (statistiche, info device):
# deve restare sotto HTTP_TIMEOUT, altrimenti un endpoint lento fa scadere il
# timeout master e butta via anche i dati live già letti (server JP, issue #27)
STATS_TIMEOUT = 12  # seconds

# La potenza batteria è stimata da solare/rete/carichi, campionati dall'API in
# istanti leggermente diversi: a batteria ferma resta un residuo di qualche
# decina di watt. Sotto questa soglia il valore viene riportato a 0 (issue #20)
BATTERY_POWER_DEADBAND_KW = 0.1

# Isteresi dello stato batteria (charging/discharging/idle): si entra in
# carica/scarica oltre ±BATTERY_POWER_DEADBAND_KW e si torna a "ferma" solo
# sotto BATTERY_STATUS_IDLE_KW. Nella fascia intermedia si tiene lo stato
# precedente, così non oscilla quando la potenza resta vicino alla soglia.
BATTERY_STATUS_IDLE_KW = 0.05

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

BASE_URLS = {
    "EU": "https://monitoring-eu.epcube.com/api",
    "US": "https://epcube-monitoring.com/app-api",
    "JP": "https://monitoring-jp.epcube.com/api"
}

def get_base_url(region: str) -> str:
    return BASE_URLS.get(region.upper(), BASE_URLS["EU"])
