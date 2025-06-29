#!/usr/bin/env python3
"""
Echo Diagnostic Tool for MKR5 Pump Communication

This script tests if the serial port has echo/loopback issues by:
1. Writing test data to the port
2. Reading back after a delay
3. Comparing what was sent vs what was received

If you receive exactly what you sent, it indicates either:
- Hardware echo/loopback (RS485 wiring, transceiver issues)
- The pump is not processing commands and just echoing them back
"""

import serial
import time
import sys
from typing import Optional

def test_serial_echo(port: str, baud_rate: int = 19200, timeout: float = 2.0):
    """
    Test for serial echo/loopback issues
    
    Args:
        port: Serial port name (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
        baud_rate: Baud rate for communication
        timeout: Read timeout in seconds
    """
    
    # Test patterns - different types of data to test with
    test_patterns = [
        # Simple test pattern
        b'\x01\x02\x03\x04\x05',
        
        # Pattern similar to MKR5 frame structure
        b'\x50\x81\x01\x01\x00\xBF\xBA\x03\xFA',
        
        # Random pattern
        b'\xAA\x55\xCC\x33\xFF\x00\x11\x22',
        
        # ASCII pattern
        b'HELLO_WORLD_TEST',
        
        # Longer pattern
        b'\x50\x81\x05\x18\x01\x55\x00\x01\x55\x00\x01\x55\x00\x01\x55\x00\x01\x55\x00\x01\x55\x00\x01\x55\x00\x01\x55\x00\x61\x70\x03\xFA'
    ]
    
    try:
        print(f"🔧 Opening serial port {port} at {baud_rate} baud...")
        
        # Configure serial port
        ser = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )
        
        print(f"✅ Serial port opened successfully")
        print(f"   Port: {ser.port}")
        print(f"   Baud rate: {ser.baudrate}")
        print(f"   Timeout: {ser.timeout}s")
        print()
        
        # Clear any existing data in buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
        echo_detected = False
        
        for i, test_data in enumerate(test_patterns, 1):
            print(f"🧪 Test {i}/{len(test_patterns)}: Testing pattern of {len(test_data)} bytes")
            print(f"   Sending: {test_data.hex().upper()}")
            
            # Clear buffers before test
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Send test data
            bytes_sent = ser.write(test_data)
            ser.flush()  # Ensure data is transmitted
            
            print(f"   Sent: {bytes_sent} bytes")
            
            # Wait a bit for any echo/response
            time.sleep(0.5)
            
            # Check how many bytes are available to read
            bytes_available = ser.in_waiting
            print(f"   Available to read: {bytes_available} bytes")
            
            if bytes_available > 0:
                # Read the data
                received_data = ser.read(bytes_available)
                print(f"   Received: {received_data.hex().upper()}")
                
                # Compare sent vs received
                if received_data == test_data:
                    print("   ⚠️  EXACT ECHO DETECTED - Received exactly what was sent!")
                    echo_detected = True
                elif received_data.startswith(test_data):
                    print("   ⚠️  PARTIAL ECHO DETECTED - Received data starts with sent data")
                    echo_detected = True
                elif test_data in received_data:
                    print("   ⚠️  ECHO DETECTED - Sent data found within received data")
                    echo_detected = True
                else:
                    print("   ✅ Different data received - This could be a valid response")
            else:
                print("   📭 No data received")
            
            print()
            time.sleep(0.5)  # Brief pause between tests
        
        # Summary
        print("=" * 60)
        if echo_detected:
            print("🚨 ECHO/LOOPBACK DETECTED!")
            print()
            print("Possible causes:")
            print("1. Hardware echo/loopback:")
            print("   - RS485 transceiver not properly configured")
            print("   - TX and RX lines connected together")
            print("   - Echo jumper or DIP switch enabled")
            print("   - Wiring issue (A+/B- lines crossed or shorted)")
            print()
            print("2. Pump behavior:")
            print("   - Pump is not processing commands properly")
            print("   - Pump is in a mode where it just echoes data")
            print("   - Communication protocol mismatch")
            print()
            print("Next steps:")
            print("- Check RS485 hardware configuration")
            print("- Verify pump is powered and operational")
            print("- Try different baud rates or communication settings")
            print("- Consult pump documentation for initialization sequence")
        else:
            print("✅ No consistent echo detected")
            print("The port appears to be working correctly for basic communication.")
            print("If you're still getting echoes with the pump, the issue may be")
            print("protocol-specific or related to the pump's current state.")
        
    except serial.SerialException as e:
        print(f"❌ Serial port error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        try:
            ser.close()
            print(f"🔒 Serial port {port} closed")
        except:
            pass
    
    return not echo_detected

def test_with_pump_patterns(port: str, baud_rate: int = 19200):
    """
    Test with actual MKR5 pump command patterns
    """
    print("\n🔍 Testing with actual MKR5 command patterns...")
    
    # Actual MKR5 commands from your logs
    mkr5_patterns = [
        # RETURN_STATUS command
        bytes.fromhex("5081010100bfba03fa"),
        
        # PRICE_UPDATE command (from your logs)
        bytes.fromhex("50810518015500015500015500015500015500015500015500015500617003fa"),
        
        # Simple status query
        bytes.fromhex("50810100009f9a03fa")
    ]
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=2.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )
        
        for i, cmd_data in enumerate(mkr5_patterns, 1):
            print(f"\n📡 MKR5 Test {i}: Sending actual pump command")
            print(f"   Command: {cmd_data.hex().upper()}")
            
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Send command
            ser.write(cmd_data)
            ser.flush()
            
            # Wait for response
            time.sleep(1.0)
            
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"   Response: {response.hex().upper()}")
                
                if response == cmd_data:
                    print("   ⚠️  EXACT ECHO - Pump echoed the command back!")
                else:
                    print("   ✅ Different response received")
            else:
                print("   📭 No response received")
        
    except Exception as e:
        print(f"❌ Error in MKR5 pattern test: {e}")
    finally:
        try:
            ser.close()
        except:
            pass

if __name__ == "__main__":
    # Default settings - you can modify these
    DEFAULT_PORT = "COM3"  # Change this to your actual port
    DEFAULT_BAUD = 19200   # Based on your .env file
    
    print("🔧 MKR5 Pump Echo Diagnostic Tool")
    print("=" * 50)
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        port = sys.argv[1]
        baud_rate = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD
    else:
        port = DEFAULT_PORT
        baud_rate = DEFAULT_BAUD
    
    print(f"Testing port: {port}")
    print(f"Baud rate: {baud_rate}")
    print()
    
    # Run the basic echo test
    success = test_serial_echo(port, baud_rate)
    
    # Run MKR5-specific tests
    test_with_pump_patterns(port, baud_rate)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Diagnostic complete - No consistent hardware echo detected")
    else:
        print("⚠️  Diagnostic complete - Echo/loopback issues detected")
