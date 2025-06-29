#!/usr/bin/env python3
"""
POS System vs Our Code Diagnostic Tool

This tool helps identify differences between the original POS system
and our implementation that might cause the echo behavior.
"""

import serial
import time
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class POSDiagnostic:
    def __init__(self, port: str = "COM3"):
        self.port = port
        self.serial_conn: Optional[serial.Serial] = None
        
    def test_serial_settings(self):
        """Test different serial port configurations"""
        logger.info("🔧 Testing different serial port configurations...")
        
        # Common RS485/MKR5 configurations based on industrial protocols
        # Testing various parity settings as MKR5 spec mentions "parity check is made in the line protocol"
        test_configs = [
            {"baud": 9600, "parity": serial.PARITY_NONE, "stopbits": 1, "bytesize": 8, "name": "9600-N-8-1"},
            {"baud": 19200, "parity": serial.PARITY_NONE, "stopbits": 1, "bytesize": 8, "name": "19200-N-8-1"},
            {"baud": 9600, "parity": serial.PARITY_EVEN, "stopbits": 1, "bytesize": 8, "name": "9600-E-8-1"},
            {"baud": 19200, "parity": serial.PARITY_EVEN, "stopbits": 1, "bytesize": 8, "name": "19200-E-8-1"},
            {"baud": 9600, "parity": serial.PARITY_ODD, "stopbits": 1, "bytesize": 8, "name": "9600-O-8-1"},
            {"baud": 19200, "parity": serial.PARITY_ODD, "stopbits": 1, "bytesize": 8, "name": "19200-O-8-1"},
            {"baud": 9600, "parity": serial.PARITY_NONE, "stopbits": 2, "bytesize": 8, "name": "9600-N-8-2"},
            {"baud": 19200, "parity": serial.PARITY_NONE, "stopbits": 2, "bytesize": 8, "name": "19200-N-8-2"},
        ]
        
        for i, config in enumerate(test_configs, 1):
            logger.info(f"\n📡 Test {i}/8: {config['name']} - {config}")
            try:
                # Test this configuration
                with serial.Serial(
                    port=self.port,
                    baudrate=config["baud"],
                    parity=config["parity"],
                    stopbits=config["stopbits"],
                    bytesize=config["bytesize"],
                    timeout=1.0,
                    rtscts=False,
                    dsrdtr=False
                ) as ser:
                    time.sleep(0.1)  # Let port settle
                    
                    # Send a simple test pattern
                    test_data = b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
                    logger.info(f"   📤 Sending: {test_data.hex().upper()}")
                    ser.write(test_data)
                    ser.flush()
                    
                    # Wait and read response
                    time.sleep(0.2)
                    response = ser.read(100)
                    
                    if response:
                        logger.info(f"   📥 Received: {response.hex().upper()}")
                        if response == test_data:
                            logger.warning("   ⚠️  ECHO detected with this config")
                        else:
                            logger.info("   ✅ Different response - possible pump communication!")
                    else:
                        logger.info("   📭 No response")
                        
            except Exception as e:
                logger.error(f"   ❌ Error with config: {e}")
    
    def test_rts_dtr_control(self):
        """Test RTS/DTR line control for RS485 direction"""
        logger.info("\n🔧 Testing RTS/DTR control for RS485 direction...")
        
        # Test different RTS/DTR configurations
        rts_dtr_configs = [
            {"rtscts": False, "dsrdtr": False, "rts": None, "dtr": None},
            {"rtscts": True, "dsrdtr": False, "rts": None, "dtr": None},
            {"rtscts": False, "dsrdtr": True, "rts": None, "dtr": None},
            {"rtscts": False, "dsrdtr": False, "rts": True, "dtr": None},
            {"rtscts": False, "dsrdtr": False, "rts": False, "dtr": None},
            {"rtscts": False, "dsrdtr": False, "rts": None, "dtr": True},
            {"rtscts": False, "dsrdtr": False, "rts": None, "dtr": False},
        ]
        
        for i, config in enumerate(rts_dtr_configs, 1):
            logger.info(f"\n📡 RTS/DTR Test {i}/7: {config}")
            try:
                ser = serial.Serial(
                    port=self.port,
                    baudrate=19200,
                    timeout=1.0,
                    rtscts=config["rtscts"],
                    dsrdtr=config["dsrdtr"]
                )
                
                # Set RTS/DTR if specified
                if config["rts"] is not None:
                    ser.rts = config["rts"]
                if config["dtr"] is not None:
                    ser.dtr = config["dtr"]
                
                time.sleep(0.1)
                
                # Send test command
                test_data = b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
                logger.info(f"   📤 Sending: {test_data.hex().upper()}")
                ser.write(test_data)
                ser.flush()
                
                time.sleep(0.2)
                response = ser.read(100)
                
                if response:
                    logger.info(f"   📥 Received: {response.hex().upper()}")
                    if response == test_data:
                        logger.warning("   ⚠️  ECHO detected")
                    else:
                        logger.info("   ✅ Different response!")
                else:
                    logger.info("   📭 No response")
                
                ser.close()
                
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
    
    def test_timing_variations(self):
        """Test different timing patterns"""
        logger.info("\n🔧 Testing timing variations...")
        
        timing_tests = [
            {"pre_delay": 0.0, "post_delay": 0.1, "name": "No pre-delay"},
            {"pre_delay": 0.05, "post_delay": 0.1, "name": "50ms pre-delay"},
            {"pre_delay": 0.1, "post_delay": 0.1, "name": "100ms pre-delay"},
            {"pre_delay": 0.2, "post_delay": 0.2, "name": "200ms delays"},
            {"pre_delay": 0.5, "post_delay": 0.5, "name": "500ms delays"},
        ]
        
        for i, timing in enumerate(timing_tests, 1):
            logger.info(f"\n⏱️  Timing Test {i}/5: {timing['name']}")
            try:
                with serial.Serial(
                    port=self.port,
                    baudrate=19200,
                    timeout=2.0,
                    rtscts=False,
                    dsrdtr=False
                ) as ser:
                    
                    # Pre-transmission delay
                    if timing["pre_delay"] > 0:
                        time.sleep(timing["pre_delay"])
                    
                    # Send command
                    test_data = b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
                    logger.info(f"   📤 Sending after {timing['pre_delay']}s delay")
                    ser.write(test_data)
                    ser.flush()
                    
                    # Post-transmission delay
                    time.sleep(timing["post_delay"])
                    
                    # Read response
                    response = ser.read(100)
                    
                    if response:
                        logger.info(f"   📥 Received: {response.hex().upper()}")
                        if response == test_data:
                            logger.warning("   ⚠️  ECHO detected")
                        else:
                            logger.info("   ✅ Different response!")
                    else:
                        logger.info("   📭 No response")
                        
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
    
    def test_frame_variations(self):
        """Test different frame formats that POS might use"""
        logger.info("\n🔧 Testing frame format variations...")
        
        # Different possible frame formats
        test_frames = [
            {
                "name": "Standard MKR5 Status Request",
                "frame": b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
            },
            {
                "name": "Alternative control byte (0x80)",
                "frame": b'\x50\x80\x01\x01\x00\x7F\x3A\x03\xFA'
            },
            {
                "name": "Different pump address (0x51)",
                "frame": b'\x51\x81\x01\x01\x00\xEF\x8B\x03\xFA'
            },
            {
                "name": "No ETX/SF bytes",
                "frame": b'\x50\x81\x01\x01\x00\xBF\xBA'
            },
            {
                "name": "Different termination",
                "frame": b'\x50\x81\x01\x01\x00\xBF\xBA\x0D\x0A'
            }
        ]
        
        for i, test in enumerate(test_frames, 1):
            logger.info(f"\n📡 Frame Test {i}/5: {test['name']}")
            try:
                with serial.Serial(
                    port=self.port,
                    baudrate=19200,
                    timeout=1.0
                ) as ser:
                    
                    logger.info(f"   📤 Sending: {test['frame'].hex().upper()}")
                    ser.write(test['frame'])
                    ser.flush()
                    
                    time.sleep(0.2)
                    response = ser.read(100)
                    
                    if response:
                        logger.info(f"   📥 Received: {response.hex().upper()}")
                        if response == test['frame']:
                            logger.warning("   ⚠️  ECHO detected")
                        else:
                            logger.info("   ✅ Different response!")
                    else:
                        logger.info("   📭 No response")
                        
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
    
    def run_full_diagnostic(self):
        """Run all diagnostic tests"""
        logger.info("🚀 Starting POS System Comparison Diagnostic")
        logger.info("=" * 60)
        logger.info("This will test various configurations to find what")
        logger.info("makes the original POS system work vs our code.")
        logger.info("=" * 60)
        
        # Run all tests
        self.test_serial_settings()
        self.test_rts_dtr_control()
        self.test_timing_variations()
        self.test_frame_variations()
        
        logger.info("\n" + "=" * 60)
        logger.info("🏁 DIAGNOSTIC COMPLETE")
        logger.info("=" * 60)
        logger.info("Look for any test that shows 'Different response!' or")
        logger.info("'No response' instead of 'ECHO detected'.")
        logger.info("Those configurations might match the POS system.")

def main():
    diagnostic = POSDiagnostic("COM3")
    diagnostic.run_full_diagnostic()

if __name__ == "__main__":
    main()
