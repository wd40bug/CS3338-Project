import serial
import time

# Open serial connection
esp = serial.Serial(port = 'COM3', baudrate = 115200, timeout = .1)
time.sleep(0.05)

def send_byte(c):
    esp.write(bytes([c]))
    time.sleep(0.05)

msg = [20, 6]

for i in msg:
    send_byte(i)