"""
Generate uniform k-bit random integers.

Based on the paper "High Quality Uniform Random Number Generation Using LUT
Optimised State-transition Matrices" by David B. Thomas and Wayne Luk.

Copyright 2017 Adam Greig
"""

import numpy as np
from functools import reduce
from operator import xor
from migen import Module, Signal
from migen.sim import run_simulation


class LUTOPT(Module):
    """
    Generates uniform random integers according to the given binary recurrence.
    """
    def __init__(self, a, init=1):
        """
        Initialise with a recurrence matrix `a` that has shape k by k.

        The initial state is set to `init`.
        """
        # `x` is k bits wide and outputs uniform random bits
        self.x = Signal(a.shape[0], reset=init)

        ###

        self.a = a
        self.k = a.shape[0]

        # Each row of `a` represents the input connections for each element of
        # state. Each LUT thus XORs those old state bits together to produce
        # the new state bit.
        for idx, row in enumerate(a):
            taps = np.nonzero(row)[0].tolist()
            self.sync += self.x[idx].eq(reduce(xor, [self.x[i] for i in taps]))

    @classmethod
    def from_packed(cls, packed, init=1):
        """
        Creates a new LUTOPT from a packed representation.

        The initial state is set to `init`.
        """
        k = int(np.sqrt(len(packed)*8))
        a = np.unpackbits(np.array(packed, dtype=np.uint8)).reshape(k, k)
        return cls(a, init)


def test_lutopt():
    """Tests that the HDL matches the normal recurrence implementation."""
    # Generate a suitable recurrence matrix
    packed = [32, 9, 8, 224, 20, 5, 96, 65, 10, 80, 68, 36, 80, 3, 39, 0, 136,
              136, 26, 1, 9, 24, 132, 36, 0, 195, 25, 16, 130, 10, 131, 32]
    lutopt = LUTOPT.from_packed(packed, init=1)
    a, k = lutopt.a, lutopt.k

    def tb():
        # x represents our state, k bits wide
        x = np.zeros((k, 1), dtype=np.uint8)
        # Initialise to the same initial state as the LUTOPT
        x[0] = 1

        # Check the first 100 outputs
        for _ in range(100):
            # Run the hardware for one clock
            yield

            # Run our recurrence, convert to an integer
            x = np.mod(np.dot(a, x), 2)
            x_int = int(''.join(str(xi) for xi in x[::-1].flatten()), 2)

            assert (yield lutopt.x) == x_int

    run_simulation(lutopt, tb())
