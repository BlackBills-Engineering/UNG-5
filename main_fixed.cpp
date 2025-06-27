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
    uint8_t txNumber;  // Номер транзакции

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
        : portName(port), isConnected(false), txNumber(1) {
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
        timeouts.ReadTotalTimeoutConstant = 250;
        timeouts.ReadTotalTimeoutMultiplier = 10;
        timeouts.WriteTotalTimeoutConstant = 250;
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
        tty.c_cc[VTIME] = 5;  // Уменьшаем таймаут

        tty.c_iflag &= ~(IXON | IXOFF | IXANY);
        tty.c_cflag |= (CLOCAL | CREAD);
        tty.c_cflag &= ~(PARENB | PARODD);
        tty.c_cflag |= PARENB;  // Включить четность (ODD)
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CRTSCTS;

        if (tcsetattr(serialPort, TCSANOW, &tty) != 0) {
            std::cerr << "Ошибка установки атрибутов порта" << std::endl;
            close(serialPort);
            return false;
        }
#endif

        isConnected = true;
        // Очистка буферов
        clearBuffers();
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

    void clearBuffers() {
        if (!isConnected) return;

#ifdef _WIN32
        PurgeComm(hSerial, PURGE_RXCLEAR | PURGE_TXCLEAR);
#else
        tcflush(serialPort, TCIOFLUSH);
#endif
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

        std::cout << "Отправка: ";
        for (uint8_t byte : data) {
            std::cout << std::hex << std::uppercase << std::setw(2)
                      << std::setfill('0') << static_cast<int>(byte) << " ";
        }
        std::cout << std::dec << std::endl;

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

    std::vector<uint8_t> receiveData(size_t maxBytes = 128,
                                     int timeoutMs = 500) {
        std::vector<uint8_t> buffer;
        auto startTime = std::chrono::steady_clock::now();
        auto lastDataTime = startTime;

        if (!isConnected) return {};

        while (buffer.size() < maxBytes) {
            auto currentTime = std::chrono::steady_clock::now();
            auto totalElapsed =
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    currentTime - startTime)
                    .count();
            auto silenceElapsed =
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    currentTime - lastDataTime)
                    .count();

            // Выход по общему таймауту
            if (totalElapsed > timeoutMs) break;

            // Выход по таймауту молчания после получения данных
            if (buffer.size() > 0 && silenceElapsed > 50) break;

            uint8_t byte;
            bool dataReceived = false;

#ifdef _WIN32
            DWORD bytesRead;
            if (ReadFile(hSerial, &byte, 1, &bytesRead, NULL) &&
                bytesRead == 1) {
                dataReceived = true;
            }
#else
            ssize_t bytesRead = read(serialPort, &byte, 1);
            if (bytesRead == 1) {
                dataReceived = true;
            }
#endif

            if (dataReceived) {
                buffer.push_back(byte);
                lastDataTime = std::chrono::steady_clock::now();

                // Обнаружение валидного пакета данных
                if (buffer.size() >= 8 && buffer.back() == 0xFA) {
                    // Возможно это конец пакета, проверим структуру
                    if (buffer.size() >= 3) {
                        // Ждем немного, чтобы убедиться что данных больше нет
                        std::this_thread::sleep_for(
                            std::chrono::milliseconds(20));
                        break;
                    }
                }

                // Проверка на повторяющийся паттерн FA 50 81
                if (buffer.size() >= 9) {
                    size_t patternCount = 0;
                    for (size_t i = 0; i <= buffer.size() - 3; i += 3) {
                        if (i + 2 < buffer.size() && buffer[i] == 0xFA &&
                            buffer[i + 1] == 0x50 && buffer[i + 2] == 0x81) {
                            patternCount++;
                        } else {
                            break;
                        }
                    }

                    if (patternCount >= 3) {
                        // Найден повторяющийся паттерн
                        // Ищем начало полезных данных перед паттерном
                        size_t cutPoint = 0;
                        for (size_t i = 0; i < buffer.size() - 2; i++) {
                            if (buffer[i] == 0xFA && buffer[i + 1] == 0x50 &&
                                buffer[i + 2] == 0x81) {
                                cutPoint = i;
                                break;
                            }
                        }

                        if (cutPoint > 0) {
                            buffer.resize(cutPoint);
                        } else {
                            // Весь буфер - это паттерн, оставляем только первые
                            // 3 байта
                            buffer.resize(3);
                        }
                        break;
                    }
                }
            } else {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        }

        return buffer;
    }

    std::vector<uint8_t> createPollPacket(uint8_t address) {
        std::vector<uint8_t> packet;

        // Адрес
        packet.push_back(address);

        // Контрольный байт для POLL: Master=1, TX#=0, Control=POLL(1)
        packet.push_back(0x81);  // 10000001 = Master(1) + reserved(000) +
                                 // TX#(0000) + POLL(1)

        // Stop Flag
        packet.push_back(0xFA);

        return packet;
    }

    std::vector<uint8_t> createDataPacket(
        uint8_t address, uint8_t command, uint8_t nozzle = 1,
        const std::vector<uint8_t>& data = {}) {
        std::vector<uint8_t> packet;

        // Адрес (50h-6Fh для насосов)
        packet.push_back(address);

        // Контрольный байт: Master=1, TX#, Control=DATA(4)
        uint8_t ctrl = 0x80 | ((txNumber & 0x0F) << 4) | DATA;
        packet.push_back(ctrl);

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

        // Увеличиваем номер транзакции для следующего пакета
        txNumber = (txNumber == 0x0F) ? 1 : txNumber + 1;

        return packet;
    }

    std::vector<uint8_t> createAckPacket(uint8_t address, uint8_t txNum = 0) {
        std::vector<uint8_t> packet;

        // Адрес
        packet.push_back(address);

        // Контрольный байт для ACK: Master=1, TX#, Control=ACK(2)
        uint8_t ctrl = 0x80 | ((txNum & 0x0F) << 4) | ACK;
        packet.push_back(ctrl);

        // Stop Flag
        packet.push_back(0xFA);

        return packet;
    }

    bool sendAck(uint8_t address, uint8_t txNum = 0) {
        auto packet = createAckPacket(address, txNum);
        std::cout << "Отправка ACK для адреса 0x" << std::hex
                  << static_cast<int>(address) << std::dec << std::endl;
        return sendData(packet);
    }

    PumpStatus parseResponse(const std::vector<uint8_t>& response) {
        PumpStatus status;

        std::cout << "Анализ ответа размером " << response.size() << " байт: ";
        for (size_t i = 0; i < std::min(response.size(), size_t(20)); i++) {
            std::cout << std::hex << std::uppercase << std::setw(2)
                      << std::setfill('0') << static_cast<int>(response[i])
                      << " ";
        }
        if (response.size() > 20) {
            std::cout << "... (показаны первые 20 байт)";
        }
        std::cout << std::dec << std::endl;

        // Анализ структуры данных из вашего примера:
        // Получен: 01 5F 37 03 FA 50 81 FA...
        // Это может быть: [DATA_SIZE] [OPC] [CRC_L] [ETX] [STOP_FLAG]
        // [повторяющийся паттерн]

        if (response.size() >= 5) {
            // Проверяем, есть ли валидная структура в начале
            uint8_t firstByte = response[0];   // 01 - размер данных или адрес?
            uint8_t secondByte = response[1];  // 5F - OPC или контроль?
            uint8_t thirdByte = response[2];   // 37 - CRC_L?
            uint8_t fourthByte = response[3];  // 03 - ETX?
            uint8_t fifthByte = response[4];   // FA - Stop Flag?

            std::cout << "Разбор структуры:" << std::endl;
            std::cout << "  Байт 0: 0x" << std::hex
                      << static_cast<int>(firstByte)
                      << " (возможно размер данных: " << std::dec
                      << static_cast<int>(firstByte) << ")" << std::endl;
            std::cout << "  Байт 1: 0x" << std::hex
                      << static_cast<int>(secondByte) << std::dec << std::endl;
            std::cout << "  Байт 2: 0x" << std::hex
                      << static_cast<int>(thirdByte) << std::dec << std::endl;
            std::cout << "  Байт 3: 0x" << std::hex
                      << static_cast<int>(fourthByte);
            if (fourthByte == 0x03) std::cout << " (ETX)";
            std::cout << std::dec << std::endl;
            std::cout << "  Байт 4: 0x" << std::hex
                      << static_cast<int>(fifthByte);
            if (fifthByte == 0xFA) std::cout << " (Stop Flag)";
            std::cout << std::dec << std::endl;

            // Если это структура [SIZE][OPC][CRC][ETX][STOP]
            if (fourthByte == 0x03 && fifthByte == 0xFA) {
                std::cout << "Найдена структура: SIZE-OPC-CRC-ETX-STOP"
                          << std::endl;

                // Интерпретируем как ответ устройства
                uint8_t dataSize = firstByte;
                uint8_t opc = secondByte;

                std::cout << "  Размер данных: " << static_cast<int>(dataSize)
                          << std::endl;
                std::cout << "  OPC: 0x" << std::hex << static_cast<int>(opc)
                          << std::dec << std::endl;

                // Разбираем OPC согласно протоколу MKR5
                uint8_t responseType = (opc >> 4) & 0x0F;
                uint8_t nozzleNum = opc & 0x0F;

                std::cout << "  Тип ответа: " << static_cast<int>(responseType)
                          << std::endl;
                std::cout << "  Номер сопла: " << static_cast<int>(nozzleNum)
                          << std::endl;

                // Если есть дополнительные данные между OPC и CRC
                if (dataSize > 1) {
                    std::cout << "  Дополнительных данных нет (dataSize=1, "
                                 "только OPC)"
                              << std::endl;
                } else {
                    std::cout << "  Дополнительные данные: отсутствуют"
                              << std::endl;
                }

                // Создаем статус на основе анализа
                status.address = 0x50;  // Предполагаемый адрес
                status.isValid = true;

                // Анализируем тип ответа
                switch (responseType) {
                    case NOZZLE_STATUS:
                        status.status = IDLE;  // Базовый статус
                        status.statusDescription = "Статус сопла (из OPC)";
                        break;
                    case ERROR_CODE:
                        status.status = IDLE;
                        status.statusDescription = "Код ошибки";
                        status.errorFlag = true;
                        break;
                    default:
                        status.status = IDLE;
                        status.statusDescription = "Неизвестный тип ответа: " +
                                                   std::to_string(responseType);
                        break;
                }

                return status;
            }
        }

        // Проверка на повторяющийся паттерн FA 50 81
        if (response.size() >= 3 && response[0] == 0xFA &&
            response[1] == 0x50 && response[2] == 0x81) {
            std::cout
                << "Обнаружен паттерн FA 50 81 - poll/ack от устройства 0x50"
                << std::endl;

            status.address = 0x50;
            status.status = IDLE;
            status.statusDescription = "Устройство отвечает на POLL";
            status.isValid = true;
            return status;
        }

        // Стандартный разбор пакета (если адрес в начале)
        if (response.size() >= 3) {
            status.address = response[0];
            uint8_t ctrl = response[1];

            std::cout << "Стандартный разбор - Адрес: 0x" << std::hex
                      << static_cast<int>(status.address) << ", Контроль: 0x"
                      << static_cast<int>(ctrl) << std::dec << std::endl;

            // Проверка типа ответа
            uint8_t controlCode = ctrl & 0x0F;
            bool isMaster = (ctrl & 0x80) != 0;
            uint8_t txNum = (ctrl >> 4) & 0x0F;

            std::cout << "  Тип управления: " << static_cast<int>(controlCode)
                      << ", Master: " << (isMaster ? "да" : "нет")
                      << ", TX#: " << static_cast<int>(txNum) << std::endl;

            // Если это простой ACK, EOT или подобное
            if (response.size() == 3) {
                switch (controlCode) {
                    case ACK:
                        std::cout << "Получен ACK" << std::endl;
                        break;
                    case NACK:
                        std::cout << "Получен NACK" << std::endl;
                        break;
                    case POLL:
                        std::cout << "Получен POLL" << std::endl;
                        break;
                    default:
                        std::cout << "Получен неизвестный короткий ответ"
                                  << std::endl;
                        break;
                }

                // Для коротких ответов создаем базовый статус
                status.address = response[0];
                status.status = IDLE;
                status.statusDescription =
                    "Статус неопределен (короткий ответ)";
                status.isValid = true;
                return status;
            }

            // Для длинных пакетов с данными
            if (controlCode == DATA && response.size() >= 7) {
                size_t dataSize = response[2];
                std::cout << "Размер данных: " << static_cast<int>(dataSize)
                          << std::endl;

                if (response.size() >= 6 + dataSize) {
                    uint8_t opc = response[3];
                    uint8_t responseType = (opc >> 4) & 0x0F;
                    uint8_t nozzleNum = opc & 0x0F;

                    std::cout
                        << "Тип ответа: " << static_cast<int>(responseType)
                        << ", Сопло: " << static_cast<int>(nozzleNum)
                        << std::endl;

                    if (responseType == NOZZLE_STATUS && dataSize >= 2) {
                        uint8_t statusByte = response[4];
                        status.status = statusByte & 0x0F;
                        status.nozzleOn = (statusByte & 0x10) != 0;
                        status.rfTagSensed = (statusByte & 0x20) != 0;
                        status.errorFlag = (statusByte & 0x40) != 0;
                        status.statusDescription =
                            getStatusDescription(status.status);
                        status.isValid = true;

                        std::cout << "Статус байт: 0x" << std::hex
                                  << static_cast<int>(statusByte) << std::dec
                                  << " -> " << status.statusDescription
                                  << std::endl;
                    }
                }
            }
        }

        std::cout << "Не удалось разобрать структуру пакета" << std::endl;
        return status;
    }

    // Усовершенствованный метод для анализа сырых данных протокола
    void analyzeProtocolData(const std::vector<uint8_t>& data) {
        std::cout << "\n=== Детальный анализ протокола ===" << std::endl;

        if (data.empty()) {
            std::cout << "Нет данных для анализа" << std::endl;
            return;
        }

        std::cout << "Размер данных: " << data.size() << " байт" << std::endl;
        std::cout << "Hex данные: ";
        for (auto byte : data) {
            std::cout << std::hex << std::uppercase << std::setw(2)
                      << std::setfill('0') << static_cast<int>(byte) << " ";
        }
        std::cout << std::dec << std::endl;

        // Ищем возможные структуры пакетов
        for (size_t i = 0; i < data.size(); i++) {
            if (data[i] == 0xFA && i + 2 < data.size()) {
                std::cout << "\nНайден Stop Flag на позиции " << i << std::endl;
                std::cout << "  Следующие 2 байта: 0x" << std::hex
                          << static_cast<int>(data[i + 1]) << " 0x"
                          << static_cast<int>(data[i + 2]) << std::dec
                          << std::endl;

                if (data[i + 1] == 0x50 && data[i + 2] == 0x81) {
                    std::cout << "  -> Это POLL от устройства 0x50"
                              << std::endl;
                }
            }

            // Поиск возможных адресов устройств
            if (data[i] >= 0x50 && data[i] <= 0x6F) {
                std::cout << "\nВозможный адрес устройства на позиции " << i
                          << ": 0x" << std::hex << static_cast<int>(data[i])
                          << std::dec << std::endl;

                if (i + 1 < data.size()) {
                    uint8_t ctrl = data[i + 1];
                    uint8_t controlCode = ctrl & 0x0F;
                    bool isMaster = (ctrl & 0x80) != 0;
                    uint8_t txNum = (ctrl >> 4) & 0x0F;

                    std::cout << "  Контрольный байт: 0x" << std::hex
                              << static_cast<int>(ctrl) << std::dec
                              << std::endl;
                    std::cout << "    Master: " << (isMaster ? "да" : "нет")
                              << std::endl;
                    std::cout << "    TX#: " << static_cast<int>(txNum)
                              << std::endl;
                    std::cout << "    Код управления: "
                              << static_cast<int>(controlCode);

                    switch (controlCode) {
                        case POLL:
                            std::cout << " (POLL)";
                            break;
                        case ACK:
                            std::cout << " (ACK)";
                            break;
                        case NACK:
                            std::cout << " (NACK)";
                            break;
                        case DATA:
                            std::cout << " (DATA)";
                            break;
                        case ACKPOLL:
                            std::cout << " (ACKPOLL)";
                            break;
                        default:
                            std::cout << " (неизвестно)";
                            break;
                    }
                    std::cout << std::endl;
                }
            }
        }
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

        std::cout << "Запрос статуса насоса 0x" << std::hex << std::uppercase
                  << static_cast<int>(address) << ", сопло "
                  << static_cast<int>(nozzle) << std::dec << std::endl;

        // Очистка буферов перед отправкой
        clearBuffers();

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
        auto response = receiveData(128, 1000);

        if (response.empty()) {
            std::cerr << "Нет ответа от насоса" << std::endl;
            return PumpStatus();
        }

        return parseResponse(response);
    }

    bool pollPump(uint8_t address) {
        if (!isConnected) return false;

        std::cout << "Опрос насоса 0x" << std::hex << static_cast<int>(address)
                  << std::dec << std::endl;

        // Очистка буферов
        clearBuffers();

        auto packet = createPollPacket(address);

        if (!sendData(packet)) {
            return false;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(50));

        auto response = receiveData(10, 300);  // Короткий таймаут для poll

        if (!response.empty()) {
            std::cout << "Ответ на POLL: ";
            for (uint8_t byte : response) {
                std::cout << std::hex << std::uppercase << std::setw(2)
                          << std::setfill('0') << static_cast<int>(byte) << " ";
            }
            std::cout << std::dec << std::endl;
            return true;
        }

        return false;
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

            // Сначала попробуем простой опрос
            if (pollPump(addr)) {
                std::cout << "Устройство найдено на адресе 0x" << std::hex
                          << static_cast<int>(addr) << std::dec << std::endl;

                // Получаем статус
                auto status = getPumpStatus(addr);
                printPumpStatus(status);
            } else {
                std::cout << "Нет ответа от адреса 0x" << std::hex
                          << static_cast<int>(addr) << std::dec << std::endl;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
    }

    // Метод для тестирования конкретного адреса с разными подходами
    void testAddress(uint8_t address) {
        std::cout << "\n=== Детальное тестирование адреса 0x" << std::hex
                  << static_cast<int>(address) << std::dec
                  << " ===" << std::endl;

        // 1. Простой POLL
        std::cout << "\n1. Тест POLL:" << std::endl;
        clearBuffers();
        bool pollResult = pollPump(address);
        std::cout << "Результат POLL: " << (pollResult ? "Успех" : "Неудача")
                  << std::endl;

        std::this_thread::sleep_for(std::chrono::milliseconds(300));

        // 2. Запрос статуса с детальным анализом
        std::cout << "\n2. Тест запроса статуса с детальным анализом:"
                  << std::endl;
        clearBuffers();

        auto packet = createDataPacket(address, RETURN_STATUS, 1);
        if (sendData(packet)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(150));

            auto response = receiveData(128, 1000);
            if (!response.empty()) {
                std::cout << "Полученный ответ:" << std::endl;
                analyzeProtocolData(response);

                // Пробуем стандартный разбор
                auto status = parseResponse(response);
                printPumpStatus(status);

                // Если получили данные, отправляем ACK
                if (response.size() >= 5) {
                    std::cout << "\nОтправляем ACK..." << std::endl;
                    sendAck(address, 1);
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));

                    // Проверяем дополнительные данные
                    auto extraData = receiveData(64, 300);
                    if (!extraData.empty()) {
                        std::cout << "Дополнительные данные после ACK:"
                                  << std::endl;
                        analyzeProtocolData(extraData);
                    }
                }
            } else {
                std::cout << "Нет ответа на запрос статуса" << std::endl;
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(300));

        // 3. Тест других команд
        std::cout << "\n3. Тест команды получения информации о заправке:"
                  << std::endl;
        clearBuffers();
        auto fillingPacket = createDataPacket(address, RETURN_FILLING_INFO, 1);
        if (sendData(fillingPacket)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(150));
            auto response = receiveData(128, 500);
            if (!response.empty()) {
                std::cout << "Ответ на запрос информации о заправке:"
                          << std::endl;
                analyzeProtocolData(response);
            } else {
                std::cout << "Нет ответа на запрос информации о заправке"
                          << std::endl;
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(300));

        // 4. Осторожно тестируем сброс
        std::cout << "\n4. Тест команды сброса (осторожно!):" << std::endl;
        clearBuffers();
        auto resetPacket = createDataPacket(address, RESET_NOZZLE, 1);
        if (sendData(resetPacket)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            auto response = receiveData(128, 500);
            if (!response.empty()) {
                std::cout << "Ответ на сброс:" << std::endl;
                analyzeProtocolData(response);
            } else {
                std::cout << "Нет ответа на сброс" << std::endl;
            }
        }

        std::cout << "\n=== Тестирование завершено ===" << std::endl;
    }
};

int main() {
    std::cout << "=== Исправленный контроллер MKR5 для проверки статуса ТРК ==="
              << std::endl;

    // Настройка порта (измените на ваш порт)
#ifdef _WIN32
    std::string port = "COM1";
#else
    std::string port = "/dev/ttyS4";  // или /dev/ttyS0
#endif

    MKR5Controller controller(port);

    if (!controller.connect()) {
        std::cerr << "Не удалось подключиться к порту " << port << std::endl;
        return 1;
    }

    try {
        // Детальный тест одного адреса
        std::cout << "\n=== Детальный тест адреса 0x50 ===" << std::endl;
        controller.testAddress(0x50);

        // Быстрое сканирование (раскомментируйте если нужно)
        /*
        std::cout << "\n=== Быстрое сканирование ===" << std::endl;
        controller.scanAllPumps();
        */

    } catch (const std::exception& e) {
        std::cerr << "Ошибка: " << e.what() << std::endl;
    }

    controller.disconnect();
    return 0;
}
