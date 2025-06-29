#!/usr/bin/env python3
"""
Test script for the new filling information endpoint
"""

import requests
import json
import sys

def test_filling_info_endpoint():
    """Test the new /pumps/{address}/filling-info endpoint"""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Testing RETURN_FILLING_INFORMATION endpoint...")
    print("=" * 50)
    
    # Test addresses - you can modify these based on your pump setup
    test_addresses = ["50", "0x50", "80"]  # Same address in different formats
    
    for address in test_addresses:
        print(f"\n📍 Testing pump address: {address}")
        
        try:
            # Test the new filling info endpoint
            response = requests.get(f"{base_url}/pumps/{address}/filling-info", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success!")
                print(f"   Filled Volume: {data['data'].get('filled_volume', 'N/A')} L")
                print(f"   Filled Amount: {data['data'].get('filled_amount', 'N/A')}")
                print(f"   Nozzle Number: {data['data'].get('nozzle_number', 'N/A')}")
                print(f"   Nozzle Out: {data['data'].get('is_nozzle_out', 'N/A')}")
                print(f"   Filling Price: {data['data'].get('filling_price', 'N/A')}")
                print(f"   Raw response: {json.dumps(data, indent=2)}")
                
            elif response.status_code == 404:
                print(f"⚠️  Pump not responding or no filling data available")
                
            elif response.status_code == 503:
                print(f"❌ Serial connection issue: {response.json().get('detail', 'Unknown')}")
                
            else:
                print(f"❌ Error {response.status_code}: {response.json().get('detail', 'Unknown error')}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to API server at {base_url}")
            print("   Make sure the server is running: python run_server.py")
            break
            
        except Exception as e:
            print(f"❌ Error: {e}")

def test_compare_with_status():
    """Compare filling info with regular status to see differences"""
    
    base_url = "http://localhost:8000"
    address = "50"  # Change this to a pump you know exists
    
    print(f"\n🔍 Comparing STATUS vs FILLING_INFO for pump {address}...")
    print("=" * 60)
    
    try:
        # Get regular status
        status_response = requests.get(f"{base_url}/pumps/{address}/status", timeout=5)
        filling_response = requests.get(f"{base_url}/pumps/{address}/filling-info", timeout=5)
        
        if status_response.status_code == 200 and filling_response.status_code == 200:
            status_data = status_response.json()
            filling_data = filling_response.json()
            
            print("📊 STATUS response:")
            print(json.dumps(status_data, indent=2))
            
            print("\n📊 FILLING_INFO response:")
            print(json.dumps(filling_data, indent=2))
            
        else:
            print(f"Status: {status_response.status_code}, Filling: {filling_response.status_code}")
            
    except Exception as e:
        print(f"Error comparing responses: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        test_compare_with_status()
    else:
        test_filling_info_endpoint()
        
    print(f"\n💡 Usage:")
    print(f"   python {sys.argv[0]}           # Test filling info endpoint")
    print(f"   python {sys.argv[0]} compare   # Compare with status endpoint")
