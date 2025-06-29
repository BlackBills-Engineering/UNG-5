#!/usr/bin/env python3
"""
Serial Port Monitor - Capture POS System Communication

This tool monitors the serial port to capture the actual communication
between the original POS system and the pump. Run this while the POS
system is communicating to see what it's actually sending.
"""

import serial
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SerialMonitor:
    def __init__(self, port: str = "COM3", baud: int = 19200):
        self.port = port
        self.baud = baud
        
    def monitor_communication(self, duration: int = 60):
        """Monitor serial communication for specified duration"""
        logger.info(f"🔍 Starting serial port monitor on {self.port} at {self.baud} baud")
        logger.info(f"📊 Will monitor for {duration} seconds")
        logger.info("👉 Start your POS system communication now!")
        logger.info("-" * 60)
        
        try:
            with serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=0.1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            ) as ser:
                
                start_time = time.time()
                packet_count = 0
                
                while (time.time() - start_time) < duration:
                    # Read any available data
                    data = ser.read(1000)  # Read up to 1000 bytes
                    
                    if data:
                        packet_count += 1
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        
                        logger.info(f"📦 Packet #{packet_count} at {timestamp}")
                        logger.info(f"   Length: {len(data)} bytes")
                        logger.info(f"   Hex: {data.hex().upper()}")
                        
                        # Try to decode as ASCII (for debugging)
                        try:
                            ascii_data = data.decode('ascii', errors='replace')
                            printable_ascii = ''.join(c if c.isprintable() else '.' for c in ascii_data)
                            logger.info(f"   ASCII: {printable_ascii}")
                        except:
                            pass
                        
                        # Parse as potential MKR5 frame
                        self.analyze_mkr5_frame(data)
                        logger.info("-" * 40)
                    
                    time.sleep(0.01)  # Small delay to prevent CPU spinning
                
                logger.info(f"✅ Monitoring complete. Captured {packet_count} packets.")
                
        except Exception as e:
            logger.error(f"❌ Error monitoring serial port: {e}")
    
    def analyze_mkr5_frame(self, data: bytes):
        """Analyze data as potential MKR5 frame"""
        if len(data) < 9:  # Minimum MKR5 frame size
            logger.info("   Analysis: Too short for MKR5 frame")
            return
        
        # Check for MKR5-like structure
        if data[-2:] == b'\x03\xFA':  # ETX + SF
            logger.info("   Analysis: Ends with MKR5 termination (03 FA)")
            
            # Parse basic structure
            if len(data) >= 9:
                adr = data[0]
                ctrl = data[1]
                trans = data[2]
                lng = data[3]
                
                logger.info(f"   MKR5 Structure:")
                logger.info(f"     ADR: 0x{adr:02X} (pump address)")
                logger.info(f"     CTRL: 0x{ctrl:02X} (control)")
                logger.info(f"     TRANS: 0x{trans:02X} (transaction)")
                logger.info(f"     LNG: 0x{lng:02X} (data length: {lng})")
                
                # Check if data length matches
                expected_total = 4 + lng + 2 + 2 + 1  # Header + data + CRC + ETX + SF
                if len(data) == expected_total:
                    logger.info("   ✅ Frame length matches LNG field")
                else:
                    logger.info(f"   ⚠️  Frame length mismatch: got {len(data)}, expected {expected_total}")
        else:
            logger.info("   Analysis: Not standard MKR5 termination")

def main():
    print("🔍 Serial Port Monitor for POS System Analysis")
    print("=" * 50)
    print("This tool will capture communication between your")
    print("original POS system and the pump.")
    print()
    print("INSTRUCTIONS:")
    print("1. Make sure the POS system is NOT running")
    print("2. Start this monitor")
    print("3. Start your POS system")
    print("4. Perform some pump operations (status check, etc.)")
    print("5. Let it run for 30-60 seconds")
    print("=" * 50)
    
    # Get user input
    port = input("Enter COM port (default: COM3): ").strip() or "COM3"
    baud_input = input("Enter baud rate (default: 19200): ").strip()
    baud = int(baud_input) if baud_input else 19200
    duration_input = input("Monitor duration in seconds (default: 60): ").strip()
    duration = int(duration_input) if duration_input else 60
    
    monitor = SerialMonitor(port, baud)
    monitor.monitor_communication(duration)

if __name__ == "__main__":
    main()
