# MKR5 Pump Control API

A Python REST API service for controlling and monitoring MKR5 protocol fuel pumps based on the DART Pump Interface specification.

## Features

- **Pump Scanning**: Automatically discover all pumps on the network (addresses 0x50-0x6F)
- **Status Monitoring**: Get real-time status of individual pumps
- **Protocol Implementation**: Full MKR5 protocol support with proper CRC validation
- **Swagger Documentation**: Interactive API documentation
- **Simulation Mode**: Test without hardware for development

## Protocol Support

Based on MKR5 Protocol Specification - DART PUMP INTERFACE:

- **Address Range**: 0x50-0x6F (80-111 decimal)
- **Max Pumps**: 32
- **Communication**: Serial RS-485/Current Loop
- **Baud Rates**: 9600/19200 bps
- **Error Checking**: CRC-16 CCITT + Parity

### Supported Pump Commands

- `RETURN_STATUS` - Get pump status and nozzle information
- `RETURN_PUMP_IDENTITY` - Get pump identity (10-digit ID)
- `RETURN_FILLING_INFORMATION` - Get filling data
- `RESET` - Reset pump display and counters
- `AUTHORIZE` - Authorize pump for filling
- `STOP` - Stop current filling operation
- `SWITCH_OFF` - Switch off pump

### Pump Status Types

- `PUMP_NOT_PROGRAMMED` (0)
- `RESET` (1)
- `AUTHORIZED` (2)
- `FILLING` (4)
- `FILLING_COMPLETED` (5)
- `MAX_AMOUNT_VOLUME_REACHED` (6)
- `SWITCHED_OFF` (7)

## Installation and Configuration

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure COM Port**:
   Edit the `.env` file to set your COM port:
   ```
   COM_PORT=COM3
   BAUD_RATE=9600
   ```
   
   **Common COM Port Names:**
   - **Windows**: COM1, COM2, COM3, COM4, etc.
   - **Linux**: /dev/ttyUSB0, /dev/ttyS0, /dev/ttyAMA0, etc.
   - **macOS**: /dev/tty.usbserial-*, /dev/cu.usbserial-*, etc.

3. **Test Your Connection** (Important!):
   Before running the API, test your connection with the included COM port tester:
   ```bash
   python test_comport_simple.py
   ```
   
   This interactive tool will:
   - List all available COM ports on your system
   - Test basic connectivity to your selected port
   - Scan for MKR5 pumps using the actual protocol
   - Verify communication and display pump responses
   - Provide configuration suggestions
   
   **Command Line Usage:**
   ```bash
   # Test specific port and baud rate
   python test_comport_simple.py COM3 9600
   python test_comport_simple.py /dev/ttyUSB0 19200
   ```

4. **Run the Server**:
   ```bash
   python run_server.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Hardware Setup

### Connection Requirements

- **Interface**: RS-485 or Current Loop (20mA)
- **Voltage**: 24V DC ±5%
- **Current**: 45mA ±5%
- **Cable**: Twisted pair, max 400 meters
- **Baud Rate**: 9600 or 19200 bps
- **Data Format**: 8 data bits, 1 stop bit, odd parity

### COM Port Setup

1. **Connect Hardware**: Connect your RS-485/Serial adapter to the pump network
2. **Identify Port**: Check Device Manager (Windows) or `ls /dev/tty*` (Linux/macOS) to find your COM port
3. **Test Connection**: Use the health check endpoint to verify connection
4. **Scan Pumps**: Use the scan endpoint to discover connected pumps

## Usage

### Web Interface

Open your browser and go to:
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc
- **Main Page**: http://localhost:8000/

### API Endpoints

#### Scan All Pumps
```bash
GET /pumps/scan
```

**Response**:
```json
{
  "success": true,
  "total_pumps_found": 5,
  "pumps": [
    {
      "address": 80,
      "status": "RESET",
      "identity": "1234010001",
      "nozzles": [
        {
          "nozzle_number": 1,
          "is_out": false,
          "filling_price": 1.45
        }
      ],
      "filled_volume": null,
      "filled_amount": null,
      "is_online": true,
      "error_message": null
    }
  ],
  "scan_range": {
    "min_address": 80,
    "max_address": 111,
    "min_address_hex": "0x50",
    "max_address_hex": "0x6F"
  },
  "message": "Scan completed successfully. Found 5 pump(s)."
}
```

#### Get Pump Status
```bash
GET /pumps/{pump_address}/status
```

Examples:
- `GET /pumps/50/status` (hex)
- `GET /pumps/0x50/status` (hex with prefix)
- `GET /pumps/80/status` (decimal)

#### Health Check
```bash
GET /health
```

### Switch Off Command

```bash
POST /pumps/{pump_address}/switch-off
```

The SWITCH_OFF command turns off the pump according to MKR5 protocol:
- **Purpose**: Used when station is closing or if there is an error in the pump
- **Action**: Turns off the pump light and motor
- **Result**: Pump transitions to `SWITCHED_OFF` status (code 7)

Example:
```bash
curl -X POST http://localhost:8000/pumps/50/switch-off
```

Response:
```json
{
  "success": true,
  "message": "SWITCH_OFF command sent to pump 0x50",
  "data": {
    "command": "SWITCH_OFF",
    "pump_address": "0x50",
    "command_response": {"acknowledged": true},
    "new_status": 7,
    "status_name": "SWITCHED_OFF"
  }
}
```

**Important Notes:**
- A pump in `SWITCHED_OFF` status can only be reactivated using:
  - `RESET` command (transitions to `RESET` status)
  - `STOP` command (transitions to `FILLING_COMPLETED` status)
- The pump remains responsive to commands but motor and light are off
- This is different from a communication failure - the pump is still connected

## Configuration

### Configuration Options

You can configure the API by editing the `.env` file:

```env
# Serial Port Configuration
COM_PORT=COM3                    # Your COM port
BAUD_RATE=9600                   # Communication speed (9600 or 19200)
RESPONSE_TIMEOUT=0.1             # Timeout for pump responses (seconds)
LOG_LEVEL=INFO                   # Logging level (DEBUG, INFO, WARNING, ERROR)
```

Alternatively, set environment variables:
```bash
export COM_PORT=COM3
export BAUD_RATE=9600
python run_server.py
```

## Project Structure

```
UNG-5/
├── src/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── models.py        # Pydantic data models
│   └── protocol.py      # MKR5 protocol implementation
├── docs.txt             # Protocol specification
├── requirements.txt     # Python dependencies
├── run_server.py        # Server startup script
└── README.md           # This file
```

## Development

### Adding New Pump Commands

1. Add the command to `PumpCommand` enum in `models.py`
2. Implement the command logic in `protocol.py`
3. Add a new API endpoint in `main.py`

Example structure for new endpoints:
```python
@app.post("/pumps/{pump_address}/authorize")
async def authorize_pump(pump_address: str, protocol: MKR5Protocol = Depends(get_protocol)):
    # Implementation here
    pass
