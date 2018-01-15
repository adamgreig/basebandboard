from ..sinc import SincInterpolator
from migen import Signal, Memory
from migen.sim import run_simulation
import numpy as np
import scipy.signal
import matplotlib.pyplot as plt


def do_interpolation():
    x = np.sin(2*np.pi*7*np.linspace(0, 1, 72)) * 127
    x = x.astype(np.int8).astype(np.int16)
    h = np.sinc(np.linspace(-4, 4, 128)) * scipy.signal.hamming(128) * 127
    h = h.astype(np.int8).astype(np.int16)
    x = np.repeat(x, 16)
    for i in range(1, 16):
        x[i::16] = 0
    rx = np.convolve(x, h, mode='same') >> 8
    return rx[46:]


def test_sinc():
    samples = np.sin(2*np.pi*7*np.linspace(0, 1, 72)) * 127
    inmem = Memory(8, 72, samples.astype(np.int8).tolist())
    inport = inmem.get_port()
    outmem = Memory(8, 1024)
    outport = outmem.get_port(write_capable=True)
    trigger = Signal()
    sinc = SincInterpolator(inport, outport, trigger)
    sinc.specials += [inmem, inport, outmem, outport]

    def tb():
        for _ in range(20):
            yield
        yield trigger.eq(1)
        yield
        yield trigger.eq(0)
        for _ in range(1200):
            yield
        data = []
        for x in range(1024):
            data.append((yield outmem[x]))
        data = np.array(data, dtype=np.int8)
        rx = do_interpolation()
        if not np.all(rx[:1024] == data):
            if False:
                plt.plot(data, color='g')
                plt.plot(rx, color='r')
                plt.ylim(-100, 100)
                plt.grid()
                plt.show()
        assert rx[:1024].tolist() == data.tolist()

    run_simulation(sinc, tb(), vcd_name="sinc.vcd")
