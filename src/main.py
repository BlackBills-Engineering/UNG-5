from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Optional
import logging
import os
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global protocol_instance
    
    # Startup
    logger.info("Starting MKR5 Pump Control API")
    logger.info(f"Configured COM port: {COM_PORT}")
    logger.info(f"Configured baud rate: {BAUD_RATE}")
    
    # Initialize with real COM port
    protocol_instance = MKR5Protocol(port=COM_PORT, baud_rate=BAUD_RATE)
    
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
        log_level="info"
    )
