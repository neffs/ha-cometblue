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
import threading
import voluptuous as vol

import time
import struct


from sys import stderr

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
#    HVAC_MODE_AUTO,
#    HVAC_MODE_OFF,
#    PRESET_AWAY,
#    PRESET_HOME,
#    PRESET_NONE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_MAC,
    CONF_PIN,
    CONF_DEVICES,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
    PRECISION_HALVES)

import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['bluepy>=1.3.0']

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

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE )
#SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        dev = CometBlueThermostat(device_cfg[CONF_MAC], name, device_cfg[CONF_PIN])
        devices.append(dev)

    add_devices(devices)


PASSWORD_HANDLE = 0x47
TEMPERATURE_HANDLE = 0x3f
_TEMPERATURES_STRUCT_PACKING = '<bbbbbbb'
_PIN_STRUCT_PACKING = '<I'


class CometBlueThermostat(ClimateDevice):
    """Representation of a CometBlue thermostat."""

    def __init__(self, _mac, _name, _pin=None):
        """Initialize the thermostat."""
        self._mac = _mac
        self._name = _name
        self._pin = _pin
        self._thermostat = CometBlue(_mac, _pin)
        self._lastupdate = datetime.now() - MIN_TIME_BETWEEN_UPDATES
        #self._hvac_mode = HVAC_MODE_HEAT

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
        return self._thermostat.manual_temperature


    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        _LOGGER.debug("Temperature to set: {}".format(temperature))
        self._thermostat.manual_temperature = temperature

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
        #return self._hvac_mode
        return HVAC_MODE_HEAT

    def set_hvac_mode(self,hvac_mode):
        #self._hvac_mode = hvac_mode 
        pass

    @property
    def hvac_modes(self):
        return (HVAC_MODE_HEAT,)
        #return (HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO)

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.info("Update called {}".format(self._mac))
        now = datetime.now()
        if ( 
            self._thermostat.should_update() or
            (self._lastupdate and self._lastupdate + MIN_TIME_BETWEEN_UPDATES < now)
        ):
            self._thermostat.update()
            self._lastupdate = datetime.now()
        else: 
            _LOGGER.debug("Ignoring Update for {}".format(self._mac))


class CometBlue(object):
    """CometBlue Thermostat """
    def __init__(self, address, pin):
        from bluepy import btle
        super(CometBlue, self).__init__()
        self._address = address
        self._conn = btle.Peripheral()
        self._pin = pin
        self._manual_temp = None
        self._cur_temp = None
        self._temperature = None
        self.available = False
#        self.update()

    def connect(self):
        from bluepy import btle
        try:
            self._conn.connect(self._address)
        except btle.BTLEException as ex:
            _LOGGER.debug("Unable to connect to the device %s, retrying: %s", self._address, ex)
            try:
                self._conn.connect(self._address)
            except Exception as ex2:
                _LOGGER.debug("Second connection try to %s failed: %s", self._address, ex2)
                raise
                
        self._conn.writeCharacteristic(PASSWORD_HANDLE, struct.pack(_PIN_STRUCT_PACKING, self._pin), withResponse=True)

    def disconnect(self):
        from bluepy import btle
        
        self._conn.disconnect()
        self._conn = btle.Peripheral()

    def should_update(self):
        return self._temperature != None #or self._cur_temp == None

    @property
    def manual_temperature(self):
        if self._manual_temp:
            return self._manual_temp / 2.0
        else:
            return None
 
    @property
    def current_temperature(self):
        if self._cur_temp:
            return self._cur_temp / 2.0
        else:
            return None 


    def update(self):
        from bluepy import btle
        _LOGGER.debug("Connecting to device %s", self._address)
        self.connect()
        try:
            data = self._conn.readCharacteristic(TEMPERATURE_HANDLE)
            self._cur_temp, self._manual_temp, self._target_low, self._target_high, self._offset_temp, \
                    self._window_open_detect, self._window_open_minutes = struct.unpack(
                            _TEMPERATURES_STRUCT_PACKING, data)
            if self._temperature:
                _LOGGER.debug("Updating Temperature for device %s to %d", self._address, self._temperature)
                self.write_temperature()
            self.available = True
            
        except btle.BTLEGattError:
            _LOGGER.error("Can't read cometblue data (%s). Did you set the correct PIN?", self._address)
            self.available = False
        finally:
            self.disconnect()
            _LOGGER.debug("Disconnected from device %s", self._address)

 
    @manual_temperature.setter
    def manual_temperature(self, temperature):
        self._temperature = temperature

    def write_temperature(self):
        self._manual_temp = int(self._temperature * 2.0)
        data = struct.pack(
                    _TEMPERATURES_STRUCT_PACKING,
                    -128, self._manual_temp,
                    -128, -128, -128, -128, -128)
        self._conn.writeCharacteristic(TEMPERATURE_HANDLE,data)
        
        self._temperature = None
