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

from bluepy import btle



from sys import stderr

REQUIREMENTS = ['bluepy>=1.3.0']

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(10)



PASSWORD_HANDLE = 0x47
TEMPERATURE_HANDLE = 0x3f
STATUS_HANDLE = 0x3d
_TEMPERATURES_STRUCT_PACKING = '<bbbbbbb'
_PIN_STRUCT_PACKING = '<I'
_STATUS_STRUCT_PACKING = '<BBB'
_DATETIME_STRUCT_PACKING = '<BBBBB'
_BATTERY_STRUCT_PACKING = '<B'
_DAY_STRUCT_PACKING = '<BBBBBBBB'

_STATUS_BITMASKS = {
    'childlock': 0x80,
    'manual_mode': 0x1,
    'adapting': 0x400,
    'not_ready': 0x200,
    'installing': 0x400 | 0x200 | 0x100,
    'motor_moving': 0x100,
    'antifrost_activated': 0x10,
    'satisfied': 0x80000,
    'low_battery': 0x800
}




class CometBlue(object):
    """CometBlue Thermostat """
    def __init__(self, address, pin):
        super(CometBlue, self).__init__()
        self._address = address
        self._conn = btle.Peripheral()
        self._pin = pin
        self._manual_temp = None
        self._cur_temp = None
        self._temperature = None
        self.available = False
        self._new_status = dict()
        self._status = dict()
#        self.update()

    def connect(self):
        try:
            self._conn.connect(self._address)
        except btle.BTLEException as ex:
            _LOGGER.debug("Unable to connect to the device %s, retrying: %s", self._address, ex)
            try:
                self._conn.connect(self._address)
            except Exception as ex2:
                _LOGGER.debug("Second connection try to %s failed: %s", self._address, ex2)
                raise
                
        self._conn.writeCharacteristic(PASSWORD_HANDLE, struct.pack(_PIN_STRUCT_PACKING, self._pin))

    def disconnect(self):
        
        self._conn.disconnect()
        self._conn = btle.Peripheral()

    def should_update(self):
        return self._temperature != None or len(self._new_status)>0

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
    
    @property
    def manual_mode(self):
        if self._status:
            return self._status['manual_mode']
        else:
            return None 
    


    def update(self):
        _LOGGER.debug("Connecting to device %s", self._address)
        self.connect()
        try:
            data = self._conn.readCharacteristic(TEMPERATURE_HANDLE)
            self._cur_temp, self._manual_temp, self._target_low, self._target_high, self._offset_temp, \
                    self._window_open_detect, self._window_open_minutes = struct.unpack(
                            _TEMPERATURES_STRUCT_PACKING, data)
            data = self._conn.readCharacteristic(STATUS_HANDLE)
            self._status = CometBlue._decode_status(data)
            
            if self._temperature:
                _LOGGER.debug("Updating Temperature for device %s to %d", self._address, self._temperature)
                self.write_temperature()
            if len(self._new_status)>0:
                _LOGGER.debug("Updating Status for device %s", self._address)
                self.write_status()            
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
    
    @manual_mode.setter
    def manual_mode(self, mode):
        self._new_status['manual_mode'] = mode

    def write_temperature(self):
        self._manual_temp = int(self._temperature * 2.0)
        data = struct.pack(
                    _TEMPERATURES_STRUCT_PACKING,
                    -128, self._manual_temp,
                    -128, -128, -128, -128, -128)
        self._conn.writeCharacteristic(TEMPERATURE_HANDLE,data)
        
        self._temperature = None
    
    def write_status(self):
        status = self._status.copy()
        status.update(self._new_status)
        _LOGGER.debug("new status %s", status)
        
        data = CometBlue._encode_status(status)
        self._conn.writeCharacteristic(STATUS_HANDLE,data)
        self._status = status
        
        self._new_status = dict()

    def _decode_status(value):
        state_bytes = struct.unpack(_STATUS_STRUCT_PACKING, value)
        state_dword = struct.unpack('<I', value + b'\x00')[0]

        report = {}
        masked_out = 0
        for key, mask in _STATUS_BITMASKS.items():
            report[key] = bool(state_dword & mask == mask)
            masked_out |= mask

        report['state_as_dword'] = state_dword
        report['unused_bits'] = state_dword & ~masked_out

        return report
        
    


    def _encode_status(value):
        status_dword = 0
        for key, state in value.items():
            if not state:
                continue

            if not key in _STATUS_BITMASKS:
               # _log.error('Unknown flag ' + key)
                continue

            status_dword |= _STATUS_BITMASKS[key]

        value = struct.pack('<I', status_dword)
        # downcast to 3 bytes
        return struct.pack(_STATUS_STRUCT_PACKING, *[int(byte) for byte in value[:3]])
