#include <iostream>
#include <map>
#include <string>
#include <vector>

#include "helper.cpp"
#include "serial/serial.h"

using namespace std;

const string PORT_STRING = "/dev/ttys004";

uint16_t crc16_ccitt(const vector<uint8_t>& data, uint16_t crc = 0x0000) {
    for (uint8_t byte : data) {
        crc ^= (byte << 8);
        for (int i = 0; i < 8; ++i) {
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
        }
    }
    return crc;
}

int main() {
    serial::Serial port(PORT_STRING, 9600,
                        serial::Timeout::simpleTimeout(1000));
    port.setParity(serial::parity_odd);
    port.setStopbits(serial::stopbits_one);
    port.setBytesize(serial::eightbits);

    vector<uint8_t> data = {0x01, 0x01, 0x00};

    vector<uint8_t> frame = {0x52, 0x00};
    frame.insert(frame.end(), data.begin(), data.end());

    uint16_t crc = crc16_ccitt(frame);
    frame.push_back(crc & 0xFF);
    frame.push_back((crc >> 8) & 0xFF);

    frame.push_back(0x03);
    frame.push_back(0xFA);

    // Конвертируем vector<uint8_t> в string для отправки
    string frame_str(frame.begin(), frame.end());
    port.write(frame_str);

    cout << "Sent: ";
    for (uint8_t b : frame) printf("%02X ", b);
    cout << endl;

    string response = port.read(64);
    cout << "Received (" << response.size() << "):\n";
    for (char c : response) {
        printf("%02X ", static_cast<uint8_t>(c));
    }
    cout << endl;

    return 0;
}
