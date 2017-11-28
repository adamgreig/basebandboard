"""
Baseband receiver.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, ClockDomain, ClockDomainsRenamer
from bbb.average import MovingAverage
from bbb.prbs import PRBSErrorDetector
from bbb.delayline import BitDelayLine


class RX(Module):
    def __init__(self, prbs_k, sample_delay, sample):
        """
        `prbs_k`: PRBS sequence length parameter, 7, 9, 11, 15, 20, 23, or 31.
        `sample_delay`: sampling clock delay signal, in samples, 0-3.
        `sample`: the input ADC sample signal, signed.
        """
        # Connect the ADC to the moving-average filter
        # self.submodules.avg = MovingAverage(sample)

        # Threshold the averages to single bits
        self.sliced = Signal()
        # self.comb += self.sliced.eq(self.avg.x > 0)
        self.comb += self.sliced.eq(~sample[-1])

        # Feed the averages to the delay line
        self.submodules.delay = BitDelayLine(self.sliced, 4, sample_delay)

        # Make a 1/4 clock for the PRBS
        self.div = Signal(2)
        self.sync += self.div.eq(self.div + 1)
        self.clock_domains.prbsclk = ClockDomain("prbsclk")
        self.comb += self.prbsclk.clk.eq(self.div[1])

        # Make the PRBS error detector
        self.submodules.prbsdet = ClockDomainsRenamer("prbsclk")(
            PRBSErrorDetector(prbs_k, self.delay.x))

        # Forward the PRBS error signal
        self.err = self.prbsdet.err
