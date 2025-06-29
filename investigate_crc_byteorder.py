#!/usr/bin/env python3
"""
CRC Byte Order Investigation
Testing different byte orders to match MKR5 specification
"""

import logging
import crc16

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_crc16_ccitt(data: bytes) -> int:
    """Calculate CRC-16 CCITT (same as our protocol implementation)"""
    return crc16.crc16xmodem(data, 0x0000)

def test_crc_byte_orders():
    """Test different CRC byte order interpretations"""
    
    # Test frame: Status request
    frame_hex = "5081010100BFBA03FA"
    frame_bytes = bytes.fromhex(frame_hex)
    
    # Extract parts
    message_data = frame_bytes[:-4]  # ADR to last data byte: 5081010100
    crc_bytes = frame_bytes[-4:-2]   # CRC bytes: BFBA
    
    logger.info(f"🔍 Analyzing frame: {frame_hex}")
    logger.info(f"   Message data: {message_data.hex().upper()}")
    logger.info(f"   CRC bytes in frame: {crc_bytes.hex().upper()}")
    logger.info(f"   CRC byte 1: 0x{crc_bytes[0]:02X}")
    logger.info(f"   CRC byte 2: 0x{crc_bytes[1]:02X}")
    
    # Test different interpretations
    crc_big_endian = (crc_bytes[0] << 8) | crc_bytes[1]  # 0xBFBA
    crc_little_endian = (crc_bytes[1] << 8) | crc_bytes[0]  # 0xBABF
    
    logger.info(f"   Big-endian interpretation: 0x{crc_big_endian:04X}")
    logger.info(f"   Little-endian interpretation: 0x{crc_little_endian:04X}")
    
    # Test CCITT with both interpretations
    calculated_crc = calculate_crc16_ccitt(message_data)
    
    logger.info(f"   Calculated CCITT CRC: 0x{calculated_crc:04X}")
    
    # Test verification (should be 0x0000)
    # Big-endian: message + CRC high byte + CRC low byte
    verify_big = message_data + bytes([crc_bytes[0], crc_bytes[1]])
    verify_crc_big = calculate_crc16_ccitt(verify_big)
    
    # Little-endian: message + CRC low byte + CRC high byte  
    verify_little = message_data + bytes([crc_bytes[1], crc_bytes[0]])
    verify_crc_little = calculate_crc16_ccitt(verify_little)
    
    logger.info(f"   Verification (big-endian): 0x{verify_crc_big:04X}")
    logger.info(f"   Verification (little-endian): 0x{verify_crc_little:04X}")
    
    # Test with manual CRC calculation and different byte orders
    logger.info("\n🧮 Testing manual CRC with different byte orders:")
    
    # Our current approach (little-endian result, big-endian storage)
    crc_val = calculated_crc
    crc_high = (crc_val >> 8) & 0xFF
    crc_low = crc_val & 0xFF
    
    logger.info(f"   CRC value: 0x{crc_val:04X}")
    logger.info(f"   CRC high byte: 0x{crc_high:02X}")
    logger.info(f"   CRC low byte: 0x{crc_low:02X}")
    
    # Test 1: Store as [high, low] (big-endian)
    test1_bytes = message_data + bytes([crc_high, crc_low])
    test1_verify = calculate_crc16_ccitt(test1_bytes)
    logger.info(f"   Test 1 [high,low]: {test1_bytes.hex().upper()}")
    logger.info(f"   Test 1 verification: 0x{test1_verify:04X}")
    
    # Test 2: Store as [low, high] (little-endian)
    test2_bytes = message_data + bytes([crc_low, crc_high])
    test2_verify = calculate_crc16_ccitt(test2_bytes)
    logger.info(f"   Test 2 [low,high]: {test2_bytes.hex().upper()}")
    logger.info(f"   Test 2 verification: 0x{test2_verify:04X}")
    
    # Compare with actual frame
    actual_frame_start = frame_bytes[:-2]  # Without ETX+SF
    logger.info(f"   Actual frame (no ETX/SF): {actual_frame_start.hex().upper()}")
    
    if test1_bytes == actual_frame_start:
        logger.info("   ✅ Test 1 matches actual frame!")
    elif test2_bytes == actual_frame_start:
        logger.info("   ✅ Test 2 matches actual frame!")
    else:
        logger.info("   ❌ Neither test matches actual frame")

def test_working_frames():
    """Test frames that should work according to spec"""
    logger.info("\n🔧 Testing known working frames:")
    
    # Let's create a frame from scratch and see what CRC we get
    message = bytes([0x50, 0x81, 0x01, 0x01, 0x00])  # ADR, CTRL, TRANS, LNG, DATA
    crc = calculate_crc16_ccitt(message)
    
    logger.info(f"   Message: {message.hex().upper()}")
    logger.info(f"   Calculated CRC: 0x{crc:04X}")
    
    # Test both byte orders
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    
    # Big-endian storage [high, low]
    frame_big = message + bytes([crc_high, crc_low])
    verify_big = calculate_crc16_ccitt(frame_big)
    logger.info(f"   Frame (big-endian): {frame_big.hex().upper()}")
    logger.info(f"   Verification (big-endian): 0x{verify_big:04X}")
    
    # Little-endian storage [low, high]  
    frame_little = message + bytes([crc_low, crc_high])
    verify_little = calculate_crc16_ccitt(frame_little)
    logger.info(f"   Frame (little-endian): {frame_little.hex().upper()}")
    logger.info(f"   Verification (little-endian): 0x{verify_little:04X}")
    
    # The one that gives 0x0000 verification is correct!
    if verify_big == 0x0000:
        logger.info("   ✅ Big-endian storage is correct!")
    elif verify_little == 0x0000:
        logger.info("   ✅ Little-endian storage is correct!")
    else:
        logger.info("   ❌ Neither gives 0x0000 verification")

def main():
    logger.info("🚀 CRC Byte Order Investigation")
    logger.info("=" * 60)
    
    test_crc_byte_orders()
    test_working_frames()
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 INVESTIGATION COMPLETE")
    logger.info("The correct byte order should give 0x0000 verification")

if __name__ == "__main__":
    main()
