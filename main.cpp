#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#include "types.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#endif

class MKR5Controller {
   private:
#ifdef _WIN32
    HANDLE hSerial;
#else
    int serialPort;
#endif

    std::string portName;
    bool isConnected;

    // Коды команд MKR5
    enum MasterCommands {
        RETURN_STATUS = 0x00,
        RESET_NOZZLE = 0x01,
        AUTHORIZE_NOZZLE = 0x02,
        PAUSE_DELIVERY = 0x03,
        RESUME_DELIVERY = 0x04,
        RETURN_FILLING_INFO = 0x05,
        RETURN_TOTALIZER = 0x06,
        PRICE_UPDATE = 0x07,
        PRESET_AMOUNT = 0x08,
        PRESET_VOLUME = 0x09
    };

    // Коды ответов от насоса
    enum SlaveResponses {
        NOZZLE_STATUS = 0x00,
        ERROR_CODE = 0x01,
        FILLING_INFO = 0x02,
        TOTALIZER = 0x03
    };

    // Статусы насоса
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

    // Коды управления
    enum ControlCodes {
        POLL = 0x01,
        ACK = 0x02,
        NACK = 0x03,
        DATA = 0x04,
        ACKPOLL = 0x05
    };

   public:
    struct PumpStatus {
        uint8_t address;
        uint8_t status;
        bool nozzleOn;
        bool rfTagSensed;
        bool errorFlag;
        std::string statusDescription;
        bool isValid;

        PumpStatus()
            : address(0),
              status(0),
              nozzleOn(false),
              rfTagSensed(false),
              errorFlag(false),
              isValid(false) {}
    };

    struct FillingInfo {
        uint32_t amount;
        uint32_t volume;
        bool isValid;

        FillingInfo() : amount(0), volume(0), isValid(false) {}
    };

    MKR5Controller(const std::string& port)
        : portName(port), isConnected(false) {
#ifdef _WIN32
        hSerial = INVALID_HANDLE_VALUE;
#else
        serialPort = -1;
#endif
    }

    ~MKR5Controller() { disconnect(); }

