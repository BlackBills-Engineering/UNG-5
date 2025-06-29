#!/usr/bin/env python3
"""
Simplified POS System Diagnostic Tool

This is a more robust version that focuses on the most likely differences
between the original POS system and our implementation, with better
error handling to prevent hanging.
"""

import serial
import time
import logging
import threading
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimeoutSerialTest:
    """Serial test with timeout protection"""
    
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds
        self.result = None
        self.error = None
    
    def run_test_with_timeout(self, test_func, *args, **kwargs):
        """Run a test function with timeout protection"""
        def target():
            try:
                self.result = test_func(*args, **kwargs)
            except Exception as e:
                self.error = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout_seconds)
        
        if thread.is_alive():
            logger.error(f"   ❌ Test timed out after {self.timeout_seconds}s")
            return None, "TIMEOUT"
        elif self.error:
            return None, str(self.error)
        else:
            return self.result, None

class SimplePOSDiagnostic:
    def __init__(self, port: str = "COM3"):
        self.port = port
        
    def test_basic_serial_configs(self):
        """Test the most common serial configurations"""
        logger.info("🔧 Testing basic serial configurations...")
        
        # Focus on most likely configurations for industrial protocols
        configs = [
            {"baud": 9600, "parity": serial.PARITY_NONE, "name": "9600-N-8-1"},
            {"baud": 19200, "parity": serial.PARITY_NONE, "name": "19200-N-8-1"},
            {"baud": 9600, "parity": serial.PARITY_EVEN, "name": "9600-E-8-1"},
            {"baud": 19200, "parity": serial.PARITY_EVEN, "name": "19200-E-8-1"},
            {"baud": 9600, "parity": serial.PARITY_ODD, "name": "9600-O-8-1"},
            {"baud": 19200, "parity": serial.PARITY_ODD, "name": "19200-O-8-1"},
        ]
        
        for i, config in enumerate(configs, 1):
            logger.info(f"\n📡 Config Test {i}/6: {config['name']}")
            
            tester = TimeoutSerialTest(timeout_seconds=3)
            result, error = tester.run_test_with_timeout(self._test_serial_config, config)
            
            if error == "TIMEOUT":
                logger.warning(f"   ⏰ Test timed out - possible flow control issue")
            elif error:
                logger.error(f"   ❌ Error: {error}")
            elif result:
                logger.info(f"   {result}")
    
    def _test_serial_config(self, config):
        """Test a single serial configuration"""
        try:
            with serial.Serial(
                port=self.port,
                baudrate=config["baud"],
                parity=config["parity"],
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0.5,  # Short timeout to prevent hanging
                rtscts=False,
                dsrdtr=False
            ) as ser:
                
                time.sleep(0.1)  # Let port settle
                
                # Send test command
                test_data = b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
                logger.info(f"   📤 Sending: {test_data.hex().upper()}")
                ser.write(test_data)
                ser.flush()
                
                # Read response with short timeout
                time.sleep(0.2)
                response = ser.read(100)
                
                if response:
                    logger.info(f"   📥 Received: {response.hex().upper()}")
                    if response == test_data:
                        return "⚠️  ECHO detected"
                    else:
                        return "✅ Different response - possible communication!"
                else:
                    return "📭 No response"
                    
        except Exception as e:
            raise e
    
    def test_simple_rts_variations(self):
        """Test only safe RTS variations without flow control"""
        logger.info("\n🔧 Testing simple RTS variations...")
        
        # Only test safe RTS configurations that won't cause hanging
        rts_configs = [
            {"rts": None, "name": "Default RTS"},
            {"rts": True, "name": "RTS High"},
            {"rts": False, "name": "RTS Low"},
        ]
        
        for i, config in enumerate(rts_configs, 1):
            logger.info(f"\n📡 RTS Test {i}/3: {config['name']}")
            
            tester = TimeoutSerialTest(timeout_seconds=3)
            result, error = tester.run_test_with_timeout(self._test_rts_config, config)
            
            if error == "TIMEOUT":
                logger.warning(f"   ⏰ Test timed out")
            elif error:
                logger.error(f"   ❌ Error: {error}")
            elif result:
                logger.info(f"   {result}")
    
    def _test_rts_config(self, config):
        """Test a single RTS configuration"""
        try:
            ser = serial.Serial(
                port=self.port,
                baudrate=19200,
                timeout=0.5,
                rtscts=False,  # No flow control
                dsrdtr=False   # No flow control
            )
            
            # Set RTS if specified
            if config["rts"] is not None:
                ser.rts = config["rts"]
            
            time.sleep(0.1)
            
            # Send test command
            test_data = b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
            logger.info(f"   📤 Sending: {test_data.hex().upper()}")
            ser.write(test_data)
            ser.flush()
            
            time.sleep(0.2)
            response = ser.read(100)
            
            ser.close()
            
            if response:
                logger.info(f"   📥 Received: {response.hex().upper()}")
                if response == test_data:
                    return "⚠️  ECHO detected"
                else:
                    return "✅ Different response!"
            else:
                return "📭 No response"
                
        except Exception as e:
            raise e
    
    def test_frame_variations(self):
        """Test different frame formats"""
        logger.info("\n🔧 Testing frame variations...")
        
        test_frames = [
            {
                "name": "Standard MKR5 Status",
                "frame": b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA'
            },
            {
                "name": "Different pump address",
                "frame": b'\x01\x81\x01\x01\x00\x1F\x3B\x03\xFA'
            },
            {
                "name": "Broadcast address",
                "frame": b'\xFF\x81\x01\x01\x00\xFF\x7B\x03\xFA'
            },
        ]
        
        for i, test in enumerate(test_frames, 1):
            logger.info(f"\n📡 Frame Test {i}/3: {test['name']}")
            
            tester = TimeoutSerialTest(timeout_seconds=3)
            result, error = tester.run_test_with_timeout(self._test_frame, test['frame'])
            
            if error == "TIMEOUT":
                logger.warning(f"   ⏰ Test timed out")
            elif error:
                logger.error(f"   ❌ Error: {error}")
            elif result:
                logger.info(f"   {result}")
    
    def _test_frame(self, frame_data):
        """Test a single frame"""
        try:
            with serial.Serial(
                port=self.port,
                baudrate=19200,
                timeout=0.5,
                rtscts=False,
                dsrdtr=False
            ) as ser:
                
                logger.info(f"   📤 Sending: {frame_data.hex().upper()}")
                ser.write(frame_data)
                ser.flush()
                
                time.sleep(0.2)
                response = ser.read(100)
                
                if response:
                    logger.info(f"   📥 Received: {response.hex().upper()}")
                    if response == frame_data:
                        return "⚠️  ECHO detected"
                    else:
                        return "✅ Different response!"
                else:
                    return "📭 No response"
                    
        except Exception as e:
            raise e
    
    def run_diagnostic(self):
        """Run the simplified diagnostic"""
        logger.info("🚀 Starting Simplified POS System Diagnostic")
        logger.info("=" * 60)
        logger.info("Testing key differences between POS system and our code")
        logger.info("This version has timeouts to prevent hanging")
        logger.info("=" * 60)
        
        # Run tests in order of likelihood
        self.test_basic_serial_configs()
        self.test_simple_rts_variations() 
        self.test_frame_variations()
        
        logger.info("\n" + "=" * 60)
        logger.info("🏁 DIAGNOSTIC COMPLETE")
        logger.info("=" * 60)
        logger.info("Key things to look for:")
        logger.info("- Any test showing 'Different response!' instead of echo")
        logger.info("- Any test showing 'No response' (might indicate wrong config)")
        logger.info("- Tests that timed out (indicates problematic settings)")

def main():
    diagnostic = SimplePOSDiagnostic("COM3")
    diagnostic.run_diagnostic()

if __name__ == "__main__":
    main()
