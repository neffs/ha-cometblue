
_Component to integrate with a Eurotronic Comet Blue thermostat._
They are identical to the Sygonix, Xavax Bluetooth thermostats

This version is based on the bluepy library and works on hass.io. 

{% if not installed %}
## Installation

1. Click install.
1. Add mac address and pin to your HA configuration.

{% endif %}
## Example configuration.yaml

```yaml
climate cometblue:
  platform: cometblue
  devices:
    thermostat1:
      mac: 11:11:11:11:11:11
      pin: 000000
      fake_manual_mode: False
```

Fake manual mode should be used with BLE 100 devices. 
These devices don't have a manual mode. To be able to set a
permanent temperature this mode sets high, low and target temperature 
to the same temperature.

***

[ha-cometblue]: https://github.com/neffs/ha-cometblue
