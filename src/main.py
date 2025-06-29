from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Optional
import logging
import os
import serial
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .models import ScanPumpsResponse, ApiResponse, PumpInfo
from .protocol import MKR5Protocol

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

# Global protocol instance
protocol_instance: Optional[MKR5Protocol] = None

# Configuration - Load from environment variables
COM_PORT = os.getenv("COM_PORT", "COM3")
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))
RESPONSE_TIMEOUT = float(os.getenv("RESPONSE_TIMEOUT", "0.1"))

# Parity configuration
def get_parity_setting() -> str:
    """Convert parity string to serial constant"""
    parity_str = os.getenv("PARITY", "NONE").upper()
    parity_map = {
        "NONE": serial.PARITY_NONE,
        "EVEN": serial.PARITY_EVEN, 
        "ODD": serial.PARITY_ODD
    }
    return parity_map.get(parity_str, serial.PARITY_NONE)

PARITY = get_parity_setting()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global protocol_instance
    
    # Startup
    logger.info("Starting MKR5 Pump Control API")
    logger.info(f"Configured COM port: {COM_PORT}")
    logger.info(f"Configured baud rate: {BAUD_RATE}")
    logger.info(f"Configured parity: {os.getenv('PARITY', 'NONE')}")
    
    # Initialize with real COM port
    protocol_instance = MKR5Protocol(port=COM_PORT, baud_rate=BAUD_RATE, parity=PARITY)
    
    if protocol_instance.connect():
        logger.info(f"Successfully connected to {COM_PORT}")
    else:
        logger.error(f"Failed to connect to {COM_PORT} - API will not function properly")
        # Don't exit, let the API start but endpoints will return errors
    
    yield
    
    # Shutdown
    if protocol_instance:
        protocol_instance.disconnect()
        logger.info("Serial connection closed")


app = FastAPI(
    title="MKR5 Pump Control API",
    description="REST API for controlling and monitoring MKR5 protocol fuel pumps",
    version="1.0.0",
    lifespan=lifespan
)


