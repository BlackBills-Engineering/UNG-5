import serial
import time

PORT = "/dev/ttyS4"

def crc16_ccitt(data, crc=0x0000):
    """Вычисляет CRC16-CCITT для данных"""
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if (crc & 0x8000) else (crc << 1)
        crc &= 0xFFFF  # Ограничиваем до 16 бит
    return crc

def main():
    # Настройка serial порта
    port = serial.Serial(
        port=PORT,
        baudrate=9600,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1.0
    )
    
    # Подготовка данных
    data = [0x01, 0x01, 0x00]
    
    # Создание frame
    frame = [0x52, 0x00]
    frame.extend(data)
    
    # Вычисление и добавление CRC
    crc = crc16_ccitt(frame)
    frame.append(crc & 0xFF)        # младший байт
    frame.append((crc >> 8) & 0xFF) # старший байт
    
    # Добавление завершающих байтов
    frame.extend([0x03, 0xFA])
    
    # Сохранение frame в файл для проверки (опционально)
    # with open("frame_output.bin", "wb") as file:
    #     file.write(bytes(frame))
    #     print("Frame saved to frame_output.bin")
    
    # Отправка данных
    frame_bytes = bytes(frame)
    tmp = port.write(frame_bytes)
    
    # Вывод отправленных данных
    print("Sent:", " ".join(f"{b:02X}" for b in frame))
    
    # Чтение ответа (если нужно)
    # response = port.read(64)
    # if response:
    #     print(f"Received ({len(response)} bytes):", " ".join(f"{b:02X}" for b in response))
    
    port.close()

if __name__ == "__main__":
    main()