"""
Baseband receiver.

Copyright 2017 Adam Greig
"""

import numpy as np
from migen import Module, Signal, ClockDomain, ClockDomainsRenamer
from bbb.average import MovingAverage
from bbb.prbs import PRBSErrorDetector
from bbb.delayline import BitDelayLine


class RX(Module):
    def __init__(self, prbs_k, samples_per_bit, sample_delay, sample):
        """
        `prbs_k`: PRBS sequence length parameter, 7, 9, 11, 15, 20, 23, or 31.
        `samples_per_bit`: RX clocks per TX bit. Must be a power of 2.
        `sample_delay`: sampling clock delay signal, in samples, 0-15.
        `sample`: the input ADC sample signal, signed.
        """
        self.sliced = Signal()

        # Optionally preprocess with a moving average filter.
        # self.submodules.avg = MovingAverage(sample)
        # self.comb += self.sliced.eq(self.avg.x > 0)

        # Threshold the samples to single bits
        self.comb += self.sliced.eq(~sample[-1])

        # Feed the averages to the delay line
        self.submodules.delay = BitDelayLine(
            self.sliced, samples_per_bit, sample_delay)

        # Make a 1/max_delay clock for the PRBS
        self.div = Signal(int(np.log2(samples_per_bit)))
        self.sync += self.div.eq(self.div + 1)
        self.clock_domains.prbsclk = ClockDomain("prbsclk")
        self.comb += self.prbsclk.clk.eq(self.div[1])

        # Make the PRBS error detector
        self.submodules.prbsdet = ClockDomainsRenamer("prbsclk")(
            PRBSErrorDetector(prbs_k, self.delay.x))

        # Forward the PRBS error signal
        self.err = self.prbsdet.err
