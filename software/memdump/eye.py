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
t = np.linspace(0, 18/100e6, 18)
dat /= 512.0
dat *= 1.0
for i in range(0, 8192-18, 4):
    plt.plot(t, dat[i:i+18], lw=1, alpha=0.8, color='g')
for tt in t:
    plt.axvline(tt, ls='--', color='k')
plt.axhline(0, ls='--', color='r')

plt.xlabel("Time (s)")
plt.ylabel("ADC Reading (V)")
plt.show()
