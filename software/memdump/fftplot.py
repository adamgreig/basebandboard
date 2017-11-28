import sys
import numpy as np
import scipy.signal
import struct
import serial
import matplotlib.pyplot as plt

if len(sys.argv) != 3:
    print("Usage: {} <serial port> <baud rate>".format(sys.argv[0]))
    sys.exit()

ser = serial.Serial(sys.argv[1], sys.argv[2])
dat = ser.read(8192*2)
dat = np.array(struct.unpack("<{}h".format(8192), dat)).astype(np.float)
dat /= 512.0
dat *= 1.0

plt.magnitude_spectrum(dat, Fs=100e6, scale='dB')
plt.grid()
plt.show()
