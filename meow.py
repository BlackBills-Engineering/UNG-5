import serial
import time

PORT = "/dev/ttyS4"

def crc16_ccitt(data, crc=0x0000):
    """Вычисляет CRC16-CCITT для данных"""
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if (crc & 0x8000) else (crc << 1)
        crc &= 0xFFFF  
    return crc

def foo(port, data):
    frame = [0x52, 0x00]
    frame.extend(data)
    
    crc = crc16_ccitt(frame)
    frame.append(crc & 0xFF)        
    frame.append((crc >> 8) & 0xFF) 
    
    frame.extend([0x03, 0xFA])
    
    frame_bytes = bytes(frame)
    port.write(frame_bytes)
    port.flush()
    
    time.sleep(1)
    
    bytes_available = port.in_waiting
    print(f"Bytes available: {bytes_available}")
    
    if bytes_available > 0:
        response = port.read(bytes_available)
    else:
        response = port.read(64)  
        
    if response:
        print(f"Received ({len(response)} bytes):", " ".join(f"{b:02X}" for b in response))
        if len(response) >= 2:
            print(f"Response header: {response[0]:02X} {response[1]:02X}")
    else:
        print("No response received within timeout")
  
    print("Sent:", " ".join(f"{b:02X}" for b in frame))

def main(): 
    port = serial.Serial(
        port=PORT,
        baudrate=9600,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1.0
    )
    
    print("=== Test 1 ===")
    response1 = foo(port, [0x01, 0x01, 0x00])
    
    print("\n=== Test 2 ===")
    response2 = foo(port, [0x02, 0x03, 0x04])
    
    print("\n=== Test 3 ===")
    response3 = foo(port, [0xFF, 0x00, 0xFF])

if __name__ == "__main__":
    main()