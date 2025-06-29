#!/usr/bin/env python3
"""
Serial Port Echo Test

This script tests if the serial port/pump is echoing back the data we send.
It sends test data and checks if the same data is received back.

If we get back exactly what we sent, it could mean:
1. The serial line is configured for loopback/echo
2. The pump hardware is echoing data without processing it
3. There's a wiring issue causing the TX and RX lines to be connected

Usage:
    python test_serial_echo.py
"""

import serial
import time
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_serial_echo():
    """Test if the serial port echoes back sent data."""
    
    # Get configuration from environment
    com_port = os.getenv('COM_PORT', 'COM3')
    baud_rate = int(os.getenv('BAUD_RATE', '9600'))
    
    logger.info(f"Testing serial echo on {com_port} at {baud_rate} baud")
    
    try:
        # Open serial connection
        with serial.Serial(
            port=com_port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0,
            write_timeout=2.0
        ) as ser:
            
            logger.info(f"✅ Connected to {com_port}")
            
            # Clear any existing data in buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)
            
            # Test 1: Simple ASCII test
            logger.info("\n" + "="*50)
            logger.info("TEST 1: Simple ASCII String")
            logger.info("="*50)
            
            test_data_1 = b"HELLO_TEST_123"
            logger.info(f"📤 Sending: {test_data_1.decode('ascii')} ({len(test_data_1)} bytes)")
            logger.info(f"📤 Hex: {test_data_1.hex().upper()}")
            
            ser.write(test_data_1)
            time.sleep(0.5)  # Wait for response
            
            received_1 = ser.read(ser.in_waiting or len(test_data_1))
            logger.info(f"📥 Received: {len(received_1)} bytes")
            
            if received_1:
                try:
                    logger.info(f"📥 ASCII: {received_1.decode('ascii', errors='ignore')}")
                except:
                    logger.info("📥 ASCII: <not decodable>")
                logger.info(f"📥 Hex: {received_1.hex().upper()}")
                
                if received_1 == test_data_1:
                    logger.warning("⚠️  EXACT ECHO DETECTED - Received exactly what was sent!")
                else:
                    logger.info("✅ No exact echo - received different data")
            else:
                logger.info("📥 No data received")
            
            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)
            
            # Test 2: Binary test data
            logger.info("\n" + "="*50)
            logger.info("TEST 2: Binary Test Data")
            logger.info("="*50)
            
            test_data_2 = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE])
            logger.info(f"📤 Sending: {len(test_data_2)} bytes")
            logger.info(f"📤 Hex: {test_data_2.hex().upper()}")
            
            ser.write(test_data_2)
            time.sleep(0.5)  # Wait for response
            
            received_2 = ser.read(ser.in_waiting or len(test_data_2))
            logger.info(f"📥 Received: {len(received_2)} bytes")
            
            if received_2:
                logger.info(f"📥 Hex: {received_2.hex().upper()}")
                
                if received_2 == test_data_2:
                    logger.warning("⚠️  EXACT ECHO DETECTED - Received exactly what was sent!")
                else:
                    logger.info("✅ No exact echo - received different data")
            else:
                logger.info("📥 No data received")
            
            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)
            
            # Test 3: Test with different delays
            logger.info("\n" + "="*50)
            logger.info("TEST 3: Testing Different Delays")
            logger.info("="*50)
            
            for delay in [0.1, 0.2, 0.5, 1.0]:
                test_data_3 = f"DELAY_{delay:.1f}".encode('ascii')
                logger.info(f"📤 Sending with {delay}s delay: {test_data_3.decode('ascii')}")
                
                ser.write(test_data_3)
                time.sleep(delay)
                
                received_3 = ser.read(ser.in_waiting or len(test_data_3))
                if received_3:
                    logger.info(f"📥 Received: {received_3.decode('ascii', errors='ignore')}")
                    if received_3 == test_data_3:
                        logger.warning(f"⚠️  ECHO at {delay}s delay")
                    else:
                        logger.info(f"✅ Different data at {delay}s delay")
                else:
                    logger.info(f"📥 No data at {delay}s delay")
                
                # Clear for next test
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                time.sleep(0.1)
            
            # Test 4: MKR5-like frame test
            logger.info("\n" + "="*50)
            logger.info("TEST 4: MKR5-like Frame Test")
            logger.info("="*50)
            
            # Simple MKR5-like frame (not a real command, just for testing)
            test_frame = bytes([0x50, 0x81, 0x99, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x12, 0x34, 0x03, 0xFA])
            logger.info(f"📤 Sending MKR5-like frame: {len(test_frame)} bytes")
            logger.info(f"📤 Hex: {test_frame.hex().upper()}")
            
            ser.write(test_frame)
            time.sleep(0.5)
            
            received_4 = ser.read(ser.in_waiting or len(test_frame))
            if received_4:
                logger.info(f"📥 Received: {len(received_4)} bytes")
                logger.info(f"📥 Hex: {received_4.hex().upper()}")
                
                if received_4 == test_frame:
                    logger.warning("⚠️  EXACT ECHO of MKR5-like frame!")
                else:
                    logger.info("✅ Received different MKR5-like frame")
            else:
                logger.info("📥 No MKR5-like frame received")
            
            # Final summary
            logger.info("\n" + "="*60)
            logger.info("ECHO TEST SUMMARY")
            logger.info("="*60)
            logger.info("If you see 'EXACT ECHO DETECTED' messages above, it means:")
            logger.info("1. The serial connection is echoing data back")
            logger.info("2. This could be due to:")
            logger.info("   - Hardware loopback (TX connected to RX)")
            logger.info("   - Pump echoing without processing")
            logger.info("   - Serial driver/adapter issue")
            logger.info("   - Incorrect wiring")
            logger.info("")
            logger.info("If no echoes were detected, the pump may be:")
            logger.info("   - Not responding at all")
            logger.info("   - Responding with different data")
            logger.info("   - Processing commands correctly")
            
    except serial.SerialException as e:
        logger.error(f"❌ Serial connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False
    
    return True

def main():
    """Main function."""
    logger.info("Serial Port Echo Test")
    logger.info("This test will help determine if the pump is echoing data")
    logger.info("or if there's a hardware/wiring issue causing echoes.")
    logger.info("")
    
    success = test_serial_echo()
    
    if success:
        logger.info("✅ Echo test completed successfully")
    else:
        logger.error("❌ Echo test failed")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
