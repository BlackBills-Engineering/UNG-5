enum PumpCommand {
    RETURN_STATUS = 0x0,
    RETURN_PUMP_IDENTITY = 0x2,
    RETURN_FILLING_INFORMATION = 0x3,
    RESET = 0x4,
    AUTHORIZE = 0x5,
    SUSPEND = 0x6,
    RESUME = 0x8,
    STOP = 0x10,
    SWITCH_OFF = 0xa,
};

enum PumpStatus {
    PUMP_NOT_PROGRAMMED,
    // RESET,
    AUTHORIZED_SUSPENDED,
    FILLING_SUSPENDED,
    FILLING_COMPLETED,
    MAX_AMOUNT_OR_VOLUME_REACHED,
    SWITCHED_OFF
};

enum TransactionToPump {
    CD1,
    CD2,
    CD3,
    CD4,
    CD5,
    CD6,
    CD7,
    CD8,
    CD9,
    CD10,
    CD11,
    CD12,
    CD13,
    CD14,
    CD15,
    CD16,
};

enum TransactionToController {
    DC1,
    DC2,
    DC3,
    DC4,
    DC5,
    DC6,
    DC7,
    DC8,
    DC9,
    DC10,
    DC14,
    DC15,
    DC100,
    DC101,
};