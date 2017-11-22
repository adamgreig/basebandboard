"""
Numerically controlled oscillator.

Copyright 2017 Adam Greig
"""

import numpy as np
from migen import Signal, Module, Memory


class NCO(Module):
    """
    Numerically controlled oscillator.

    Uses the input `fcw` (up to n=24 bit signal) to run an NCO which
    generates a sine wave.

    The sine wave is phase modulated by `pm`, a m=10 bit signed signal,
    frequency modulated by `fm`, an n=24 bit signed signal, and amplitude
    modulated by `am`, a p=16 bit unsigned signal.

    The result is output as `x`, a p=16 bit signed signal.
    """
    def __init__(self, fcw, am, fm, pm, n=24, m=10, p=16):
        # Phase accumulator
        self.pa = Signal(n)
        self.sync += self.pa.eq(self.pa + fcw + fm)

        # Phase to amplitude converter
        t = np.linspace(0, 2*np.pi, 2**m)
        s = np.round(np.sin(t) * (2**(p-1) - 1)).astype(np.int)
        s[s < 0] += 2**p
        self.rom = Memory(p, 2**m, s.tolist())
        self.port = self.rom.get_port()
        self.comb += self.port.adr.eq(self.pa[n-m:n] + pm)
        self.specials += [self.rom, self.port]

        # Output
        self.w = Signal((p, True))
        self.sync += self.w.eq(self.port.dat_r)
        self.y = Signal((2*p, True))
        self.sync += self.y.eq(am * self.w)
        self.x = Signal((p, True))
        self.comb += self.x.eq(self.y[p:])


def test_nco():
    from migen.sim import run_simulation
    fcw = Signal(24, reset=2**14)
    am = Signal((16, False), reset=2**16 - 1)
    fm = Signal((24, True), reset=0)
    pm = Signal((10, True), reset=0)

    values = []
    nco = NCO(fcw, am, fm, pm)

    def tb():
        for _ in range(1024):
            values.append((yield nco.x))
            yield
        expected = np.sin(np.linspace(0, 2*np.pi, 1024)) * (2**15 - 1)
        expected = np.round(expected).astype(np.int) * (2**16 - 1)
        expected >>= 16
        assert values[3:] == expected.tolist()[:-3]

    run_simulation(nco, tb())
