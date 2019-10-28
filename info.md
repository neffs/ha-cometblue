
_Component to integrate with a Eurotronic Comet Blue thermostat._
They are identical to the Sygonix, Xavax Bluetooth thermostats

This version is based on the bluepy library and works on hass.io. 
Currently only current and target temperature in manual mode is supported, nothing else. 


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
```

***

[ha-cometblue]: https://github.com/neffs/ha-cometblue
