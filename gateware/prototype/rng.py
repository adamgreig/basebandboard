"""
Generate random numbers.

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

    Based on the paper "High Quality Uniform Random Number Generation Using LUT
    Optimised State-transition Matrices" by David B. Thomas and Wayne Luk.
    """
    def __init__(self, a, init=1):
        """
        Initialise with a recurrence matrix `a` that has shape k by k.

        The initial state is set to `init`.

        Outputs `x`, which is k bits wide and uniformly distributed,
        on each clock cycle.
        """
        self.x = Signal(a.shape[0], reset=init)

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
        Creates a new LUTOPT from a packed representation: a list of k lists,
        which each contains the position of the 1 entries for that row.

        The initial state is set to `init`.
        """
        k = len(packed)
        a = np.zeros((k, k), dtype=np.uint8)
        for row in range(k):
            for idx in packed[row]:
                a[row, idx] = 1
        return cls(a, init)


class CLTGRNG(Module):
    """
    Generates a Gaussian-distributed random integer by tree-summing the bits
    of a large uniform random integer.

    The result is generated on each clock cycle, and has mean 0 (as a signed
    integer) and variance equal to 2**(log2(n)-2), where n is the width of the
    input URNG.

    Outputs `x` each clock cycle, which is signed, has width log2(n),
    is Gaussian-distributed, and is log2(n) clock cycles delayed from urng.
    """
    def __init__(self, urng):
        """
        `urng` must be provided, a n-bit wide uniform RNG module with output x,
        where n is a power of two.
        """
        n = urng.x.nbits
        logn = int(np.log2(n))

        self.x = Signal((logn, True))
        self.submodules.urng = urng

        # We have logn levels of registers (including the output).
        # The first level contains n/2 Signals, each 2 bits wide, and is
        # computed directly from the input signal. The next level is n/4
        # Signals, each 3 bits wide, and so on until the final level,
        # which has just 1 Signal which is logn bits wide (the output).
        self.levels = [[] for _ in range(logn)]
        for level in range(logn):
            level_n = 2**(logn - level - 1)
            level_bits = level+2
            self.levels[level] = [Signal((level_bits, True))
                                  for _ in range(level_n)]

        # Input level computations.
        # Each 2-bit entry in level0 is the difference of the two 1-bit
        # entries in the input from the URNG.
        for idx in range(len(self.levels[0])):
            a, b = 2*idx, 2*idx+1
            self.sync += self.levels[0][idx].eq(urng.x[a] - urng.x[b])

        # Remaining level computations.
        for level in range(1, logn):
            for idx in range(len(self.levels[level])):
                a, b = 2*idx, 2*idx + 1
                self.sync += self.levels[level][idx].eq(
                        self.levels[level-1][a] - self.levels[level-1][b])

        # Output
        self.comb += self.x.eq(self.levels[-1][0])


def test_lutopt():
    """Tests that the HDL matches the normal recurrence implementation."""
    # Generate a suitable recurrence matrix
    packed = [
        [8, 11, 12, 13], [2, 6, 14], [0, 3, 4, 7], [1, 5, 9, 15], [5, 10, 13],
        [0, 2, 3, 6], [10, 12, 15], [4, 7, 9, 11], [0, 1, 8, 14],
        [5, 9, 10, 12], [1, 7, 13, 15], [2, 4, 14], [3, 6, 8], [0, 8, 11, 15],
        [6, 10, 11, 12], [2, 5, 7, 13]]
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


def test_cltgrng():
    """Tests that the CLTGRNG matches the Python implementation."""
    packed = [
        [5, 15, 19], [11, 25, 30, 31], [10, 17, 21, 28], [1, 3, 23],
        [2, 7, 18, 29], [9, 14, 20, 27], [4, 8, 16, 26], [0, 6, 12, 24],
        [13, 22, 26], [10, 14, 24, 28], [2, 13, 15, 19], [4, 6, 9, 27],
        [3, 17, 23, 25], [12, 16, 22, 30], [0, 1, 7, 8], [11, 18, 20, 31],
        [2, 5, 21, 29], [0, 1, 14, 17], [9, 22, 25], [3, 18, 28, 31],
        [7, 21, 24, 29], [4, 5, 6, 16], [8, 13, 20], [11, 15, 19, 26],
        [10, 12, 23, 30], [5, 10, 13, 27], [2, 8, 22, 25], [7, 12, 14, 21],
        [3, 15, 24, 31], [4, 6, 19, 23], [17, 28, 30], [16, 18, 20]]
    urng = LUTOPT.from_packed(packed, init=1)
    grng = CLTGRNG(urng)
    n = len(packed)
    logn = int(np.log2(n))

    def tb_urng():
        yield

    def tb():
        # Run a few cycles of the URNG to warm it up and fill up the
        # register hierarchy of the GRNG.
        for _ in range(2*logn):
            yield

        # Check first 100 outputs match
        results = []
        for i in range(100):
            # Run the hardware simulation for one clock cycle
            yield

            # Fetch the URNG value and compute the corresponding Gaussian.
            # Note that we bit-reverse the URNG to correspond to the bit
            # indexing of the hardware.
            x = np.array([int(x) for x in
                          bin(int((yield urng.x)))[2:].rjust(n, "0")[::-1]])
            for level in range(logn):
                level_n = 2**(logn - level)
                y = np.zeros(level_n//2, dtype=np.int16)
                for pair in range(0, level_n, 2):
                    y[pair//2] = x[pair] - x[pair+1]
                x = y
            results.append(x[0])

            # Convert grng.x into signed form
            grng_x = (yield grng.x)
            grng_x = grng_x if grng_x < 2**31 else (grng_x - 2**32)

            # Once we've collected enough results to compensate for the
            # clock delay, start comparing numbers.
            if len(results) > logn:
                assert grng_x == results[-logn-1]

    run_simulation(grng, tb())
