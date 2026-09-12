# Top-level ESP-IDF project file.
# Build with: idf.py set-target esp32s3 && idf.py menuconfig && idf.py build flash monitor
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(csi_presence_firmware)
