#!/usr/bin/env python3
"""
CRC-16 Verification Tool for MKR5 Protocol

This tool verifies that our CRC-16 implementation matches the MKR5 specification:
- CRC-16 calculated from ADR to last byte of data
- CRC initialized to 0000h
- Recalculated CRC from ADR to CRC-H must be 0000h
"""

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CRCVerifier:
    """CRC-16 verification according to MKR5 specification"""
    
    def __init__(self):
        pass
    
    def calculate_crc16_ccitt(self, data: bytes) -> int:
        """
        Calculate CRC-16 CCITT checksum (our current implementation)
        Polynomial: 0x1021
        Initial value: 0x0000
        """
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
    
    def calculate_crc16_modbus(self, data: bytes) -> int:
        """
        Calculate CRC-16 Modbus checksum (alternative implementation)
        Polynomial: 0x8005
        Initial value: 0xFFFF
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def calculate_crc16_ansi(self, data: bytes) -> int:
        """
        Calculate CRC-16 ANSI checksum (another alternative)
        Polynomial: 0x8005
        Initial value: 0x0000
        """
        crc = 0x0000
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def verify_frame_crc(self, frame: bytes, crc_algorithm: str = "ccitt") -> dict:
        """
        Verify CRC of a complete MKR5 frame
        
        Args:
            frame: Complete frame including CRC, ETX, SF
            crc_algorithm: "ccitt", "modbus", or "ansi"
        
        Returns:
            dict: Verification results
        """
        if len(frame) < 9:  # Minimum frame size
            return {"error": "Frame too short"}
        
        # Extract parts
        # Frame format: ADR CTRL TRANS LNG DATA... CRC_L CRC_H ETX SF
        data_end = len(frame) - 4  # Remove CRC_L, CRC_H, ETX, SF
        message_data = frame[:data_end]  # ADR to last data byte
        received_crc_l = frame[data_end]
        received_crc_h = frame[data_end + 1]
        received_crc = (received_crc_h << 8) | received_crc_l
        etx = frame[data_end + 2]
        sf = frame[data_end + 3]
        
        # Calculate CRC based on algorithm
        if crc_algorithm == "ccitt":
            calculated_crc = self.calculate_crc16_ccitt(message_data)
        elif crc_algorithm == "modbus":
            calculated_crc = self.calculate_crc16_modbus(message_data)
        elif crc_algorithm == "ansi":
            calculated_crc = self.calculate_crc16_ansi(message_data)
        else:
            return {"error": f"Unknown CRC algorithm: {crc_algorithm}"}
        
        # Verification test: recalculate CRC from ADR to CRC_H
        # According to spec, this should result in 0x0000
        data_with_crc = frame[:data_end + 2]  # ADR to CRC_H
        if crc_algorithm == "ccitt":
            verification_crc = self.calculate_crc16_ccitt(data_with_crc)
        elif crc_algorithm == "modbus":
            verification_crc = self.calculate_crc16_modbus(data_with_crc)
        elif crc_algorithm == "ansi":
            verification_crc = self.calculate_crc16_ansi(data_with_crc)
        
        return {
            "frame_hex": frame.hex().upper(),
            "message_data": message_data.hex().upper(),
            "received_crc": f"0x{received_crc:04X}",
            "calculated_crc": f"0x{calculated_crc:04X}",
            "crc_match": received_crc == calculated_crc,
            "verification_crc": f"0x{verification_crc:04X}",
            "verification_pass": verification_crc == 0x0000,
            "etx": f"0x{etx:02X}",
            "sf": f"0x{sf:02X}",
            "algorithm": crc_algorithm
        }
    
    def test_known_frames(self):
        """Test CRC calculation on known MKR5 frames"""
        logger.info("🔍 Testing CRC calculation on known MKR5 frames")
        logger.info("=" * 60)
        
        # Test frames from our logs
        test_frames = [
            {
                "name": "Status Request",
                "frame": bytes.fromhex("5081010100BFBA03FA"),
                "description": "Standard status request to pump 0x50"
            },
            {
                "name": "Price Update",
                "frame": bytes.fromhex("50810518015500015500015500015500015500015500015500015500617003FA"),
                "description": "Price update command with 8 nozzles"
            },
            {
                "name": "Switch Off Command",
                "frame": bytes.fromhex("50810100009F9A03FA"),
                "description": "Switch off command to pump 0x50"
            }
        ]
        
        algorithms = ["ccitt", "modbus", "ansi"]
        
        for frame_info in test_frames:
            logger.info(f"\n📊 Testing: {frame_info['name']}")
            logger.info(f"   Description: {frame_info['description']}")
            logger.info(f"   Frame: {frame_info['frame'].hex().upper()}")
            
            for algorithm in algorithms:
                result = self.verify_frame_crc(frame_info['frame'], algorithm)
                
                logger.info(f"\n   🔧 Algorithm: {algorithm.upper()}")
                if "error" in result:
                    logger.error(f"      ❌ Error: {result['error']}")
                else:
                    logger.info(f"      Message Data: {result['message_data']}")
                    logger.info(f"      Received CRC: {result['received_crc']}")
                    logger.info(f"      Calculated CRC: {result['calculated_crc']}")
                    logger.info(f"      CRC Match: {'✅' if result['crc_match'] else '❌'}")
                    logger.info(f"      Verification CRC: {result['verification_crc']}")
                    logger.info(f"      Verification Pass: {'✅' if result['verification_pass'] else '❌'}")
                    
                    if result['crc_match'] and result['verification_pass']:
                        logger.info(f"      🎉 PERFECT MATCH - This is likely the correct algorithm!")
                    elif result['crc_match']:
                        logger.info(f"      ⚠️  CRC matches but verification failed")
                    elif result['verification_pass']:
                        logger.info(f"      ⚠️  Verification passes but CRC doesn't match")
    
    def test_manual_crc_calculation(self):
        """Manually test CRC calculation step by step"""
        logger.info("\n🔍 Manual CRC calculation test")
        logger.info("=" * 60)
        
        # Test with simple status request
        test_data = bytes([0x50, 0x81, 0x01, 0x01, 0x00])  # ADR to DATA
        
        logger.info(f"Test data: {test_data.hex().upper()}")
        logger.info(f"Bytes: {[f'0x{b:02X}' for b in test_data]}")
        
        # Calculate with different algorithms
        algorithms = {
            "CCITT": self.calculate_crc16_ccitt,
            "Modbus": self.calculate_crc16_modbus,
            "ANSI": self.calculate_crc16_ansi
        }
        
        for name, func in algorithms.items():
            crc = func(test_data)
            logger.info(f"{name}: 0x{crc:04X} (CRC_L=0x{crc & 0xFF:02X}, CRC_H=0x{(crc >> 8) & 0xFF:02X})")
    
    def run_verification(self):
        """Run complete CRC verification"""
        logger.info("🚀 Starting CRC-16 Verification for MKR5 Protocol")
        logger.info("=" * 60)
        logger.info("Testing our CRC implementation against MKR5 specification:")
        logger.info("- CRC-16 calculated from ADR to last byte of data")
        logger.info("- CRC initialized to 0000h")
        logger.info("- Recalculated CRC from ADR to CRC-H must be 0000h")
        logger.info("=" * 60)
        
        self.test_manual_crc_calculation()
        self.test_known_frames()
        
        logger.info("\n" + "=" * 60)
        logger.info("🏁 CRC VERIFICATION COMPLETE")
        logger.info("=" * 60)
        logger.info("Look for algorithms that show:")
        logger.info("- CRC Match: ✅ (our calculated CRC matches frame CRC)")
        logger.info("- Verification Pass: ✅ (CRC from ADR to CRC-H equals 0000h)")
        logger.info("The algorithm with both ✅ is the correct one!")

def main():
    verifier = CRCVerifier()
    verifier.run_verification()

if __name__ == "__main__":
    main()