def get_protocol() -> MKR5Protocol:
    """Dependency to get protocol instance"""
    if protocol_instance is None:
        raise HTTPException(status_code=500, detail="Protocol not initialized")
    return protocol_instance


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API documentation"""
    return """
    <html>
        <head>
            <title>MKR5 Pump Control API</title>
        </head>
        <body>
            <h1>MKR5 Pump Control API</h1>
            <p>REST API for controlling and monitoring MKR5 protocol fuel pumps.</p>
            <h2>Available Endpoints:</h2>
            <ul>
                <li><a href="/docs">Swagger UI Documentation</a></li>
                <li><a href="/redoc">ReDoc Documentation</a></li>
                <li><a href="/pumps/scan">Scan All Pumps</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
            
            <h2>Pump Control Endpoints:</h2>
            <ul>
                <li><strong>GET</strong> /pumps/scan - Scan all pumps</li>
                <li><strong>GET</strong> /pumps/{address}/status - Get pump status</li>
                <li><strong>POST</strong> /pumps/{address}/switch-off - Switch off pump</li>
            </ul>
            
            <h2>Protocol Information:</h2>
            <p><strong>Protocol:</strong> MKR5 DART Pump Interface</p>
            <p><strong>Address Range:</strong> 0x50 - 0x6F (80-111 decimal)</p>
            <p><strong>Max Pumps:</strong> 32</p>
            <p><strong>Communication:</strong> Serial RS-485/Current Loop</p>
            <p><strong>COM Port:</strong> """ + COM_PORT + """</p>
            <p><strong>Baud Rate:</strong> """ + str(BAUD_RATE) + """</p>
        </body>
    </html>
    """


@app.get("/health", response_model=ApiResponse)
async def health_check(protocol: MKR5Protocol = Depends(get_protocol)):
    """Health check endpoint"""
    is_connected = protocol.serial_conn and protocol.serial_conn.is_open if protocol.serial_conn else False
    
    return ApiResponse(
        success=is_connected,
        message="API is running" if is_connected else "API running but serial connection failed",
        data={
            "serial_connected": is_connected,
            "port": protocol.port,
            "baud_rate": protocol.baud_rate
        }
    )


@app.get("/pumps/scan", response_model=ScanPumpsResponse)
async def scan_pumps(protocol: MKR5Protocol = Depends(get_protocol)):
    """
    Scan all pump addresses (0x50-0x6F) and return available pumps
    
    This endpoint sends RETURN_STATUS commands to all possible pump addresses
    and returns information about responsive pumps including their status,
    identity, and nozzle information.
    
    Returns:
        ScanPumpsResponse: Scan results with found pumps
    """
    # Check if serial connection is available
    if not protocol.serial_conn or not protocol.serial_conn.is_open:
        raise HTTPException(
            status_code=503,
            detail=f"Serial connection to {protocol.port} is not available. Check COM port connection."
        )
    
    try:
        logger.info("Starting pump scan...")
        found_pumps = protocol.scan_pumps()
        
        return ScanPumpsResponse(
            success=True,
            total_pumps_found=len(found_pumps),
            pumps=found_pumps,
            scan_range={
                "min_address": protocol.MIN_PUMP_ADDRESS,
                "max_address": protocol.MAX_PUMP_ADDRESS,
                "min_address_hex": f"0x{protocol.MIN_PUMP_ADDRESS:02X}",
                "max_address_hex": f"0x{protocol.MAX_PUMP_ADDRESS:02X}"
            },
            message=f"Scan completed successfully. Found {len(found_pumps)} pump(s)."
        )
        
    except Exception as e:
        logger.error(f"Error during pump scan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scan pumps: {str(e)}"
        )


@app.get("/pumps/{pump_address}/status", response_model=ApiResponse)
async def get_pump_status(
    pump_address: str,
    protocol: MKR5Protocol = Depends(get_protocol)
):
    """
    Get status of a specific pump
    
    Args:
        pump_address: Pump address in hex format (e.g., '50', '0x50') or decimal
    
    Returns:
        ApiResponse: Pump status information
    """
    try:
        # Parse address (support both hex and decimal)
        if pump_address.startswith('0x') or pump_address.startswith('0X'):
            address = int(pump_address, 16)
        elif pump_address.lower().endswith('h'):
            address = int(pump_address[:-1], 16)
        else:
            # Try decimal first, then hex
            try:
                address = int(pump_address, 10)  # Try decimal first
            except ValueError:
                try:
                    address = int(pump_address, 16)  # Then try hex
                except ValueError:
                    raise ValueError(f"Invalid address format: {pump_address}")
        
        # Validate address range
        if not (protocol.MIN_PUMP_ADDRESS <= address <= protocol.MAX_PUMP_ADDRESS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pump address. Must be between 0x{protocol.MIN_PUMP_ADDRESS:02X} and 0x{protocol.MAX_PUMP_ADDRESS:02X}"
            )
        
        # Check if serial connection is available
        if not protocol.serial_conn or not protocol.serial_conn.is_open:
            raise HTTPException(
                status_code=503,
                detail=f"Serial connection to {protocol.port} is not available. Check COM port connection."
            )
        
        from .protocol import PumpCommand
        response = protocol.send_command(address, PumpCommand.RETURN_STATUS)
        
        if response is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pump at address 0x{address:02X} is not responding"
            )
        
        return ApiResponse(
            success=True,
            message=f"Status retrieved for pump 0x{address:02X}",
            data=response
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid address format: {pump_address}. Error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error getting pump status: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pump status: {error_msg}"
        )


@app.post("/pumps/{pump_address}/switch-off", response_model=ApiResponse)
async def switch_off_pump(
    pump_address: str,
    protocol: MKR5Protocol = Depends(get_protocol)
):
    """
    Switch off a specific pump
    
    This command switches off the pump. The light and pump motor are turned off.
    Used when the station is closing or if there is an error in the pump.
    
    Args:
        pump_address: Pump address in hex format (e.g., '50', '0x50') or decimal
    
    Returns:
        ApiResponse: Command execution result
    """
    try:
        # Parse address (support both hex and decimal)
        if pump_address.startswith('0x') or pump_address.startswith('0X'):
            address = int(pump_address, 16)
        elif pump_address.lower().endswith('h'):
            address = int(pump_address[:-1], 16)
        else:
            # Try decimal first, then hex
            try:
                address = int(pump_address, 10)  # Try decimal first
            except ValueError:
                try:
                    address = int(pump_address, 16)  # Then try hex
                except ValueError:
                    raise ValueError(f"Invalid address format: {pump_address}")
        
        # Validate address range
        if not (protocol.MIN_PUMP_ADDRESS <= address <= protocol.MAX_PUMP_ADDRESS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pump address. Must be between 0x{protocol.MIN_PUMP_ADDRESS:02X} and 0x{protocol.MAX_PUMP_ADDRESS:02X}"
            )
        
        # Check if serial connection is available
        if not protocol.serial_conn or not protocol.serial_conn.is_open:
            raise HTTPException(
                status_code=503,
                detail="Serial connection not available. Check COM port configuration."
            )
        
        from .protocol import PumpCommand
        
        # Send SWITCH_OFF command
        logger.info(f"Sending SWITCH_OFF command to pump 0x{address:02X}")
        response = protocol.send_command(address, PumpCommand.SWITCH_OFF, timeout=1.0)
        
        if response is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pump at address 0x{address:02X} is not responding"
            )
        
        # Get updated status to confirm command was executed
        status_response = protocol.send_command(address, PumpCommand.RETURN_STATUS, timeout=1.0)
        
        result_data = {
            "command": "SWITCH_OFF",
            "pump_address": f"0x{address:02X}",
            "command_response": response,
        }
        
        if status_response:
            result_data["new_status"] = status_response.get('status', 'unknown')
            result_data["status_name"] = get_status_name(status_response.get('status', 0))
        
        return ApiResponse(
            success=True,
            message=f"SWITCH_OFF command sent to pump 0x{address:02X}",
            data=result_data
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid address format: {pump_address}. Error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error switching off pump: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch off pump: {error_msg}"
        )


@app.get("/pumps/{pump_address}/filling-info", response_model=ApiResponse)
async def get_pump_filling_info(
    pump_address: str,
    protocol: MKR5Protocol = Depends(get_protocol)
):
    """
    Get last successful filling information from a specific pump
    
    Returns the filled volume and amount from the last completed filling operation.
    This command sends RETURN_FILLING_INFORMATION to the pump which triggers
    the pump to send transaction DC2 (filled volume and amount) and potentially
    DC3 (nozzle status and filling price).
    
    Args:
        pump_address: Pump address in hex format (e.g., '50', '0x50') or decimal
    
    Returns:
        ApiResponse: Filling information including volume, amount, and nozzle details
    """
    try:
        # Parse address (support both hex and decimal)
        if pump_address.startswith('0x') or pump_address.startswith('0X'):
            address = int(pump_address, 16)
        elif pump_address.lower().endswith('h'):
            address = int(pump_address[:-1], 16)
        else:
            # Try decimal first, then hex
            try:
                address = int(pump_address, 10)  # Try decimal first
            except ValueError:
                try:
                    address = int(pump_address, 16)  # Then try hex
                except ValueError:
                    raise ValueError(f"Invalid address format: {pump_address}")
        
        # Validate address range
        if not (protocol.MIN_PUMP_ADDRESS <= address <= protocol.MAX_PUMP_ADDRESS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pump address. Must be between 0x{protocol.MIN_PUMP_ADDRESS:02X} and 0x{protocol.MAX_PUMP_ADDRESS:02X}"
            )
        
        # Check if serial connection is available
        if not protocol.serial_conn or not protocol.serial_conn.is_open:
            raise HTTPException(
                status_code=503,
                detail="Serial connection not available. Check COM port configuration."
            )
        
        # Get filling information
        logger.info(f"Getting filling information from pump 0x{address:02X}")
        filling_info = protocol.get_filling_information(address)
        
        if filling_info is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pump at address 0x{address:02X} is not responding or has no filling information"
            )
        
        return ApiResponse(
            success=True,
            message=f"Filling information retrieved from pump 0x{address:02X}",
            data=filling_info
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid address format: {pump_address}. Error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error getting filling information: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get filling information: {error_msg}"
        )


def get_status_name(status_code: int) -> str:
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


@app.post("/pumps/{pump_address}/price-update", response_model=ApiResponse)
async def update_pump_prices(
    pump_address: str,
    price_update: dict,
    protocol: MKR5Protocol = Depends(get_protocol)
):
    """
    Update prices for a specific pump
    
    This command updates the filling prices for all nozzles on the pump.
    A pump in PUMP_NOT_PROGRAMMED state requires a price update to become operational.
    
    Args:
        pump_address: Pump address in hex format (e.g., '50', '0x50') or decimal
        price_update: Dictionary with "prices" list containing {"nozzle_number": int, "price": float}
    
    Returns:
        ApiResponse: Command execution result
    """
    try:
        # Parse address
        if pump_address.startswith('0x') or pump_address.startswith('0X'):
            address = int(pump_address, 16)
        elif pump_address.lower().endswith('h'):
            address = int(pump_address[:-1], 16)
        else:
            try:
                address = int(pump_address, 10)
            except ValueError:
                try:
                    address = int(pump_address, 16)
                except ValueError:
                    raise ValueError(f"Invalid address format: {pump_address}")
        
        # Validate address range
        if not (protocol.MIN_PUMP_ADDRESS <= address <= protocol.MAX_PUMP_ADDRESS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pump address. Must be between 0x{protocol.MIN_PUMP_ADDRESS:02X} and 0x{protocol.MAX_PUMP_ADDRESS:02X}"
            )
        
        # Check if serial connection is available
        if not protocol.serial_conn or not protocol.serial_conn.is_open:
            raise HTTPException(
                status_code=503,
                detail="Serial connection not available. Check COM port configuration."
            )
        
        # Validate price update data
        if 'prices' not in price_update:
            raise HTTPException(
                status_code=400,
                detail="Missing 'prices' field in request body"
            )
        
        prices_list = price_update['prices']
        if not isinstance(prices_list, list) or len(prices_list) == 0:
            raise HTTPException(
                status_code=400,
                detail="'prices' must be a non-empty list"
            )
        
        # Convert to format expected by protocol
        price_tuples = []
        for price_info in prices_list:
            if not isinstance(price_info, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Each price entry must be an object with 'nozzle_number' and 'price' fields"
                )
            
            if 'nozzle_number' not in price_info or 'price' not in price_info:
                raise HTTPException(
                    status_code=400,
                    detail="Each price entry must have 'nozzle_number' and 'price' fields"
                )
            
            nozzle_num = int(price_info['nozzle_number'])
            price = float(price_info['price'])
            
            if nozzle_num < 1 or nozzle_num > 8:
                raise HTTPException(
                    status_code=400,
                    detail=f"Nozzle number must be between 1 and 8, got {nozzle_num}"
                )
            
            if price < 0 or price > 999.99:
                raise HTTPException(
                    status_code=400,
                    detail=f"Price must be between 0 and 999.99, got {price}"
                )
            
            price_tuples.append((nozzle_num, price))
        
        # Import PumpCommand
        from .protocol import PumpCommand
        
        # Send price update command
        logger.info(f"Sending PRICE_UPDATE command to pump 0x{address:02X} with {len(price_tuples)} prices")
        response = protocol.send_price_update(address, price_tuples, timeout=1.0)
        
        if response is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pump at address 0x{address:02X} is not responding to price update"
            )
        
        # Get updated status to confirm command was executed
        status_response = protocol.send_command(address, PumpCommand.RETURN_STATUS, timeout=1.0)
        
        result_data = {
            "command": "PRICE_UPDATE",
            "pump_address": f"0x{address:02X}",
            "prices_updated": price_tuples,
            "command_response": response,
        }
        
        if status_response:
            result_data["new_status"] = status_response.get('status', 'unknown')
            result_data["status_name"] = get_status_name(status_response.get('status', 0))
        
        return ApiResponse(
            success=True,
            message=f"PRICE_UPDATE command sent to pump 0x{address:02X} with {len(price_tuples)} prices",
            data=result_data
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating prices for pump {pump_address}: {str(e)}")
        return ApiResponse(
            success=False,
            message=f"Error updating prices: {str(e)}"
        )


@app.post("/pumps/{pump_address}/dummy-price-update", response_model=ApiResponse)
async def dummy_price_update(
    pump_address: str,
    nozzle_count: int,
    protocol: MKR5Protocol = Depends(get_protocol)
):
    """
    Send dummy price update to a pump (for testing)
    
    This is a simplified price update that sets the same price (1000.00) 
    for the specified number of nozzles (1, 2, 3, etc.).
    Useful for testing pumps in PUMP_NOT_PROGRAMMED state.
    
    Args:
        pump_address: Pump address in hex format (e.g., '50', '0x50') or decimal
        nozzle_count: Number of nozzles to update (1-8)
    
    Returns:
        ApiResponse: Command execution result
    """
    try:
        # Parse address
        if pump_address.startswith('0x') or pump_address.startswith('0X'):
            address = int(pump_address, 16)
        elif pump_address.lower().endswith('h'):
            address = int(pump_address[:-1], 16)
        else:
            try:
                address = int(pump_address, 10)
            except ValueError:
                try:
                    address = int(pump_address, 16)
                except ValueError:
                    raise ValueError(f"Invalid address format: {pump_address}")
        
        # Validate address range
        if not (protocol.MIN_PUMP_ADDRESS <= address <= protocol.MAX_PUMP_ADDRESS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pump address. Must be between 0x{protocol.MIN_PUMP_ADDRESS:02X} and 0x{protocol.MAX_PUMP_ADDRESS:02X}"
            )
        
        # Validate nozzle count
        if not isinstance(nozzle_count, int) or nozzle_count < 1 or nozzle_count > 8:
            raise HTTPException(
                status_code=400,
                detail="nozzle_count must be an integer between 1 and 8"
            )
        
        # Check if serial connection is available
        if not protocol.serial_conn or not protocol.serial_conn.is_open:
            raise HTTPException(
                status_code=503,
                detail="Serial connection not available. Check COM port configuration."
            )
        
        # Create price tuples for nozzles 1 through nozzle_count
        dummy_price = 15.50  # 1000 soums
        price_tuples = []
        for nozzle_num in range(1, nozzle_count + 1):
            price_tuples.append((nozzle_num, dummy_price))
        
        # Import PumpCommand
        from .protocol import PumpCommand
        
        # Send price update command
        logger.info(f"Sending DUMMY PRICE_UPDATE command to pump 0x{address:02X} with {nozzle_count} nozzles at {dummy_price} soums each")
        response = protocol.send_price_update(address, price_tuples, timeout=1.0)
        
        if response is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pump at address 0x{address:02X} is not responding to price update"
            )
        
        # Get updated status to confirm command was executed
        status_response = protocol.send_command(address, PumpCommand.RETURN_STATUS, timeout=1.0)
        
        result_data = {
            "command": "DUMMY_PRICE_UPDATE",
            "pump_address": f"0x{address:02X}",
            "nozzle_count": nozzle_count,
            "price_per_nozzle": dummy_price,
            "prices_sent": price_tuples,
            "command_response": response,
        }
        
        if status_response:
            result_data["new_status"] = status_response.get('status', 'unknown')
            result_data["status_name"] = get_status_name(status_response.get('status', 0))
        
        return ApiResponse(
            success=True,
            message=f"DUMMY_PRICE_UPDATE sent to pump 0x{address:02X} for {nozzle_count} nozzle(s) at {dummy_price} soums each",
            data=result_data
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Error sending dummy price update to pump {pump_address}: {str(e)}")
        return ApiResponse(
            success=False,
            message=f"Error sending dummy price update: {str(e)}"
        )


# Additional endpoints can be added here for other pump operations:
# - authorize_pump()
# - reset_pump()
# - stop_pump()
# - set_preset_amount()
# - set_preset_volume()
# - update_prices()
# etc.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
