# Panasonic MirAIe - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/miraiehomeassistant/ha-panasonic-miraie)](LICENSE)

Home Assistant custom integration for Panasonic MirAIe smart home devices. Control your Panasonic air conditioners, fans, and switches directly from the Home Assistant dashboard.

## Supported Devices

| Device Type | Categories | Features |
|-------------|-----------|----------|
| **Air Conditioner** | AC, ODMIRB-AC | Power, HVAC modes (cool/heat/auto/dry/fan), temperature, fan speed |
| **Fan Controller** | FANCONTROLLER | Power, 5 speed levels, preset modes (auto/normal/turbo/sleep) |
| **Switches & Plugs** | SWITCHES, ROMASWITCHES, PLUG | Power on/off, multi-channel support |

## Prerequisites

- Home Assistant 2024.1.0 or later
- A Panasonic MirAIe account (register via the [MirAIe mobile app](https://play.google.com/store/apps/details?id=com.panasonic.in.miraie))
- Devices must be onboarded to your MirAIe account through the mobile app before they appear in Home Assistant

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant
2. Click the three dots in the top right corner → **Custom Repositories**
3. Add `https://github.com/miraiehomeassistant/ha-panasonic-miraie` as a new repository (Category: Integration)
4. Search for "Panasonic MirAIe" and click **Download**
5. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/panasonic_cloud` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Panasonic MirAIe**
4. Click **Open website** — you'll be redirected to the Panasonic login page
5. Log in with your MirAIe account credentials (same as the mobile app)
6. Click **Link account** on the redirect page
7. Your devices will automatically appear on the dashboard

## How It Works

This integration uses the Panasonic MirAIe cloud API with OAuth2 authentication. When you add the integration:

1. You authenticate with your MirAIe account via Panasonic's secure login page
2. The integration discovers all devices linked to your account
3. Each device is created as a Home Assistant entity (climate, fan, or switch)
4. Device status is polled every 5 minutes
5. Control commands are sent via the MirAIe cloud API

Your MirAIe login credentials are never stored by Home Assistant — only the OAuth2 tokens are saved locally.

## Automations

With this integration, you can create powerful automations:

- "Turn off all ACs when I leave home"
- "Set bedroom AC to 24°C at 11 PM"
- "Turn on living room fan when temperature exceeds 30°C"
- "Turn off all switches at midnight"

## Voice Control

Once your Panasonic devices are in Home Assistant, you can control them via:

- **Google Home** (via HA Cloud or manual setup)
- **Amazon Alexa** (via HA Cloud or manual setup)
- **Apple HomeKit** (via HomeKit Bridge integration)

## Troubleshooting

### No devices showing after setup
- Make sure your devices are onboarded in the MirAIe mobile app first
- Check that you logged in with the same account used in the mobile app

### Devices showing as unavailable
- The device may be offline (check the MirAIe app)
- The `onlineStatus` field from the API determines availability

### Token expired / Authentication error
- The integration will show a "Re-authenticate" notification
- Click it and log in again — your devices and automations will be preserved

### Integration not found in search
- Make sure you restarted Home Assistant after installation
- Check that the files are in the correct path: `config/custom_components/panasonic_cloud/`

## Roadmap

- **v1.0.0** (Current) — OAuth2 auth, AC/Fan/Switch control, cloud polling
- **v1.1.0** (Planned) — MQTT support for real-time status updates
- **v1.2.0** (Planned) — Additional device categories, energy monitoring

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

## Acknowledgments

- [milothomas/ha-miraie-ac](https://github.com/milothomas/ha-miraie-ac) — Node-RED MirAIe integration
- [rkzofficial/ha-miraie-ac](https://github.com/rkzofficial/ha-miraie-ac) — Python MirAIe HA integration
- [Panasonic MirAIe](https://www.panasonic.com/in/miraie.html) — Smart home platform

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

## Disclaimer

Developed by Panasonic India
