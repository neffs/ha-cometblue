"""
Home Assistant Support for Eurotronic CometBlue thermostats.
They are identical to the Sygonix, Xavax Bluetooth thermostats

This version is based on the bluepy library and works on hassio. 
Currently only current and target temperature in manual mode is supported, nothing else. 

Add your cometblue thermostats to configuration.yaml:

climate cometblue:
  platform: cometblue
  devices:
    thermostat1:
      mac: 11:22:33:44:55:66
      pin: 0

"""
import logging
from datetime import timedelta
from datetime import datetime
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_MAC,
    CONF_PIN,
    CONF_DEVICES,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
    ATTR_BATTERY_LEVEL,
    PRECISION_HALVES)

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(10)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)


DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_PIN, default=0): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.Schema({cv.string: DEVICE_SCHEMA}),
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        dev = CometBlueThermostat(device_cfg[CONF_MAC], name, device_cfg[CONF_PIN])
        devices.append(dev)

    add_devices(devices)



class CometBlueThermostat(ClimateDevice):
    """Representation of a CometBlue thermostat."""

    def __init__(self, _mac, _name, _pin=None):
        from cometblue_lite import CometBlue
        """Initialize the thermostat."""
        self._mac = _mac
        self._name = _name
        self._pin = _pin
        self._thermostat = CometBlue(_mac, _pin)
        self._lastupdate = datetime.now() - MIN_TIME_BETWEEN_UPDATES
#        self.update()

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._mac
    
    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self._thermostat.available

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return cometblue's precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Return current temperature"""
        return self._thermostat.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._thermostat.target_temperature


    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        _LOGGER.debug("Temperature to set: {}".format(temperature))
        self._thermostat.target_temperature = temperature

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 8.0

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 28.0

    @property
    def hvac_mode(self):
        if self._thermostat.manual_mode:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_AUTO

    def set_hvac_mode(self,hvac_mode):
        if hvac_mode==HVAC_MODE_HEAT:
            self._thermostat.manual_mode = True
        elif hvac_mode==HVAC_MODE_AUTO:
            self._thermostat.manual_mode = False

    @property
    def hvac_modes(self):
        if self._thermostat.firmware_rev == "GEN34BLE":
            # GENIUS BLE 100 does not support manual mode
            return (HVAC_MODE_AUTO,)
        else:
            return (HVAC_MODE_HEAT, HVAC_MODE_AUTO)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self._thermostat.battery_level,
            "model_type": self._thermostat.firmware_rev,
            "target_high": self._thermostat.target_temperature_high,
            "target_low": self._thermostat.target_temperature_low
        }

    def update(self):
        """Update the data from the thermostat."""
        now = datetime.now()
        if ( 
            self._thermostat.should_update() or
            (self._lastupdate and self._lastupdate + MIN_TIME_BETWEEN_UPDATES < now)
        ):
            _LOGGER.info("Updating status for {}".format(self._mac))
            self._thermostat.update()
            self._lastupdate = datetime.now()
        else: 
            _LOGGER.debug("Ignoring Update for {}".format(self._mac))

