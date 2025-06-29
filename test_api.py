#!/usr/bin/env python3
"""
Test script for MKR5 Pump Control API
Demonstrates various API endpoints and functionality
"""

import requests
import json
import time
from typing import Dict, Any


class PumpAPITester:
    """Test client for MKR5 Pump Control API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_health(self) -> Dict[str, Any]:
        """Test health check endpoint"""
        print("🔍 Testing health check...")
        response = self.session.get(f"{self.base_url}/health")
        result = response.json()
        
        if result["success"]:
            print("✅ Health check passed")
            print(f"   Simulation mode: {result['data']['simulation_mode']}")
            print(f"   Port: {result['data']['port']}")
            print(f"   Baud rate: {result['data']['baud_rate']}")
        else:
            print("❌ Health check failed")
        
        return result
    
    def test_scan_pumps(self) -> Dict[str, Any]:
        """Test pump scanning endpoint"""
        print("\n🔍 Testing pump scan...")
        response = self.session.get(f"{self.base_url}/pumps/scan")
        result = response.json()
        
        if result["success"]:
            print(f"✅ Scan completed successfully")
            print(f"   Found {result['total_pumps_found']} pumps")
            print(f"   Scan range: {result['scan_range']['min_address_hex']} - {result['scan_range']['max_address_hex']}")
            
            for i, pump in enumerate(result["pumps"], 1):
                status_name = self.get_status_name(pump["status"])
                print(f"   Pump {i}: Address 0x{pump['address']:02X} ({pump['address']}) - Status: {status_name}")
                if pump["identity"]:
                    print(f"           Identity: {pump['identity']}")
                if pump["nozzles"]:
                    for nozzle in pump["nozzles"]:
                        nozzle_status = "OUT" if nozzle["is_out"] else "IN"
                        print(f"           Nozzle {nozzle['nozzle_number']}: {nozzle_status}, Price: ${nozzle['filling_price']:.2f}")
        else:
            print("❌ Pump scan failed")
        
        return result
    
    def test_pump_status(self, address: str) -> Dict[str, Any]:
        """Test getting individual pump status"""
        print(f"\n🔍 Testing pump status for address {address}...")
        response = self.session.get(f"{self.base_url}/pumps/{address}/status")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                data = result["data"]
                status_name = self.get_status_name(data["status"])
                print(f"✅ Pump status retrieved")
                print(f"   Address: 0x{data['address']:02X} ({data['address']})")
                print(f"   Status: {status_name}")
                print(f"   Transaction: {data['transaction']}")
                if "nozzle_number" in data:
                    nozzle_status = "OUT" if data.get("nozzle_out", False) else "IN"
                    print(f"   Nozzle {data['nozzle_number']}: {nozzle_status}")
                if "filling_price" in data:
                    print(f"   Filling Price: ${data['filling_price']:.2f}")
            else:
                print("❌ Failed to get pump status")
        elif response.status_code == 404:
            print(f"❌ Pump at address {address} not found or not responding")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            
        return response.json() if response.status_code == 200 else {"error": response.status_code}
    
    def test_switch_off_pump(self, address: str) -> Dict[str, Any]:
        """Test switching off a specific pump"""
        print(f"\n🔍 Testing SWITCH_OFF command for pump {address}...")
        response = self.session.post(f"{self.base_url}/pumps/{address}/switch-off")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                data = result["data"]
                print(f"✅ SWITCH_OFF command sent successfully")
                print(f"   Pump Address: {data.get('pump_address', 'N/A')}")
                print(f"   Command: {data.get('command', 'N/A')}")
                if "new_status" in data:
                    print(f"   New Status: {data.get('status_name', 'N/A')} ({data.get('new_status', 'N/A')})")
                print(f"   Message: {result['message']}")
            else:
                print("❌ SWITCH_OFF command failed")
        elif response.status_code == 404:
            print(f"❌ Pump at address {address} not found or not responding")
        elif response.status_code == 503:
            print(f"❌ Serial connection not available")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            try:
                error_detail = response.json().get("detail", "Unknown error")
                print(f"   Details: {error_detail}")
            except:
                pass
            
        return response.json() if response.status_code == 200 else {"error": response.status_code}
    
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
    
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting MKR5 Pump API Tests")
        print("=" * 50)
        
        # Test health
        health_result = self.test_health()
        
        # Test scan
        scan_result = self.test_scan_pumps()
        
        # Test individual pump status for found pumps
        if scan_result.get("success") and scan_result["pumps"]:
            # Test first pump with hex address
            first_pump = scan_result["pumps"][0]
            self.test_pump_status(f"0x{first_pump['address']:02X}")
            
            # Test another pump with decimal address
            if len(scan_result["pumps"]) > 1:
                second_pump = scan_result["pumps"][1]
                self.test_pump_status(str(second_pump["address"]))
            
            # Test SWITCH_OFF command on first pump
            print(f"\n🔍 Testing SWITCH_OFF command...")
            first_pump_addr = f"0x{first_pump['address']:02X}"
            self.test_switch_off_pump(first_pump_addr)
            
            # Check status after switch off
            time.sleep(0.5)  # Small delay
            self.test_pump_status(first_pump_addr)
        
        # Test non-existent pump
        print(f"\n🔍 Testing non-existent pump...")
        self.test_pump_status("60")  # Should not exist in simulation
        
        print("\n" + "=" * 50)
        print("🏁 All tests completed!")


def main():
    """Main test function"""
    # Wait a moment for server to be ready
    time.sleep(1)
    
    try:
        tester = PumpAPITester()
        tester.run_all_tests()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API server.")
        print("   Make sure the server is running on http://localhost:8000")
        print("   Run: python run_server.py")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")


if __name__ == "__main__":
    main()
