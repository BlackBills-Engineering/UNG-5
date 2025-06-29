#!/usr/bin/env python3
"""
COM Port Testing Utility for MKR5 Pump Control API
This utility helps you verify your serial connection and test communication with real pumps
"""

import serial
import serial.tools.list_ports
import time
import sys
import os
from typing import List, Optional, Dict, Any
import struct

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.models import PumpCommand, PumpStatus
    from src.protocol import MKR5Protocol
except ImportError:
    # Fallback for direct execution
    from models import PumpCommand, PumpStatus
    from protocol import MKR5Protocol


class COMPortTester:
    """COM Port testing and diagnostic utility"""
    
    def __init__(self):
        self.protocol = None
    
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
            print(f"      Hardware ID: {port.hwid}")
            print()
            available_ports.append(port.device)
        
        return available_ports
    
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
                timeout=1.0
            ) as ser:
                print(f"✅ Successfully opened {port}")
                print(f"   Settings: {baud_rate} baud, 8 data bits, 1 stop bit, odd parity")
                print(f"   Port info: {ser}")
                
                # Test if we can write to the port
                test_data = b'\x50\x81\x01\x01\x00\x00\x00\x03\xFA'  # Sample command
                ser.write(test_data)
                print(f"✅ Successfully wrote {len(test_data)} bytes to port")
                
                # Try to read any response (with timeout)
                time.sleep(0.1)
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"📥 Received {len(response)} bytes: {response.hex()}")
                else:
                    print("📭 No immediate response (this is normal if no pumps are connected)")
                
                return True
                
        except serial.SerialException as e:
            print(f"❌ Failed to open {port}: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error testing {port}: {e}")
            return False
    
    def test_pump_communication(self, port: str, baud_rate: int = 9600) -> Dict[str, Any]:
        """Test actual pump communication using MKR5 protocol"""
        print(f"\n🔍 Testing MKR5 pump communication on {port}...")
        
        results = {
            'port': port,
            'baud_rate': baud_rate,
            'connected': False,
            'pumps_found': [],
            'errors': []
        }
        
        try:
            # Initialize protocol
            self.protocol = MKR5Protocol(port=port, baud_rate=baud_rate)
            
            if not self.protocol.connect():
                results['errors'].append("Failed to establish protocol connection")
                return results
            
            results['connected'] = True
            print("✅ MKR5 protocol connection established")
            
            # Test a few pump addresses
            test_addresses = [0x50, 0x51, 0x52, 0x53, 0x54]  # Test first 5 addresses
            
            print(f"🔍 Testing pump addresses: {[f'0x{addr:02X}' for addr in test_addresses]}")
            
            for address in test_addresses:
                print(f"   Testing pump 0x{address:02X}...", end=' ')
                
                try:
                    response = self.protocol.send_command(address, PumpCommand.RETURN_STATUS, timeout=0.5)
                    
                    if response:
                        pump_info = {
                            'address': address,
                            'status': response.get('status', 0),
                            'status_name': self.get_status_name(response.get('status', 0)),
                            'raw_response': response
                        }
                        results['pumps_found'].append(pump_info)
                        print(f"✅ FOUND - Status: {pump_info['status_name']}")
                        
                        # Try to get pump identity
                        identity_response = self.protocol.send_command(address, PumpCommand.RETURN_PUMP_IDENTITY, timeout=0.5)
                        if identity_response and 'identity' in identity_response:
                            pump_info['identity'] = identity_response['identity']
                            print(f"      Identity: {identity_response['identity']}")
                    else:
                        print("❌ No response")
                        
                except Exception as e:
                    error_msg = f"Error testing pump 0x{address:02X}: {e}"
                    results['errors'].append(error_msg)
                    print(f"❌ Error: {e}")
            
            if results['pumps_found']:
                print(f"\n✅ Found {len(results['pumps_found'])} pump(s) responding")
            else:
                print(f"\n❌ No pumps found responding on {port}")
                results['errors'].append("No pumps responded to status requests")
            
        except Exception as e:
            error_msg = f"Protocol communication error: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        finally:
            if self.protocol:
                self.protocol.disconnect()
        
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
        print("🚀 MKR5 COM Port Interactive Tester")
        print("=" * 50)
        
        # List available ports
        available_ports = self.list_available_ports()
        
        if not available_ports:
            print("❌ No COM ports available. Please check your connections.")
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
        print("1. 9600 (default)")
        print("2. 19200")
        
        baud_choice = input("Enter your choice (1 or 2, default is 1): ").strip()
        baud_rate = 19200 if baud_choice == '2' else 9600
        
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
        print(f"Pumps Found: {len(results['pumps_found'])}")
        
        if results['pumps_found']:
            print("\n📋 Discovered Pumps:")
            for pump in results['pumps_found']:
                print(f"   • Address 0x{pump['address']:02X} ({pump['address']}) - {pump['status_name']}")
                if 'identity' in pump:
                    print(f"     Identity: {pump['identity']}")
        
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
        elif results['connected']:
            print(f"\n⚠️  Port connection works but no pumps found.")
            print(f"   • Check that pumps are powered on")
            print(f"   • Verify pump addresses (should be 0x50-0x6F)")
            print(f"   • Check wiring and connections")
            print(f"   • Try different baud rate (9600 vs 19200)")
        else:
            print(f"\n❌ Connection failed.")
            print(f"   • Check COM port selection")
            print(f"   • Verify cable connections")
            print(f"   • Check if another program is using the port")
            print(f"   • Try different baud rate")


def manual_test(port: str, baud_rate: int = 9600):
    """Manual test mode for command line usage"""
    tester = COMPortTester()
    
    print(f"🔍 Testing {port} at {baud_rate} baud...")
    
    # Basic test
    if not tester.test_port_basic(port, baud_rate):
        return False
    
    # Communication test
    results = tester.test_pump_communication(port, baud_rate)
    
    # Print results
    if results['connected'] and results['pumps_found']:
        print(f"✅ SUCCESS: Found {len(results['pumps_found'])} pump(s)")
        return True
    else:
        print(f"❌ FAILED: No pumps found")
        return False


def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Manual mode with command line arguments
        port = sys.argv[1]
        baud_rate = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
        success = manual_test(port, baud_rate)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        tester = COMPortTester()
        tester.interactive_test()


if __name__ == "__main__":
    main()
