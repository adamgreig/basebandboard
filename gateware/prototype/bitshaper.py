"""
Shape a bitstream into oversampled pulses.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, ClockDomain, Cat, Memory
from migen.fhdl.decorators import ClockDomainsRenamer


class PRBSShaper(Module):
    """
    Given a PRBS, clocks it with a /8 divider, then runs each bit through a
    pulse shaper and outputs the sum of all active pulses.

    `prbs` is a PRBS generator with an output `x`.
    `setsel` is a 5 bit coefficient set selector signal.
    `coefficients` is a list of up to 32 lists of 64 coefficients,
                   each of which is an integer in (-256, 255).
                   Each bit duration is 8 coefficients.

    Output `x` is a 12-bit signed sum of all active pulses.
    """
    def __init__(self, prbs, setsel, coefficients):
        # `x` is the signed 12-bit output
        self.x = Signal((12, True))

        # Make a divide-by-8 clock for the PRBS and its output SR
        self.div = Signal(3)
        self.sync += self.div.eq(self.div + 1)
        self.clock_domains.prbsclk = ClockDomain("prbsclk")
        self.comb += self.prbsclk.clk.eq(self.div[2])

        # Make the PRBS a submodule and feed it the divided clock
        self.submodules.prbs = ClockDomainsRenamer("prbsclk")(prbs)

        # Make an 8-long SR for the output of the PRBS, with the same clock
        self.sr = Signal(8)
        self.prbs.sync += Cat(self.sr).eq(Cat(self.prbs.x, self.sr))

        # Prepare the memory contents.
        # We convert the signed integers to unsigned words, and we store
        # the negative version of each coefficient immediately before the
        # original version as well. They are then split into 8 ROMs of 8
        # coefficients each.
        coeffs = [[] for _ in range(8)]
        for cset in coefficients:
            for idx, c in enumerate(cset):
                # Take the positive and negative versions of c,
                # and convert both to signed positive integer representation.
                cp, cm = c, -c
                if cp < 0:
                    cp += 512
                if cm < 0:
                    cm += 512
                coeffs[idx//8].append(cm)
                coeffs[idx//8].append(cp)

        # Make a counter for the ROM addresses, which is offset from the
        # PRBS shift register clock so that ctr runs through 0 to 7 for each
        # whole bit duration from the PRBS.
        self.ctr = Signal(3, reset=4)
        self.sync += self.ctr.eq(self.ctr + 1)

        # Set up 8 ROMs
        self.roms = [Memory(9, 512, coeffs[i]) for i in range(8)]
        self.specials += self.roms
        self.ports = [self.roms[i].get_port() for i in range(8)]
        self.specials += self.ports
        self.portsout = [Signal((9, True)) for _ in range(8)]
        for idx, port in enumerate(self.ports):
            self.comb += port.adr.eq(Cat(self.sr[idx], self.ctr, setsel))
            self.sync += self.portsout[idx].eq(port.dat_r)

        # Adder tree to output
        self.adders0 = [Signal((10, True)) for _ in range(4)]
        for idx, adder in enumerate(self.adders0):
            self.sync += adder.eq(
                self.portsout[idx*2] + self.portsout[idx*2 + 1])
        self.adders1 = [Signal((11, True)) for _ in range(2)]
        for idx, adder in enumerate(self.adders1):
            self.sync += adder.eq(
                self.adders0[idx*2] + self.adders0[idx*2 + 1])
        self.x = Signal((12, True))
        self.sync += self.x.eq(self.adders1[0] + self.adders1[1])


def test_prbs_shaper_simple():
    import numpy as np
    from prbs import PRBS
    from migen.sim import run_simulation

    # Make the PRBS9 generator
    prbs9 = PRBS(9)

    # Generate a raised cosine pulse shape, and convert to fixed point
    t = np.arange(-32, 32)
    β = 0.5
    c = 1/8 * np.sinc(t/8) * np.cos(np.pi * β * t/8)/(1-((2*β*t/8)**2))
    c[t == 8/(2*β)] = c[t == -8/(2*β)] = np.pi/(4*8) * np.sinc(1/(2*β))
    scale = 254/c.max()
    c = (c*scale).astype(np.int)
    c = c.tolist()

    # We'll only use a single coefficient set here
    setsel = Signal(5, reset=0)

    # Make the shaper
    shaper = PRBSShaper(prbs9, setsel, [c])

    def tb():
        prbs = []
        shaped = []
        for _ in range(320):
            prbs.append((yield shaper.prbs.x))
            shaped.append((yield shaper.x))
            yield
        np.savez_compressed("shaped.npz", prbs=prbs, shaped=shaped, c=c)
        # TODO: Find some way to test this.
        # eg: scipy.signal.lfilter(c, [1], 2*prbs-1)
        # Need to handle offset (ok), weird scaling (???), and
        # not-quite-matched response (?????)
        assert(False)

    run_simulation(shaper, tb(), clocks={"sys": 10, "prbsclk": 80})
