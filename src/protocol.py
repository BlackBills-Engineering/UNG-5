import struct
import time
from typing import List, Optional, Tuple
import serial
import logging
from .models import PumpInfo, PumpStatus, NozzleInfo, PumpCommand

logger = logging.getLogger(__name__)


class MKR5Protocol:
    """
    MKR5 Protocol implementation for communication with fuel pumps
    Based on MKR5 Protocol Specification - DART PUMP INTERFACE
    """
    
    # Protocol constants
    MIN_PUMP_ADDRESS = 0x50  # 50H
    MAX_PUMP_ADDRESS = 0x6F  # 6FH
    MAX_PUMPS = 32
    
    # Communication settings
    BAUD_RATE = 19200  # Can be 19200 for shorter distances
    DATA_BITS = 8
    STOP_BITS = 1
    PARITY = serial.PARITY_ODD
    TIMEOUT = 0.1  # 100ms timeout
    
    # Message structure constants
    ETX = 0x03  # End of text
    SF = 0xFA   # Stop flag
    
    # Transaction codes
    CD1_COMMAND = 0x01  # Command to pump
    DC1_PUMP_STATUS = 0x01  # Pump status response
    DC2_FILLED_INFO = 0x02  # Filled volume and amount
    DC3_NOZZLE_STATUS = 0x03  # Nozzle status and filling price
    DC9_PUMP_IDENTITY = 0x09  # Pump identity
    
    def __init__(self, port: str, baud_rate: int = 9600, parity: str = serial.PARITY_ODD):
        """
        Initialize MKR5 Protocol handler
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0', 'COM1', 'COM3')
            baud_rate: Communication baud rate (9600 or 19200)
            parity: Parity setting (serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.parity = parity
        self.serial_conn = None
        
    def connect(self) -> bool:
        """
        Establish serial connection to pump network
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=self.DATA_BITS,
                stopbits=self.STOP_BITS,
                parity=self.parity,
                timeout=self.TIMEOUT
            )
            logger.info(f"Connected to {self.port} at {self.baud_rate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Serial connection closed")
    
    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculate CRC-16 CCITT checksum
        
        Args:
            data: Bytes to calculate CRC for
            
        Returns:
            int: CRC-16 value
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
    
    def create_command_message(self, address: int, command: PumpCommand) -> bytes:
        """
        Create a command message according to MKR5 protocol
        
        Args:
            address: Pump address (0x50-0x6F)
            command: Command to send
            
        Returns:
            bytes: Complete message packet
        """
        # Control byte (master, TX#=1)
        ctrl = 0x81  # 10000001 - Master bit set, TX#=1
        
        # Transaction CD1 (Command to pump)
        trans = self.CD1_COMMAND
        lng = 0x01  # Length of data
        dcc = command.value  # Command code
        
        # Build message without CRC
        message_data = bytes([address, ctrl, trans, lng, dcc])
        
        # Calculate CRC
        crc = self.calculate_crc16(message_data)
        crc_l = crc & 0xFF
        crc_h = (crc >> 8) & 0xFF
        
        # Complete message
        message = message_data + bytes([crc_l, crc_h, self.ETX, self.SF])
        
        return message
    
    def parse_pump_response(self, data: bytes) -> Optional[dict]:
        """
        Parse pump response message
        
        Args:
            data: Raw response data
            
        Returns:
            dict: Parsed response data or None if invalid
        """
        if len(data) < 8:  # Minimum message length
            return None
            
        try:
            # Basic message structure: ADR CTRL TRANS LNG DATA... CRC-L CRC-H ETX SF
            address = data[0]
            ctrl = data[1]
            trans = data[2]
            lng = data[3]
            
            # Verify message integrity
            if data[-2] != self.ETX or data[-1] != self.SF:
                return None
                
            # Extract data portion
            data_start = 4
            data_end = 4 + lng
            message_data = data[:data_end]
            
            # Verify CRC
            expected_crc = self.calculate_crc16(message_data)
            received_crc = (data[data_end + 1] << 8) | data[data_end]
            
            if expected_crc != received_crc:
                logger.warning(f"CRC mismatch for pump {address:02X}")
                return None
            
            response = {
                'address': address,
                'transaction': trans,
                'data_length': lng,
                'raw_data': data[data_start:data_end]
            }
            
            # Parse specific transaction types
            if trans == self.DC1_PUMP_STATUS and lng >= 1:
                response['status'] = data[data_start]
            elif trans == self.DC2_FILLED_INFO and lng >= 8:
                # VOL (4 bytes) + AMO (4 bytes) - both in packed BCD
                vol_bcd = data[data_start:data_start+4]
                amo_bcd = data[data_start+4:data_start+8]
                response['filled_volume'] = self.bcd_to_decimal(vol_bcd) / 1000.0  # Convert to liters
                response['filled_amount'] = self.bcd_to_decimal(amo_bcd) / 100.0   # Convert to currency units
            elif trans == self.DC3_NOZZLE_STATUS and lng >= 4:
                # PRI (3 bytes) + NOZIO (1 byte)
                price_bcd = data[data_start:data_start+3]
                nozio = data[data_start+3]
                response['filling_price'] = self.bcd_to_decimal(price_bcd) / 1000.0
                response['nozzle_number'] = nozio & 0x0F
                response['nozzle_out'] = bool(nozio & 0x10)
            elif trans == self.DC9_PUMP_IDENTITY and lng >= 5:
                identity_bcd = data[data_start:data_start+5]
                response['identity'] = self.bcd_to_string(identity_bcd)
                
            return response
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None
    
    def bcd_to_decimal(self, bcd_data: bytes) -> int:
        """Convert packed BCD to decimal"""
        result = 0
        for byte in bcd_data:
            result = result * 100 + ((byte >> 4) * 10) + (byte & 0x0F)
        return result
    
    def bcd_to_string(self, bcd_data: bytes) -> str:
        """Convert packed BCD to string"""
        result = ""
        for byte in bcd_data:
            result += f"{(byte >> 4):01d}{(byte & 0x0F):01d}"
        return result
    
    def decimal_to_bcd(self, value: float, total_bytes: int = 3) -> bytes:
        """Convert decimal price to packed BCD format"""
        int_value = int(value * 1000)  # Prices stored in thousandths
        bcd_bytes = []
        for _ in range(total_bytes):
            byte_val = (int_value % 100)
            bcd_byte = ((byte_val // 10) << 4) | (byte_val % 10)
            bcd_bytes.insert(0, bcd_byte)
            int_value //= 100
        return bytes(bcd_bytes)

    def create_price_update_message(self, address: int, prices: List[Tuple[int, float]]) -> bytes:
        """Create a price update message (CD5 transaction)"""
        ctrl = 0x81  # Master bit set, TX#=1
        trans = 0x05  # CD5 transaction
        lng = 3 * len(prices)  # 3 bytes per price
        
        # Build price data - 3 bytes per price in packed BCD
        price_data = b''
        for nozzle_num, price in sorted(prices):
            price_bcd = self.decimal_to_bcd(price, 3)
            price_data += price_bcd
        
        # Build message without CRC
        message_data = bytes([address, ctrl, trans, lng]) + price_data
        
        # Calculate CRC
        crc = self.calculate_crc16(message_data)
        crc_l = crc & 0xFF
        crc_h = (crc >> 8) & 0xFF
        
        # Complete message
        message = message_data + bytes([crc_l, crc_h, self.ETX, self.SF])
        return message

    def send_price_update(self, address: int, prices: List[Tuple[int, float]], timeout: float = None) -> Optional[dict]:
        """Send price update command to pump"""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Serial connection not established")
            return None
            
        if not prices:
            logger.error("No prices provided for update")
            return None
            
        timeout = timeout or 0.5  # Use longer timeout for price updates (500ms)
        
        try:
            # Clear input buffer first
            self.serial_conn.reset_input_buffer()
            
            # Small delay to ensure pump is ready for price update
            time.sleep(0.05)  # 50ms delay before sending
            
            message = self.create_price_update_message(address, prices)
            self.log_frame_details(message, "TX", address, "command PRICE_UPDATE")
            
            # Send message
            bytes_written = self.serial_conn.write(message)
            logger.info(f"   ✅ Sent {bytes_written} bytes successfully")
            
            # Wait for response using proper polling like send_command
            start_time = time.time()
            response_data = b''
            
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    response_data += self.serial_conn.read(self.serial_conn.in_waiting)
                    
                    # Check if we have a complete message
                    if len(response_data) >= 2 and response_data[-2:] == bytes([self.ETX, self.SF]):
                        break
                        
                time.sleep(0.001)  # Small delay to avoid busy waiting
            
            if response_data:
                self.log_frame_details(response_data, "RX", address, "response")
                parsed_response = self.parse_pump_response(response_data)
                
                if parsed_response:
                    logger.info("   ✅ Response parsed successfully")
                    logger.debug(f"   Parsed data: {parsed_response}")
                    return parsed_response
                else:
                    logger.warning("   ❌ Failed to parse response")
                    return None
            else:
                logger.warning(f"📭 No response from pump 0x{address:02X} after {timeout}s timeout")
                return None
                
        except Exception as e:
            logger.error(f"Error sending price update to pump 0x{address:02X}: {e}")
            return None
    
    def send_command(self, address: int, command: PumpCommand, timeout: float = None) -> Optional[dict]:
        """
        Send command to pump and wait for response
        
        Args:
            address: Pump address
            command: Command to send
            timeout: Response timeout in seconds (uses default if None)
            
        Returns:
            dict: Response data or None if no response/error
        """
        if timeout is None:
            timeout = self.TIMEOUT
            
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Serial connection not established")
            return None
            
        try:
            # Clear input buffer
            self.serial_conn.reset_input_buffer()
            
            # Create and send command
            message = self.create_command_message(address, command)
            
            # Log detailed frame information
            self.log_frame_details(message, "TX", address, f"command {command.name}")
            
            # Send the message
            bytes_written = self.serial_conn.write(message)
            logger.info(f"   ✅ Sent {bytes_written} bytes successfully")
            
            # Wait for response
            start_time = time.time()
            response_data = b''
            
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    response_data += self.serial_conn.read(self.serial_conn.in_waiting)
                    
                    # Check if we have a complete message
                    if len(response_data) >= 2 and response_data[-2:] == bytes([self.ETX, self.SF]):
                        break
                        
                time.sleep(0.001)  # Small delay to avoid busy waiting
            
            if response_data:
                self.log_frame_details(response_data, "RX", address, "response")
                
                parsed_response = self.parse_pump_response(response_data)
                if parsed_response:
                    logger.info(f"   ✅ Response parsed successfully")
                    logger.debug(f"   Parsed data: {parsed_response}")
                else:
                    logger.warning(f"   ⚠️ Failed to parse response")
                
                return parsed_response
            else:
                logger.warning(f"📭 No response from pump 0x{address:02X} after {timeout:.1f}s timeout")
                
        except Exception as e:
            logger.error(f"Error communicating with pump {address:02X}: {e}")
            
        return None
    
    def scan_pumps(self) -> List[PumpInfo]:
        """
        Scan all possible pump addresses and return available pumps
        
        Returns:
            List[PumpInfo]: List of found pumps with their information
        """
        found_pumps = []
        
        logger.info(f"Scanning pump addresses {self.MIN_PUMP_ADDRESS:02X}-{self.MAX_PUMP_ADDRESS:02X}")
        
        for address in range(self.MIN_PUMP_ADDRESS, self.MAX_PUMP_ADDRESS + 1):
            try:
                # Send RETURN_STATUS command
                response = self.send_command(address, PumpCommand.RETURN_STATUS)
                
                if response:
                    # Pump responded, get additional info
                    pump_info = PumpInfo(
                        address=address,
                        status=PumpStatus(response.get('status', 0)),
                        is_online=True
                    )
                    
                    # Try to get pump identity
                    identity_response = self.send_command(address, PumpCommand.RETURN_PUMP_IDENTITY)
                    if identity_response and 'identity' in identity_response:
                        pump_info.identity = identity_response['identity']
                    
                    # Add nozzle information if available
                    if 'nozzle_number' in response:
                        nozzle = NozzleInfo(
                            nozzle_number=response['nozzle_number'],
                            is_out=response.get('nozzle_out', False),
                            filling_price=response.get('filling_price')
                        )
                        pump_info.nozzles = [nozzle]
                    
                    found_pumps.append(pump_info)
                    logger.info(f"Found pump at address {address:02X}, status: {pump_info.status.name}")
                
            except Exception as e:
                logger.error(f"Error scanning pump {address:02X}: {e}")
                continue
        
        logger.info(f"Scan complete. Found {len(found_pumps)} pumps")
        return found_pumps
    
    def log_frame_details(self, frame: bytes, direction: str, address: int, description: str = ""):
        """
        Log detailed frame information in a readable format
        
        Args:
            frame: Raw frame bytes
            direction: "TX" for sent, "RX" for received
            address: Pump address
            description: Additional description
        """
        arrow = "📤" if direction == "TX" else "📥"
        action = "Sending to" if direction == "TX" else "Received from"
        
        logger.info(f"{arrow} {action} pump 0x{address:02X}{f' ({description})' if description else ''}:")
        logger.info(f"   Raw frame: {frame.hex()}")
        logger.info(f"   Formatted: {' '.join(f'{b:02x}' for b in frame)}")
        logger.info(f"   Length: {len(frame)} bytes")
        
        # Parse frame structure
        if len(frame) >= 4:
            logger.debug(f"   Frame structure:")
            logger.debug(f"     ADR: 0x{frame[0]:02X} ({'pump address'})")
            logger.debug(f"     CTRL: 0x{frame[1]:02X} ({'master' if frame[1] & 0x80 else 'slave'}, TX#={(frame[1] & 0x0F)})")
            logger.debug(f"     TRANS: 0x{frame[2]:02X} ({'transaction type'})")
            
            if len(frame) > 3:
                data_len = frame[3]
                logger.debug(f"     LNG: 0x{data_len:02X} ({data_len} bytes of data)")
                
                # Show data bytes
                if len(frame) > 4 and data_len > 0:
                    data_end = min(4 + data_len, len(frame))
                    data_bytes = frame[4:data_end]
                    logger.debug(f"     DATA: {' '.join(f'0x{b:02X}' for b in data_bytes)}")
                
                # Show CRC and terminators
                if len(frame) >= 4 + data_len + 4:
                    crc_start = 4 + data_len
                    logger.debug(f"     CRC: 0x{frame[crc_start]:02X}{frame[crc_start+1]:02X}")
                    logger.debug(f"     ETX: 0x{frame[crc_start+2]:02X}")
                    logger.debug(f"     SF: 0x{frame[crc_start+3]:02X}")
    
    def get_filling_information(self, address: int) -> Optional[dict]:
        """
        Get filling information from pump (last successful filling)
        
        Args:
            address: Pump address
            
        Returns:
            dict: Filling information with volume and amount, or None if failed
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Serial connection not established")
            return None
            
        try:
            logger.info(f"Getting filling information from pump 0x{address:02X}")
            
            # Send RETURN_FILLING_INFORMATION command
            response = self.send_command(address, PumpCommand.RETURN_FILLING_INFORMATION)
            
            if response and response.get('transaction') == self.DC2_FILLED_INFO:
                filling_info = {
                    'pump_address': address,
                    'filled_volume': response.get('filled_volume', 0.0),
                    'filled_amount': response.get('filled_amount', 0.0)
                }
                
                # The command may also trigger nozzle status response (DC3)
                # Try to get additional nozzle information
                time.sleep(0.05)  # Small delay for potential second response
                
                if self.serial_conn.in_waiting > 0:
                    additional_data = b''
                    start_time = time.time()
                    
                    while time.time() - start_time < 0.1:  # 100ms timeout
                        if self.serial_conn.in_waiting > 0:
                            additional_data += self.serial_conn.read(self.serial_conn.in_waiting)
                            
                            if len(additional_data) >= 2 and additional_data[-2:] == bytes([self.ETX, self.SF]):
                                break
                                
                        time.sleep(0.001)
                    
                    if additional_data:
                        self.log_frame_details(additional_data, "RX", address, "additional nozzle info")
                        additional_response = self.parse_pump_response(additional_data)
                        
                        if additional_response and additional_response.get('transaction') == self.DC3_NOZZLE_STATUS:
                            filling_info['nozzle_number'] = additional_response.get('nozzle_number')
                            filling_info['is_nozzle_out'] = additional_response.get('nozzle_out')
                            filling_info['filling_price'] = additional_response.get('filling_price')
                
                return filling_info
            else:
                logger.warning(f"Invalid or no filling information response from pump 0x{address:02X}")
                
        except Exception as e:
            logger.error(f"Error getting filling information from pump {address:02X}: {e}")
            
        return None
