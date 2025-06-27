#ifndef MKR5_PROTOCOL_H
#define MKR5_PROTOCOL_H

#include <cstdint>
#include <string>
#include <vector>

namespace MKR5 {
// Константы протокола
const uint8_t PUMP_ADDRESS_MIN = 0x50;
const uint8_t PUMP_ADDRESS_MAX = 0x6F;
const uint8_t STOP_FLAG = 0xFA;
const uint8_t ETX = 0x03;

// Команды мастера
enum MasterCommand {
    RETURN_STATUS = 0x00,
    RESET_NOZZLE = 0x01,
    AUTHORIZE_NOZZLE = 0x02,
    PAUSE_DELIVERY = 0x03,
    RESUME_DELIVERY = 0x04,
    RETURN_FILLING_INFO = 0x05,
    RETURN_TOTALIZER = 0x06,
    PRICE_UPDATE = 0x07,
    PRESET_AMOUNT = 0x08,
    PRESET_VOLUME = 0x09,
    DISABLE_NOZZLE = 0x0A,
    STOP_NOZZLE = 0x0B
};

// Коды управления
enum ControlCode {
    POLL = 0x01,
    ACK = 0x02,
    NACK = 0x03,
    DATA = 0x04,
    ACKPOLL = 0x05
};

// Статусы сопла
enum NozzleStatus {
    IDLE = 0x00,
    READY_FOR_DELIVERY = 0x01,
    RESETED = 0x02,
    AUTHORIZED = 0x03,
    DELIVERY_FILLING = 0x04,
    PAUSED = 0x05,
    NOZZLE_DISABLED = 0x06,
    NOZZLE_STOPPED = 0x07,
    NOT_PROGRAMMED = 0x08
};

// Структура статуса насоса
struct PumpStatusInfo {
    uint8_t address;
    uint8_t nozzleNumber;
    NozzleStatus status;
    bool nozzleOn;
    bool rfTagSensed;
    bool errorFlag;
    uint32_t amount;  // Для информации о заправке
    uint32_t volume;  // Для информации о заправке
    uint32_t price;   // Цена за единицу
    bool isValid;

    PumpStatusInfo()
        : address(0),
          nozzleNumber(0),
          status(IDLE),
          nozzleOn(false),
          rfTagSensed(false),
          errorFlag(false),
          amount(0),
          volume(0),
          price(0),
          isValid(false) {}
};

// Функции для работы с BCD
inline uint32_t bcdToDecimal(const std::vector<uint8_t>& bcd) {
    uint32_t result = 0;
    uint32_t multiplier = 1;

    for (int i = bcd.size() - 1; i >= 0; i--) {
        uint8_t byte = bcd[i];
        result += ((byte & 0x0F) * multiplier);
        multiplier *= 10;
        result += (((byte >> 4) & 0x0F) * multiplier);
        multiplier *= 10;
    }

    return result;
}

inline std::vector<uint8_t> decimalToBcd(uint32_t value, size_t bytes) {
    std::vector<uint8_t> result(bytes, 0);

    for (size_t i = 0; i < bytes; i++) {
        uint8_t lowNibble = value % 10;
        value /= 10;
        uint8_t highNibble = value % 10;
        value /= 10;

        result[bytes - 1 - i] = (highNibble << 4) | lowNibble;
    }

    return result;
}
}  // namespace MKR5

#endif  // MKR5_PROTOCOL_H