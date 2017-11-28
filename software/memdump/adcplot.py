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
#dat /= 512.0
#dat *= 1.0



t = np.linspace(0, 8192/100e6, 8192)
plt.plot(t, dat, '-x', color='y', label="original")
#plt.plot(t[0::4], dat[0::4], '-x', color='b', label="shift 0")
#plt.plot(t[1::4], dat[1::4], '-x', color='g', label="shift 1")
#plt.plot(t[2::4], dat[2::4], '-x', color='r', label="shift 2")
#plt.plot(t[3::4], dat[3::4], '-x', color='c', label="shift 3")
plt.grid()
plt.legend()
#plt.ylim((-1, 1))
plt.xlabel("Time (s)")
#plt.ylabel("Voltage (V)")
plt.show()


#dat = scipy.signal.lfilter([1, 1, 1, 1], [1], dat)
dat = dat[3::4]
dat = (dat > 0).astype(np.uint8)
print("".join(str(x) for x in dat)[::-1])