```

### Testing

1. **Check Connection**: First verify your COM port connection:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Scan for Pumps**: Discover all connected pumps:
   ```bash
   curl http://localhost:8000/pumps/scan
   ```

3. **Get Pump Status**: Check individual pump status:
   ```bash
   curl http://localhost:8000/pumps/50/status
   ```

## Hardware Requirements

- **Serial Interface**: RS-485 or Current Loop (20mA)
- **Voltage**: 24V DC ±5%
- **Current**: 45mA ±5%
- **Cable Length**: Up to 400 meters
- **Explosion Proof**: Equipment must meet hazardous area standards

## Troubleshooting

### COM Port Issues

1. **"Access is denied" or "Permission denied"**:
   - Close any other programs using the COM port
   - Run as administrator/sudo
   - Check if port is in use by another application

2. **"Port not found" or "Cannot find port"**:
   - Verify port name in Device Manager (Windows) or `ls /dev/tty*` (Linux/macOS)
   - Check if USB-to-Serial adapter drivers are installed
   - Try unplugging and reconnecting the device

3. **Port opens but no pump responses**:
   - Use `python test_comport_simple.py` to diagnose
   - Check power supply to pumps (24V DC)
   - Verify wiring: TX↔RX, RX↔TX, GND↔GND
   - Try different baud rates (9600 vs 19200)
   - Check if RS-485 termination resistors are needed

### Protocol Issues

1. **"No pumps found"**:
   - Verify pump addresses are in range 0x50-0x6F (80-111 decimal)
   - Check that pumps are powered on and operational
   - Ensure proper RS-485 or current loop connections
   - Test with COM port tester first

2. **"CRC Errors"**:
   - Check cable integrity and connections
   - Verify electrical specifications (impedance, termination)
   - Reduce cable length if possible
   - Check for electrical interference

3. **Connection timeout**:
   - Increase timeout values in configuration
   - Check baud rate settings
   - Verify hardware handshaking requirements

### Using the COM Port Tester

The `test_comport_simple.py` utility is your best friend for debugging:

```bash
# Interactive mode - recommended for first-time setup
python test_comport_simple.py

# Quick test of specific port
python test_comport_simple.py COM3 9600
python test_comport_simple.py /dev/ttyUSB0 19200
```

The tester will:
- Show all available ports with details
- Test basic port connectivity
- Send actual MKR5 protocol commands
- Display raw responses from pumps
- Provide specific troubleshooting advice

### Common Issues

1. **Import Errors**: Install dependencies with `pip install -r requirements.txt`
2. **Serial Port Access**: Ensure proper permissions (Linux: add user to `dialout` group)
3. **No Pumps Found**: Check serial connection, baud rate, and pump addresses
4. **CRC Errors**: Verify cable integrity and electrical connections

### Logging

The API provides detailed logging. Check console output for:
- Connection status
- Pump scan results
- Communication errors
- Protocol messages

## License

This project implements the MKR5 Protocol Specification - DART PUMP INTERFACE for educational and development purposes.

## Future Enhancements

- [ ] Add more pump control commands (authorize, reset, stop, etc.)
- [ ] Implement preset volume/amount functionality
- [ ] Add price update capabilities
- [ ] Real-time pump monitoring with WebSocket
- [ ] Database integration for logging
- [ ] Authentication and authorization
- [ ] Multiple serial port support
