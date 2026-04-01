import serial
import time


# Open serial connection
esp = serial.Serial(port = 'COM3', baudrate = 115200)
time.sleep(0.05)
esp.reset_input_buffer()
time.sleep(0.2)

def send_serial(json: str):
    esp.write(bytes(json, 'utf-8'))

def read_serial():
    line = esp.readline()
    return line.decode()

