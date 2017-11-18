"""
Baseband transmitter.

Outputs shaped PRBS bit sequence, with optional added Guassian white noise
with controllable noise power.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, Mux

from bbb.rng import LUTOPT, CLTGRNG
from bbb.rng_recurrences import n256 as packed_256
from bbb.prbs import PRBS
from bbb.bitshaper import PRBSShaper


class TX(Module):
    """
    A complete baseband transmitter module. Generates 12 bit signed samples
    of the signal to be output, one sample per clock, with the underlying
    data clock at 1/8 of the module clock.
    """
    def __init__(self, prbs_k, bit_en, shape_sel, noise_en, noise_var):
        """
        `prbs_k`: PRBS sequence length parameter, 7, 9, 11, 15, 20, 23, or 31.
        `bit_en`: a 1-bit signal that enables or disables the shaped bits.
        `shape_sel`: a 5-bit signal which selects which pulse shape is used.
        `noise_en`: a 1-bit signal that enables or disables the noise.
        `noise_var`: a 4-bit signed signal which controls the noise variance.

        Output `x` is the 12-bit signed sum of the shaped data bits (if
        enabled) and the scaled Gaussian noise (if enabled).
        """
        # Create the shaped PRBS generator
        self.betas = [0.0, 0.5, 1.0]
        self.prbs = PRBS(prbs_k)
        self.shaper = PRBSShaper.from_rcf(self.prbs, shape_sel, self.betas)
        self.bitmux = Mux(bit_en, self.shaper.x, Signal((12, True), reset=0))
        self.submodules += self.shaper

        # Create the Gaussian random noise generator.
        # Note since the URNG is 256bit, the GRNG is 8 bit, -128 to +127.
        self.urng = LUTOPT.from_packed(packed_256)
        self.grng = CLTGRNG(self.urng)
        self.submodules += self.grng

        # Manage scaling the GRNG
        self.noise = Signal((12, True))
        self.sync += self.noise.eq(self.grng.x * noise_var)
        self.noisemux = Mux(noise_en, self.noise, Signal((12, True), reset=0))

        # Set up the output
        self.x = Signal((12, True))
        self.sync += self.x.eq(self.bitmux + self.noisemux)