    bool connect() {
#ifdef _WIN32
        hSerial = CreateFileA(portName.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                              0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);

        if (hSerial == INVALID_HANDLE_VALUE) {
            std::cerr << "Ошибка открытия порта: " << portName << std::endl;
            return false;
        }

        DCB dcbSerialParams = {0};
        dcbSerialParams.DCBlength = sizeof(dcbSerialParams);

        if (!GetCommState(hSerial, &dcbSerialParams)) {
            std::cerr << "Ошибка получения параметров порта" << std::endl;
            CloseHandle(hSerial);
            return false;
        }

        dcbSerialParams.BaudRate = CBR_9600;
        dcbSerialParams.ByteSize = 8;
        dcbSerialParams.StopBits = ONESTOPBIT;
        dcbSerialParams.Parity = ODDPARITY;

        if (!SetCommState(hSerial, &dcbSerialParams)) {
            std::cerr << "Ошибка установки параметров порта" << std::endl;
            CloseHandle(hSerial);
            return false;
        }

        COMMTIMEOUTS timeouts = {0};
        timeouts.ReadIntervalTimeout = 50;
        timeouts.ReadTotalTimeoutConstant = 1000;
        timeouts.ReadTotalTimeoutMultiplier = 10;
        timeouts.WriteTotalTimeoutConstant = 1000;
        timeouts.WriteTotalTimeoutMultiplier = 10;

        if (!SetCommTimeouts(hSerial, &timeouts)) {
            std::cerr << "Ошибка установки таймаутов" << std::endl;
            CloseHandle(hSerial);
            return false;
        }

#else
        serialPort = open(portName.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
        if (serialPort < 0) {
            std::cerr << "Ошибка открытия порта: " << portName << std::endl;
            return false;
        }

        struct termios tty;
        if (tcgetattr(serialPort, &tty) != 0) {
            std::cerr << "Ошибка получения атрибутов порта" << std::endl;
            close(serialPort);
            return false;
        }

        // Настройка порта
        cfsetospeed(&tty, B9600);
        cfsetispeed(&tty, B9600);

        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
        tty.c_iflag &= ~IGNBRK;
        tty.c_lflag = 0;
        tty.c_oflag = 0;
        tty.c_cc[VMIN] = 0;
        tty.c_cc[VTIME] = 10;

        tty.c_iflag &= ~(IXON | IXOFF | IXANY);
        tty.c_cflag |= (CLOCAL | CREAD);
        tty.c_cflag &= ~(PARENB | PARODD);
        tty.c_cflag |= PARENB;  // Включить четность
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CRTSCTS;

        if (tcsetattr(serialPort, TCSANOW, &tty) != 0) {
            std::cerr << "Ошибка установки атрибутов порта" << std::endl;
            close(serialPort);
            return false;
        }
#endif

        isConnected = true;
        std::cout << "Подключение к порту " << portName << " установлено"
                  << std::endl;
        return true;
    }

    void disconnect() {
        if (isConnected) {
#ifdef _WIN32
            if (hSerial != INVALID_HANDLE_VALUE) {
                CloseHandle(hSerial);
                hSerial = INVALID_HANDLE_VALUE;
            }
#else
            if (serialPort >= 0) {
                close(serialPort);
                serialPort = -1;
            }
#endif
            isConnected = false;
            std::cout << "Соединение закрыто" << std::endl;
        }
    }

    uint16_t calculateCRC16(const std::vector<uint8_t>& data) {
        uint16_t crc = 0x0000;

        for (uint8_t byte : data) {
            crc ^= byte;
            for (int i = 0; i < 8; i++) {
                if (crc & 0x0001) {
                    crc = (crc >> 1) ^ 0x8408;  // Полином CCITT
                } else {
                    crc >>= 1;
                }
            }
        }

        return crc;
    }

    bool sendData(const std::vector<uint8_t>& data) {
        if (!isConnected) return false;

#ifdef _WIN32
        DWORD bytesWritten;
        if (!WriteFile(hSerial, data.data(), data.size(), &bytesWritten,
                       NULL)) {
            return false;
        }
        return bytesWritten == data.size();
#else
        ssize_t bytesWritten = write(serialPort, data.data(), data.size());
        return bytesWritten == static_cast<ssize_t>(data.size());
#endif
    }

    std::vector<uint8_t> receiveData(size_t maxBytes = 128) {
        std::vector<uint8_t> buffer(maxBytes);

        if (!isConnected) return {};

#ifdef _WIN32
        DWORD bytesRead;
        if (!ReadFile(hSerial, buffer.data(), maxBytes, &bytesRead, NULL)) {
            return {};
        }
        buffer.resize(bytesRead);
#else
        ssize_t bytesRead = read(serialPort, buffer.data(), maxBytes);
        if (bytesRead < 0) return {};
        buffer.resize(bytesRead);
#endif

        return buffer;
    }

    std::vector<uint8_t> createDataPacket(
        uint8_t address, uint8_t command, uint8_t nozzle = 1,
        const std::vector<uint8_t>& data = {}) {
        std::vector<uint8_t> packet;

        // Адрес (50h-6Fh для насосов)
        packet.push_back(address);

        // Контрольный байт (DATA = 0x04, TX# = 1)
        packet.push_back(0x14);  // DATA (0x04) + TX# (0x01) << 4

        // Размер данных
        uint8_t dataSize = 1 + data.size();  // OPC + data
        packet.push_back(dataSize);

        // Код операции (команда + номер сопла)
        uint8_t opc = (command << 4) | (nozzle & 0x0F);
        packet.push_back(opc);

        // Дополнительные данные
        for (uint8_t byte : data) {
            packet.push_back(byte);
        }

        // Вычисление CRC от адреса до последнего байта данных
        std::vector<uint8_t> crcData(packet.begin(), packet.end());
        uint16_t crc = calculateCRC16(crcData);

        // Добавление CRC (младший, старший байт)
        packet.push_back(crc & 0xFF);
        packet.push_back((crc >> 8) & 0xFF);

        // ETX (End of Text)
        packet.push_back(0x03);

        // Stop Flag
        packet.push_back(0xFA);

        return packet;
    }

    std::vector<uint8_t> createPollPacket(uint8_t address) {
        std::vector<uint8_t> packet;

        // Адрес
        packet.push_back(address);

        // Контрольный байт для POLL (0x01)
        packet.push_back(0x01);

        // Stop Flag
        packet.push_back(0xFA);

        return packet;
    }

    PumpStatus parseStatusResponse(const std::vector<uint8_t>& response) {
        PumpStatus status;

        if (response.size() < 7) {  // Минимальный размер ответа
            return status;
        }

        // Проверка структуры пакета
        if (response.back() != 0xFA) {  // Stop Flag
            return status;
        }

        status.address = response[0];
        uint8_t ctrl = response[1];

        // Проверка, что это DATA ответ
        if ((ctrl & 0x0F) != DATA) {
            return status;
        }

        size_t dataSize = response[2];
        if (response.size() < 6 + dataSize) {
            return status;
        }

        uint8_t opc = response[3];

        // Проверка, что это статус сопла
        if ((opc >> 4) != NOZZLE_STATUS) {
            return status;
        }

        // Проверка CRC
        std::vector<uint8_t> crcData(response.begin(), response.end() - 3);
        uint16_t calculatedCRC = calculateCRC16(crcData);
        uint16_t receivedCRC = response[response.size() - 3] |
                               (response[response.size() - 2] << 8);

        if (calculatedCRC !=
            0x0000) {  // После включения CRC результат должен быть 0
            return status;
        }

        // Извлечение статуса
        if (dataSize >= 2) {
            uint8_t statusByte = response[4];
            status.status = statusByte & 0x0F;
            status.nozzleOn = (statusByte & 0x10) != 0;
            status.rfTagSensed = (statusByte & 0x20) != 0;
            status.errorFlag = (statusByte & 0x40) != 0;
            status.statusDescription = getStatusDescription(status.status);
            status.isValid = true;
        }

        return status;
    }

    std::string getStatusDescription(uint8_t status) {
        static std::map<uint8_t, std::string> statusMap = {
            {IDLE, "Простой"},
            {READY_FOR_DELIVERY, "Готов к заправке"},
            {RESETED, "Сброшен"},
            {AUTHORIZED, "Авторизован"},
            {DELIVERY_FILLING, "Заправка"},
            {PAUSED, "Приостановлен"},
            {NOZZLE_DISABLED, "Сопло отключено"},
            {NOZZLE_STOPPED, "Сопло остановлено"},
            {NOT_PROGRAMMED, "Не запрограммирован"}};

        auto it = statusMap.find(status);
        return (it != statusMap.end()) ? it->second : "Неизвестный статус";
    }

    PumpStatus getPumpStatus(uint8_t address, uint8_t nozzle = 1) {
        if (!isConnected) {
            std::cerr << "Нет соединения с портом" << std::endl;
            return PumpStatus();
        }

        std::cout << "Запрос статуса насоса " << std::hex << std::uppercase
                  << static_cast<int>(address) << ", сопло "
                  << static_cast<int>(nozzle) << std::dec << std::endl;

        // Создание пакета запроса статуса
        auto packet = createDataPacket(address, RETURN_STATUS, nozzle);

        // Отправка запроса
        if (!sendData(packet)) {
            std::cerr << "Ошибка отправки запроса" << std::endl;
            return PumpStatus();
        }

        // Ожидание ответа
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

        // Получение ответа
        auto response = receiveData();

        if (response.empty()) {
            std::cerr << "Нет ответа от насоса" << std::endl;
            return PumpStatus();
        }

        // Вывод сырых данных для отладки
        std::cout << "Получен ответ: ";
        for (uint8_t byte : response) {
            std::cout << std::hex << std::uppercase << std::setw(2)
                      << std::setfill('0') << static_cast<int>(byte) << " ";
        }
        std::cout << std::dec << std::endl;

        return parseStatusResponse(response);
    }

    bool pollPump(uint8_t address) {
        if (!isConnected) return false;

        auto packet = createPollPacket(address);

        if (!sendData(packet)) {
            return false;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(50));

        auto response = receiveData();
        return !response.empty();
    }

    void printPumpStatus(const PumpStatus& status) {
        if (!status.isValid) {
            std::cout << "Статус недействителен или не получен" << std::endl;
            return;
        }

        std::cout << "\n=== Статус насоса ===" << std::endl;
        std::cout << "Адрес: 0x" << std::hex << std::uppercase
                  << static_cast<int>(status.address) << std::dec << std::endl;
        std::cout << "Статус: " << status.statusDescription << " (0x"
                  << std::hex << static_cast<int>(status.status) << std::dec
                  << ")" << std::endl;
        std::cout << "Сопло: " << (status.nozzleOn ? "Включено" : "Выключено")
                  << std::endl;
        std::cout << "RF-метка: "
                  << (status.rfTagSensed ? "Обнаружена" : "Не обнаружена")
                  << std::endl;
        std::cout << "Ошибка: " << (status.errorFlag ? "Есть" : "Нет")
                  << std::endl;
    }

    void scanAllPumps() {
        std::cout << "\n=== Сканирование всех насосов (0x50-0x6F) ==="
                  << std::endl;

        for (uint8_t addr = 0x50; addr <= 0x6F; addr++) {
            std::cout << "\nПроверка адреса 0x" << std::hex << std::uppercase
                      << static_cast<int>(addr) << std::dec << "..."
                      << std::endl;

            // Сначала попробуем опрос
            if (pollPump(addr)) {
                std::cout << "Насос найден на адресе 0x" << std::hex
                          << static_cast<int>(addr) << std::dec << std::endl;

                // Получаем статус
                auto status = getPumpStatus(addr);
                printPumpStatus(status);
            } else {
                std::cout << "Нет ответа от адреса 0x" << std::hex
                          << static_cast<int>(addr) << std::dec << std::endl;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
};

int main() {
    std::cout << "=== Контроллер MKR5 для проверки статуса ТРК ==="
              << std::endl;

// Настройка порта (измените на ваш порт)
#ifdef _WIN32
    std::string port = "COM1";
#else
    std::string port = "/dev/ttyS4";
#endif

    MKR5Controller controller(port);

    if (!controller.connect()) {
        std::cerr << "Не удалось подключиться к порту " << port << std::endl;
        return 1;
    }

    try {
        // Проверка конкретного насоса
        std::cout << "\n1. Проверка статуса насоса 0x50:" << std::endl;
        auto status = controller.getPumpStatus(0x50, 1);
        controller.printPumpStatus(status);

        // Сканирование всех возможных адресов
        std::cout << "\n2. Сканирование всех насосов:" << std::endl;
        controller.scanAllPumps();

        // Циклический опрос (раскомментируйте для непрерывного мониторинга)
        /*
        std::cout << "\n3. Циклический мониторинг (Ctrl+C для остановки):" <<
        std::endl; while (true) { auto status = controller.getPumpStatus(0x50,
        1); if (status.isValid) { std::cout << "Статус: " <<
        status.statusDescription; if (status.errorFlag) std::cout << "
        (ОШИБКА!)"; std::cout << std::endl;
            }
            std::this_thread::sleep_for(std::chrono::seconds(2));
        }
        */

    } catch (const std::exception& e) {
        std::cerr << "Ошибка: " << e.what() << std::endl;
    }

    controller.disconnect();
    return 0;
}