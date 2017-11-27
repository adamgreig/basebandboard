import sys
import numpy as np
import struct
import serial
import matplotlib.pyplot as plt

if len(sys.argv) != 3:
    print("Usage: {} <serial port> <baud rate>".format(sys.argv[0]))
    sys.exit()

ser = serial.Serial(sys.argv[1], sys.argv[2])
dat = ser.read(8191*2)
dat = np.array(struct.unpack("<{}h".format(8191), dat)).astype(np.float)
dat /= 512.0
dat *= 1.0
t = np.linspace(0, 8191/100e6, 8191)
plt.plot(t, dat, '-x')
plt.grid()
plt.ylim((-1, 1))
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.show()
