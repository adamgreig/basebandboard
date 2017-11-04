"""
Generate PRBS bit sequences.

Copyright 2017 Adam Greig
"""

import pytest
from migen import Module, Signal, Cat
from migen.sim import run_simulation

# These are the taps for each PRBS sequence which are not the MSb
TAPS = {7: 6, 9: 5, 11: 9, 15: 14, 20: 3, 23: 18, 31: 28}


class PRBS(Module):
    """
    Generates PRBSk binary test sequences, output as the 1-bit signal `self.o`.

    k must be one of (7, 9, 11, 15, 20, 23, 31).
    """
    def __init__(self, k):
        # `o` is a single bit which outputs the PRBS sequence.
        self.o = Signal()

        ###

        if k not in TAPS.keys():
            raise ValueError("k={} invalid for PRBSGenerator".format(k))

        tap = TAPS[k]
        state = Signal(k, reset=1)
        self.comb += self.o.eq(state[k-1] ^ state[tap-1])
        self.sync += Cat(state).eq(Cat(self.o, state))


@pytest.mark.parametrize("k", TAPS.keys())
def test_prbs(k):
    prbs = PRBS(k)

    def tb():
        lfsr = 1
        # Test up to the first 512 bits. We'd be here forever testing PRBS31.
        for _ in range(min((1 << k) - 1, 512)):

            # These two lines simulate the PRBS generator in Python
            bit = ((lfsr >> (k-1)) ^ (lfsr >> TAPS[k]-1)) & 1
            lfsr = ((lfsr << 1) | bit) & ((1 << k)-1)

            # We compare it to the hardware simulation result
            assert (yield prbs.o) == bit

            # Run the hardware for one clock cycle
            yield

    run_simulation(prbs, tb())
