from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel


class PumpStatus(Enum):
    """Pump status enumeration based on MKR5 protocol"""
    PUMP_NOT_PROGRAMMED = 0
    RESET = 1
    AUTHORIZED = 2
    FILLING = 4
    FILLING_COMPLETED = 5
    MAX_AMOUNT_VOLUME_REACHED = 6
    SWITCHED_OFF = 7


class PumpCommand(Enum):
    """Pump commands based on MKR5 protocol"""
    RETURN_STATUS = 0x00
    RETURN_PUMP_PARAMETERS = 0x02
    RETURN_PUMP_IDENTITY = 0x03
    RETURN_FILLING_INFORMATION = 0x04
    RESET = 0x05
    AUTHORIZE = 0x06
    STOP = 0x08
    SWITCH_OFF = 0x0A


class NozzleInfo(BaseModel):
    """Nozzle information model"""
    nozzle_number: int
    is_out: bool  # True if nozzle is out, False if in
    filling_price: Optional[float] = None


class PumpInfo(BaseModel):
    """Pump information model"""
    address: int
    status: PumpStatus
    identity: Optional[str] = None
    nozzles: List[NozzleInfo] = []
    filled_volume: Optional[float] = None
    filled_amount: Optional[float] = None
    is_online: bool = True
    error_message: Optional[str] = None


class ScanPumpsResponse(BaseModel):
    """Response model for scan pumps operation"""
    success: bool
    total_pumps_found: int
    pumps: List[PumpInfo]
    scan_range: Dict[str, Any]
    message: str


class ApiResponse(BaseModel):
    """Generic API response model"""
    success: bool
    message: str
    data: Optional[Any] = None
