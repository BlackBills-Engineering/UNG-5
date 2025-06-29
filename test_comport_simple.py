#!/usr/bin/env python3
"""
COM Port Testing Utility for MKR5 Pump Control API
Simple version that doesn't require complex imports
"""

import serial
import serial.tools.list_ports
import time
import sys
import struct
from typing import List, Dict, Any


class SimpleCOMPortTester:
    """Simple COM Port testing utility"""
    
    def __init__(self):
        # MKR5 Protocol constants
        self.MIN_PUMP_ADDRESS = 0x50
        self.MAX_PUMP_ADDRESS = 0x6F
        self.ETX = 0x03  # End of text
        self.SF = 0xFA   # Stop flag
        
        # Command constants
        self.RETURN_STATUS = 0x00
        self.RETURN_PUMP_IDENTITY = 0x03
    
    def list_available_ports(self) -> List[str]:
        """List all available COM ports on the system"""
        print("🔍 Scanning for available COM ports...")
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("❌ No COM ports found on this system")
            return []
        
        available_ports = []
        print("✅ Available COM ports:")
        for i, port in enumerate(ports, 1):
            print(f"   {i}. {port.device}")
            print(f"      Description: {port.description}")
            if hasattr(port, 'manufacturer') and port.manufacturer:
                print(f"      Manufacturer: {port.manufacturer}")
            print(f"      Hardware ID: {port.hwid}")
            print()
            available_ports.append(port.device)
        
        return available_ports
    
    def calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC-16 CCITT checksum"""
        crc = 0x0000
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc
    
    def create_command_message(self, address: int, command: int) -> bytes:
        """Create a command message according to MKR5 protocol"""
        # Control byte (master, TX#=1)
        ctrl = 0x81  # 10000001 - Master bit set, TX#=1
        
        # Transaction CD1 (Command to pump)
        trans = 0x01
        lng = 0x01  # Length of data
        dcc = command  # Command code
        
        # Build message without CRC
        message_data = bytes([address, ctrl, trans, lng, dcc])
        
        # Calculate CRC
        crc = self.calculate_crc16(message_data)
        crc_l = crc & 0xFF
        crc_h = (crc >> 8) & 0xFF
        
        # Complete message
        message = message_data + bytes([crc_l, crc_h, self.ETX, self.SF])
        
        return message
    
    def test_port_basic(self, port: str, baud_rate: int = 9600) -> bool:
        """Test basic port connectivity"""
        print(f"🔍 Testing basic connectivity to {port} at {baud_rate} baud...")
        
        try:
            # Try to open the port
            with serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=8,
                stopbits=1,
                parity=serial.PARITY_ODD,
                timeout=1.0,
                write_timeout=1.0
            ) as ser:
                print(f"✅ Successfully opened {port}")
                print(f"   Settings: {baud_rate} baud, 8 data bits, 1 stop bit, odd parity")
                print(f"   Port details: {ser}")
                
                # Clear any existing data
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                
                # Test if we can write to the port
                test_message = self.create_command_message(0x50, self.RETURN_STATUS)
                print(f"   Sending test message: {test_message.hex()}")
                
                bytes_written = ser.write(test_message)
                print(f"✅ Successfully wrote {bytes_written} bytes to port")
                
                # Try to read any response (with timeout)
                time.sleep(0.2)  # Wait a bit longer for response
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"📥 Received {len(response)} bytes: {response.hex()}")
                    return True
                else:
                    print("📭 No immediate response (this could be normal)")
                    print("   • Pumps might not be connected")
                    print("   • Wrong baud rate")
                    print("   • Incorrect wiring")
                    return True  # Port itself works, just no response
                
        except serial.SerialException as e:
            print(f"❌ Failed to open {port}: {e}")
            if "Access is denied" in str(e) or "Permission denied" in str(e):
                print("   💡 Tip: Make sure no other program is using this port")
                print("   💡 Tip: Try running as administrator/sudo")
            elif "cannot find" in str(e).lower() or "not found" in str(e).lower():
                print("   💡 Tip: Double-check the port name")
                print("   💡 Tip: Make sure the device is connected")
            return False
        except Exception as e:
            print(f"❌ Unexpected error testing {port}: {e}")
            return False
    
    def test_pump_communication(self, port: str, baud_rate: int = 9600) -> Dict[str, Any]:
        """Test actual pump communication"""
        print(f"\n🔍 Testing MKR5 pump communication on {port}...")
        
        results = {
            'port': port,
            'baud_rate': baud_rate,
            'connected': False,
            'pumps_found': [],
            'responses_received': 0,
            'errors': []
        }
        
        try:
            with serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=8,
                stopbits=1,
                parity=serial.PARITY_ODD,
                timeout=0.5,
                write_timeout=1.0
            ) as ser:
                
                results['connected'] = True
                print("✅ Serial connection established")
                
                # Test a range of pump addresses
                test_addresses = list(range(self.MIN_PUMP_ADDRESS, min(self.MIN_PUMP_ADDRESS + 10, self.MAX_PUMP_ADDRESS + 1)))
                print(f"🔍 Testing pump addresses: {[f'0x{addr:02X}' for addr in test_addresses]}")
                
                for address in test_addresses:
                    print(f"   Testing pump 0x{address:02X}...", end=' ', flush=True)
                    
                    try:
                        # Clear buffers
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                        
                        # Send RETURN_STATUS command
                        message = self.create_command_message(address, self.RETURN_STATUS)
                        ser.write(message)
                        
                        # Wait for response
                        time.sleep(0.1)
                        
                        if ser.in_waiting > 0:
                            response = ser.read(ser.in_waiting)
                            results['responses_received'] += 1
                            
                            if len(response) >= 8:  # Minimum valid response length
                                # Parse basic response
                                resp_addr = response[0]
                                resp_ctrl = response[1]
                                resp_trans = response[2]
                                resp_len = response[3]
                                
                                if resp_addr == address and resp_trans == 0x01:  # Status response
                                    status = response[4] if len(response) > 4 else 0
                                    status_name = self.get_status_name(status)
                                    
                                    pump_info = {
                                        'address': address,
                                        'status': status,
                                        'status_name': status_name,
                                        'raw_response': response.hex()
                                    }
                                    results['pumps_found'].append(pump_info)
                                    print(f"✅ FOUND - Status: {status_name}")
                                else:
                                    print(f"📥 Response (unexpected format): {response.hex()}")
                            else:
                                print(f"📥 Short response: {response.hex()}")
                                results['responses_received'] += 1
                        else:
                            print("❌ No response")
                            
                    except Exception as e:
                        error_msg = f"Error testing pump 0x{address:02X}: {e}"
                        results['errors'].append(error_msg)
                        print(f"❌ Error: {e}")
                    
                    # Small delay between commands
                    time.sleep(0.05)
                
                if results['pumps_found']:
                    print(f"\n✅ Found {len(results['pumps_found'])} pump(s) responding")
                elif results['responses_received'] > 0:
                    print(f"\n⚠️  Received {results['responses_received']} response(s) but couldn't parse pump data")
                    print("   This might indicate communication but wrong protocol or settings")
                else:
                    print(f"\n❌ No pumps found responding on {port}")
                    results['errors'].append("No pumps responded to status requests")
                
        except Exception as e:
            error_msg = f"Communication error: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results
    
    def get_status_name(self, status_code: int) -> str:
        """Convert status code to human-readable name"""
        status_map = {
            0: "PUMP_NOT_PROGRAMMED",
            1: "RESET",
            2: "AUTHORIZED", 
            4: "FILLING",
            5: "FILLING_COMPLETED",
            6: "MAX_AMOUNT_VOLUME_REACHED",
            7: "SWITCHED_OFF"
        }
        return status_map.get(status_code, f"UNKNOWN({status_code})")
    
    def interactive_test(self):
        """Interactive testing mode"""
        print("🚀 MKR5 COM Port Tester - Simple Version")
        print("=" * 50)
        
        # List available ports
        available_ports = self.list_available_ports()
        
        if not available_ports:
            print("❌ No COM ports available. Please check your connections.")
            print("\n💡 Troubleshooting tips:")
            print("   • Make sure your USB-to-Serial adapter is connected")
            print("   • Check Device Manager (Windows) or lsusb (Linux)")
            print("   • Try unplugging and reconnecting the device")
            return
        
        # Let user select port
        while True:
            try:
                print(f"\nSelect a COM port to test (1-{len(available_ports)}) or 'q' to quit:")
                choice = input("Enter your choice: ").strip().lower()
                
                if choice == 'q':
                    print("👋 Goodbye!")
                    return
                
                port_index = int(choice) - 1
                if 0 <= port_index < len(available_ports):
                    selected_port = available_ports[port_index]
                    break
                else:
                    print(f"❌ Invalid choice. Please enter 1-{len(available_ports)}")
                    
            except ValueError:
                print("❌ Invalid input. Please enter a number or 'q'")
        
        # Select baud rate
        print(f"\nSelect baud rate:")
        print("1. 9600 (most common for MKR5)")
        print("2. 19200 (for shorter distances)")
        print("3. 4800")
        print("4. 38400")
        
        baud_choice = input("Enter your choice (1-4, default is 1): ").strip()
        baud_rates = {
            '2': 19200,
            '3': 4800, 
            '4': 38400
        }
        baud_rate = baud_rates.get(baud_choice, 9600)
        
        print(f"\n📡 Testing {selected_port} at {baud_rate} baud...")
        print("=" * 50)
        
        # Test basic connectivity
        if not self.test_port_basic(selected_port, baud_rate):
            print("❌ Basic port test failed. Check your connections and try again.")
            return
        
        # Test pump communication
        results = self.test_pump_communication(selected_port, baud_rate)
        
        # Display results summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        print(f"Port: {results['port']}")
        print(f"Baud Rate: {results['baud_rate']}")
        print(f"Connection: {'✅ Success' if results['connected'] else '❌ Failed'}")
        print(f"Responses Received: {results['responses_received']}")
        print(f"Pumps Found: {len(results['pumps_found'])}")
        
        if results['pumps_found']:
            print("\n📋 Discovered Pumps:")
            for pump in results['pumps_found']:
                print(f"   • Address 0x{pump['address']:02X} ({pump['address']}) - {pump['status_name']}")
                print(f"     Raw Response: {pump['raw_response']}")
        
        if results['errors']:
            print("\n⚠️  Errors encountered:")
            for error in results['errors']:
                print(f"   • {error}")
        
        # Configuration suggestion
        if results['connected'] and results['pumps_found']:
            print(f"\n🎉 SUCCESS! Your configuration is working!")
            print(f"\n📝 Update your .env file with these settings:")
            print(f"   COM_PORT={selected_port}")
            print(f"   BAUD_RATE={baud_rate}")
            print(f"\nYou can now start the API server with: python run_server.py")
        elif results['connected'] and results['responses_received'] > 0:
            print(f"\n⚠️  Port connection works and received responses, but couldn't identify pumps.")
            print(f"   • Responses received: {results['responses_received']}")
            print(f"   • Try different baud rates")
            print(f"   • Check protocol documentation")
            print(f"   • Verify pump configuration")
        elif results['connected']:
            print(f"\n⚠️  Port connection works but no responses received.")
            print(f"   • Check that pumps are powered on")
            print(f"   • Verify pump addresses (should be 0x50-0x6F)")
            print(f"   • Check wiring: TX to RX, RX to TX, GND to GND")
            print(f"   • Try different baud rate (9600 vs 19200)")
            print(f"   • Check if RS-485 termination resistors are needed")
        else:
            print(f"\n❌ Connection failed.")
            print(f"   • Check COM port selection")
            print(f"   • Verify cable connections")
            print(f"   • Check if another program is using the port")
            print(f"   • Make sure drivers are installed")


def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Manual mode with command line arguments
        port = sys.argv[1]
        baud_rate = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
        
        tester = SimpleCOMPortTester()
        print(f"🔍 Testing {port} at {baud_rate} baud...")
        
        if tester.test_port_basic(port, baud_rate):
            results = tester.test_pump_communication(port, baud_rate)
            success = results['connected'] and len(results['pumps_found']) > 0
            print(f"{'✅ SUCCESS' if success else '❌ FAILED'}")
            sys.exit(0 if success else 1)
        else:
            print("❌ FAILED")
            sys.exit(1)
    else:
        # Interactive mode
        tester = SimpleCOMPortTester()
        tester.interactive_test()


if __name__ == "__main__":
    main()
