#!/usr/bin/env python3
"""
Simple CRC Byte Order Investigation
Using our existing CRC implementation to test byte order
"""

import logging
import sys
import os

# Add src directory to path so we can import our protocol
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from protocol import MKR5Protocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_crc_verification():
    """Test CRC verification according to MKR5 spec"""
    
    protocol = MKR5Protocol()
    
    logger.info("🚀 CRC Byte Order Investigation - MKR5 Specification")
    logger.info("=" * 60)
    logger.info("Spec: CRC-16 from ADR to last data byte, init to 0000h")  
    logger.info("Spec: Recalculated CRC from ADR to CRC-H must be 0000h")
    logger.info("=" * 60)
    
    # Test our actual frames
    test_frames = [
        {
            "name": "Status Request",
            "frame": "5081010100BFBA03FA",
            "message_end": 5  # Message data ends at byte 5 (0-indexed)
        },
        {
            "name": "Price Update", 
            "frame": "50810518015500015500015500015500015500015500015500015500617003FA",
            "message_end": 28  # Message data ends at byte 28
        },
        {
            "name": "Switch Off",
            "frame": "50810100009F9A03FA", 
            "message_end": 5  # Message data ends at byte 5
        }
    ]
    
    for test in test_frames:
        logger.info(f"\n🔍 Testing: {test['name']}")
        logger.info(f"   Frame: {test['frame']}")
        
        frame_bytes = bytes.fromhex(test['frame'])
        message_data = frame_bytes[:test['message_end']]
        crc_bytes = frame_bytes[test['message_end']:test['message_end']+2]
        
        logger.info(f"   Message data: {message_data.hex().upper()}")
        logger.info(f"   CRC bytes: {crc_bytes.hex().upper()}")
        
        # Calculate CRC of message data
        calculated_crc = protocol.calculate_crc16(message_data)
        logger.info(f"   Calculated CRC: 0x{calculated_crc:04X}")
        
        # Test both byte orders in the frame
        crc_as_big_endian = (crc_bytes[0] << 8) | crc_bytes[1]
        crc_as_little_endian = (crc_bytes[1] << 8) | crc_bytes[0]
        
        logger.info(f"   Frame CRC (as big-endian): 0x{crc_as_big_endian:04X}")
        logger.info(f"   Frame CRC (as little-endian): 0x{crc_as_little_endian:04X}")
        
        # Check which matches our calculation
        if calculated_crc == crc_as_big_endian:
            logger.info("   ✅ CRC matches big-endian interpretation")
            crc_match = "big-endian"
        elif calculated_crc == crc_as_little_endian:
            logger.info("   ✅ CRC matches little-endian interpretation")
            crc_match = "little-endian"
        else:
            logger.info("   ❌ CRC doesn't match either interpretation")
            crc_match = None
        
        # Now test the verification (should be 0x0000)
        # Test 1: Big-endian storage (high byte first)
        verify_frame_big = message_data + crc_bytes
        verify_crc_big = protocol.calculate_crc16(verify_frame_big)
        logger.info(f"   Verification (big-endian storage): 0x{verify_crc_big:04X}")
        
        # Test 2: Little-endian storage (low byte first)
        verify_frame_little = message_data + bytes([crc_bytes[1], crc_bytes[0]])
        verify_crc_little = protocol.calculate_crc16(verify_frame_little)
        logger.info(f"   Verification (little-endian storage): 0x{verify_crc_little:04X}")
        
        # Test 3: Verify with our calculated CRC in both orders
        calc_crc_high = (calculated_crc >> 8) & 0xFF
        calc_crc_low = calculated_crc & 0xFF
        
        # Big-endian: high byte first
        verify_calc_big = message_data + bytes([calc_crc_high, calc_crc_low])
        verify_calc_big_result = protocol.calculate_crc16(verify_calc_big)
        logger.info(f"   Verification (calculated, big-endian): 0x{verify_calc_big_result:04X}")
        
        # Little-endian: low byte first  
        verify_calc_little = message_data + bytes([calc_crc_low, calc_crc_high])
        verify_calc_little_result = protocol.calculate_crc16(verify_calc_little)
        logger.info(f"   Verification (calculated, little-endian): 0x{verify_calc_little_result:04X}")
        
        # Summary
        logger.info("   Summary:")
        if verify_crc_big == 0x0000:
            logger.info("   ✅ Frame uses big-endian CRC storage (spec compliant)")
        elif verify_crc_little == 0x0000:
            logger.info("   ✅ Frame uses little-endian CRC storage (spec compliant)")
        elif verify_calc_big_result == 0x0000:
            logger.info("   ✅ Should use big-endian CRC storage")
        elif verify_calc_little_result == 0x0000:
            logger.info("   ✅ Should use little-endian CRC storage")
        else:
            logger.info("   ❌ No configuration gives 0x0000 verification")

def test_correct_frame_generation():
    """Generate frames with correct CRC according to spec"""
    
    protocol = MKR5Protocol()
    
    logger.info("\n🔧 Generating frames with correct CRC")
    logger.info("=" * 40)
    
    # Test message
    message = bytes([0x50, 0x81, 0x01, 0x01, 0x00])  # Status request
    crc = protocol.calculate_crc16(message)
    
    logger.info(f"Message: {message.hex().upper()}")
    logger.info(f"Calculated CRC: 0x{crc:04X}")
    
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    
    # Test both storage orders
    frame_big = message + bytes([crc_high, crc_low])
    frame_little = message + bytes([crc_low, crc_high])
    
    logger.info(f"Frame (big-endian CRC): {frame_big.hex().upper()}")
    logger.info(f"Frame (little-endian CRC): {frame_little.hex().upper()}")
    
    # Verify both
    verify_big = protocol.calculate_crc16(frame_big)
    verify_little = protocol.calculate_crc16(frame_little)
    
    logger.info(f"Verification (big-endian): 0x{verify_big:04X}")
    logger.info(f"Verification (little-endian): 0x{verify_little:04X}")
    
    if verify_big == 0x0000:
        logger.info("✅ Big-endian storage is correct per MKR5 spec!")
        logger.info(f"   Correct frame format: {frame_big.hex().upper()}")
    elif verify_little == 0x0000:
        logger.info("✅ Little-endian storage is correct per MKR5 spec!")
        logger.info(f"   Correct frame format: {frame_little.hex().upper()}")

def main():
    test_crc_verification()
    test_correct_frame_generation()
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 CRC INVESTIGATION COMPLETE")
    logger.info("=" * 60)
    logger.info("The correct byte order should give 0x0000 verification")
    logger.info("This tells us how the POS system expects CRC bytes")

if __name__ == "__main__":
    main()
