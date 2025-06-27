CXX = g++
CXXFLAGS = -std=c++11 -Wall -Wextra -O2 -g
TARGET = mkr5_controller
SOURCES = main_fixed.cpp

# Определение платформы
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    # macOS
    CXXFLAGS += -DMACOS
endif

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCES)

clean:
	rm -f $(TARGET)

debug: CXXFLAGS += -DDEBUG -g3
debug: $(TARGET)

test: $(TARGET)
	./$(TARGET)

.PHONY: all clean debug test
