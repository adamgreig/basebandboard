"""
Delay incoming words by a configurable count, using a block RAM.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, Memory


class DelayLine(Module):
    """
    Delays incoming samples by a variable delay depth using a BRAM.

    `sample` is a signal containing the incoming words, at most 16 bits wide.
    `delay` is a signal containing the length to delay by, at least 3.

    Output `x` is the delayed samples.
    """
    def __init__(self, sample, delay):
        # `x` is the output, same width as the input
        self.width = sample.nbits
        self.x = Signal(self.width)

        # This counter determines where samples are written to in memory;
        # we then read from counter-delay. Since we use the BRAM as 512x16,
        # use a 9 bit counter to address the full RAM.
        self.ctr = Signal(9)
        self.sync += self.ctr.eq(self.ctr + 1)

        # Create the RAM
        self.ram = Memory(16, 512)
        self.inport = self.ram.get_port(write_capable=True)
        self.outport = self.ram.get_port()
        self.specials += [self.ram, self.inport, self.outport]

        # Wire up the RAM
        self.comb += self.inport.adr.eq(self.ctr)
        self.comb += self.inport.dat_w.eq(sample)
        self.comb += self.inport.we.eq(1)
        self.comb += self.outport.adr.eq(self.ctr - delay + 2)
        self.comb += self.x.eq(self.outport.dat_r)


def test_delay_line():
    from migen.sim import run_simulation
    source = Signal(12)
    delay = Signal(12, reset=3)
    delay_line = DelayLine(source, delay)
    outputs = []

    def tb():
        for step in range(100):
            (yield source.eq(step))
            outputs.append((yield delay_line.x))
            yield

        assert outputs == [0, 0, 0] + list(range(100 - 3))

    run_simulation(delay_line, tb())
