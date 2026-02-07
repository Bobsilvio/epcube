DOMAIN = "epcube"
DEFAULT_SCAN_INTERVAL = 5
PLATFORMS = ["sensor", "select", "number"]

CONF_SCALE_POWER = "scale_power"

CONF_ENABLE_TOTAL = "enable_total"
CONF_ENABLE_ANNUAL = "enable_annual"
CONF_ENABLE_MONTHLY = "enable_monthly"

# HTTP Configuration
USER_AGENT = "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)"
HTTP_TIMEOUT = 30  # seconds
HTTP_CONNECT_TIMEOUT = 10  # seconds

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
