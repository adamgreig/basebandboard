"""
Moving average filter.

Copyright 2017 Adam Greig
"""

from migen import Signal, Module


class MovingAverage(Module):
    """
    Output the moving average over four input samples.

    `sample` is the input signal, and is signed.

    Outputs `x`, which is the average of the current value of `sample`
        and its previous three values, delayed by two additional clocks
        due to pipelining.
    """
    def __init__(self, sample):
        self.width = sample.nbits
        self.sr = [Signal((self.width + 2, True)) for _ in range(4)]
        self.sum11 = Signal((self.width+2, True))
        self.sum12 = Signal((self.width+2, True))
        self.x = Signal((self.width+2, True))
        self.sync += [
            self.sr[0].eq(sample),
            self.sr[1].eq(self.sr[0]),
            self.sr[2].eq(self.sr[1]),
            self.sr[3].eq(self.sr[2]),
            self.sum11.eq(self.sr[0] + self.sr[1]),
            self.sum12.eq(self.sr[2] + self.sr[3]),
            self.x.eq(self.sum11 + self.sum12)]


def test_moving_average():
    import numpy as np
    from migen.sim import run_simulation

    samp = Signal((12, True))
    ma = MovingAverage(samp)
    wave = np.random.randint(-2048, 2047, 100).astype(np.int)
    out = []

    def tb():
        for s in wave:
            (yield samp.eq(int(s)))
            out.append((yield ma.x))
            yield
        expected = np.cumsum(wave).astype(np.int)
        expected[4:] = expected[4:] - expected[:-4]
        expected = expected[3:-3] >> 2
        expected = expected.tolist()
        assert out[6:] == expected

    run_simulation(ma, tb())
