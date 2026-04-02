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

# API
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


# Device categories (from actual production API responses)
AC_CATEGORIES = ["AC", "ODMIRB-AC"]
FAN_CATEGORIES = ["FANCONTROLLER"]
SWITCH_CATEGORIES = ["SWITCHES", "ROMASWITCHES", "PLUG"]

# Polling interval
SCAN_INTERVAL_SECONDS = 300  # 5 minutes

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
