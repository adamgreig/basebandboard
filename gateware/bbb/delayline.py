"""
Delay incoming words by a configurable count, using a block RAM.

Copyright 2017 Adam Greig
"""

import pytest
from migen import Module, Signal, Memory, Array


class RAMDelayLine(Module):
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


class BitDelayLine(Module):
    """
    Delays incoming bits by a variable delay depth.
    """
    def __init__(self, bit, max_delay, delay):
        """
        `bit` is the input signal, one bit wide.
        `max_delay` is the longest permissible delay (length of delay line).
        `delay` is a signal containing the length to delay by, which may not
            exceed `max_delay`.

        Output `x` is the delayed bit.
        """
        self.x = Signal()

        # Create the shift register. We'll make it `max_delay+1` so we can
        # store the current input at index 0 too.
        max_delay = max_delay + 1
        self.sr = Array(Signal() for _ in range(max_delay))
        self.comb += self.sr[0].eq(bit)
        self.sync += [self.sr[i].eq(self.sr[i-1]) for i in range(1, max_delay)]
        self.comb += self.x.eq(self.sr[delay])


@pytest.mark.parametrize("delay", [3, 4, 5, 6])
def test_ram_delay_line(delay):
    from migen.sim import run_simulation
    source = Signal(12)
    delay_sig = Signal(12, reset=delay)
    delay_line = RAMDelayLine(source, delay_sig)
    outputs = []

    def tb():
        for step in range(100):
            (yield source.eq(step))
            outputs.append((yield delay_line.x))
            yield

        assert outputs == [0]*delay + list(range(100 - delay))

    run_simulation(delay_line, tb())


@pytest.mark.parametrize("delay", [0, 1, 2, 3, 4, 5, 6])
def test_bit_delay_line(delay):
    from migen.sim import run_simulation
    source = Signal()
    delay_sig = Signal(4, reset=delay)
    delay_line = BitDelayLine(source, 6, delay_sig)
    bits = [1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 1]
    out = []

    def tb():
        for bit in bits:
            (yield source.eq(bit))
            yield
            out.append((yield delay_line.x))

        assert out == [0]*delay + bits[:len(bits)-delay]

    run_simulation(delay_line, tb())
