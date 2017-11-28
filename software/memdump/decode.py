import sys
import numpy as np
import struct
import serial

if len(sys.argv) != 3:
    print("Usage: {} <serial port> <baud rate>".format(sys.argv[0]))
    sys.exit()

ser = serial.Serial(sys.argv[1], sys.argv[2])
dat = ser.read(8192*2)
dat = np.array(struct.unpack("<{}h".format(8192), dat)).astype(np.float)
t = np.linspace(0, 18/100e6, 18)

dat = (dat > 0).astype(np.uint8)
dat = dat[::4]

print(''.join(str(x) for x in dat))
