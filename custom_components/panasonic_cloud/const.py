"""Constants for the Panasonic MirAIe integration."""

from urllib.parse import quote

DOMAIN = "panasonic_cloud"
MANUFACTURER = "Panasonic"

# OAuth2 / Auth
AUTH_URL = "https://idp.miraie.in/idpLogin"
TOKEN_URL = "https://iam.miraie.in/api/identity/v1/oauth2/token"
CLIENT_ID = "ba320fa9-0c27-48a0-a706-5facf53c51bd"
CLIENT_SECRET = "secret.a25aee2b-f44e-4812-b17c-c3a2c12a1325"
OAUTH_SCOPE = "ITFF_AUTH"
OAUTH_REDIRECT_URI = "https://my.home-assistant.io/redirect/oauth"

# REST API
API_BASE = "https://app.miraie.in/simplifi/v1"
HOMES_URL = f"{API_BASE}/homeManagement/homes"
CONTROL_URL_BASE = f"{API_BASE}/deviceManagement/control"


def STATUS_URL(device_id: str) -> str:
    """Return the status URL for a device.

    Device IDs may contain colons (e.g. 'ecaebcba6212:00')
    which must be URL-encoded for valid HTTP requests.
    """
    safe_id = quote(device_id, safe="")
    return f"{API_BASE}/deviceManagement/devices/{safe_id}/mobile/status"


def CONTROL_URL(device_id: str) -> str:
    """Return the control URL for a device."""
    return CONTROL_URL_BASE


# MQTT Broker (confirmed working - v1.1.0)
MQTT_BROKER = "mqtt.miraie.in"
MQTT_PORT = 8883
# Lower keepalive prevents Panasonic broker idle disconnects (rc=7).
# 30s pings comfortably under most cloud broker idle windows.
MQTT_KEEPALIVE = 30
MQTT_RECONNECT_MIN_DELAY = 1
MQTT_RECONNECT_MAX_DELAY = 120

# Device categories (from actual production API responses)
AC_CATEGORIES = ["AC", "ODMIRB-AC"]
FAN_CATEGORIES = ["FANCONTROLLER"]
SWITCH_CATEGORIES = ["SWITCHES", "ROMASWITCHES", "PLUG"]

# REST polling interval (fallback when MQTT is down)
# v1.0.0 used 300s (5 min); v1.1.0 uses 900s (15 min) because MQTT
# provides real-time updates - REST is just a safety net.
SCAN_INTERVAL_SECONDS = 900

# AC field mappings
AC_POWER = "acdc"          # "on" / "off"
AC_MODE = "acmd"           # "cool" / "heat" / "auto" / "dry" / "fan"
AC_TARGET_TEMP = "actmp"   # e.g. "20.0"
AC_CURRENT_TEMP = "rmtmp"  # e.g. "22.0"
AC_FAN_SPEED = "acfs"      # "auto" / "quiet" / "low" / "medium" / "high"
AC_POWER_SAVE = "ps"       # "on" / "off"

# Fan field mappings
FAN_POWER = "ps"           # "on" / "off"
FAN_SPEED = "fafs"         # 1-5
FAN_MODE = "fafm"          # "auto" / "normal" / "turbo" / "sleep"
FAN_TEMP = "rmtmp"         # room temp
FAN_HUMIDITY = "rmhmd"     # room humidity

# Switch field mappings
SWITCH_POWER = "ps"        # "on" / "off"
SWITCH_STATES = "states"   # list of channel states
SWITCH_CHANNEL = "rmcn"    # channel number "00", "01", etc.
SWITCH_CH_STATE = "rmcps"  # channel state "on" / "off"

# HA HVAC mode mappings
MIRAIE_TO_HA_HVAC = {
    "cool": "cool",
    "heat": "heat",
    "auto": "auto",
    "dry": "dry",
    "fan": "fan_only",
}
HA_TO_MIRAIE_HVAC = {v: k for k, v in MIRAIE_TO_HA_HVAC.items()}

# HA fan mode mappings
MIRAIE_TO_HA_FAN = {
    "auto": "auto",
    "quiet": "diffuse",
    "low": "low",
    "medium": "medium",
    "high": "high",
}
HA_TO_MIRAIE_FAN = {v: k for k, v in MIRAIE_TO_HA_FAN.items()}
