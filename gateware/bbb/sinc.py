"""
Sinc interpolator

Copyright 2018 Adam Greig
"""

from migen import Module, Signal, Memory, FSM, NextState, NextValue, If
import numpy as np
import scipy.signal


def make_sinc_coefficients():
    # Make the sinc filter coefficients.
    # We have have 16 filter coefficients per input sample, and
    # process 8 input samples at once, for a total of 128 coefficients.
    # The response is a windowed sinc function with 4 zero crossings
    # on either side of 0.
    # Each coefficient is quantised to 8 bits wide, signed, and we can
    # store all of them packed in to a single 32-entry, 32-bit-wide BRAM,
    # reading 8 at once from two ports. The packing structure is:
    # |------------------------
    # |   0 |  16 |  32 |  48 |
    # |  64 |  80 |  96 | 112 |
    # |   1 |  17 |  33 |  49 |
    # |  65 |  81 |  97 | 113 |
    # | ... | ... | ... | ... |
    # |  15 |  31 |  49 |  63 |
    # |  79 |  95 | 111 | 127 |
    # -------------------------
    # Each row contains 32 bits and so is treated as a single 32 bit
    # word (with the constituent coefficients shifted and OR'd), and
    # we can read two 32-bit words at a time from the two ports, so
    # we read from rows 0 and 1, then 2 and 3, etc.
    # Note that since the coefficient set is symmetric we could store
    # half of it and wrap the address backwards, but since these are stored
    # in a BRAM it's simpler to just store the whole set and have a simpler
    # address counter.
    ht = np.linspace(-4, 4, 128)
    hh = np.sinc(ht) * scipy.signal.hamming(128)
    hh *= 127.0
    hh = hh.astype(np.int8).astype(np.uint8).astype(np.int)
    packed_a = ((hh[0:16] << 24) | (hh[16:32] << 16) |
                (hh[32:48] << 8) | (hh[48:64] << 0))
    packed_b = ((hh[64:80] << 24) | (hh[80:96] << 16) |
                (hh[96:112] << 8) | (hh[112:128] << 0))
    packed = np.empty(32, dtype=np.uint32)
    packed[0::2] = packed_a
    packed[1::2] = packed_b
    return packed.tolist()


class SincInterpolator(Module):
    def __init__(self, in_port, out_port, trigger):
        """
        `in_port`: a memoryport to read input samples from.
            Samples are 8 bits wide and 72 will be read (8 samples to warm
            up the filter and 64 for actual interpolation).
        `out_port`: a memoryport to write interpolated samples to.
            Samples are 8 bits wide and 1024 will be written.
        `trigger`: begin processing a batch of input samples on.

        `self.done`: pulses after a batch of output samples is complete.
        """
        self.done = Signal()

        # Make the coefficient storage and access circuitry
        hh = make_sinc_coefficients()
        coeff_bram = Memory(32, 32, list(hh))
        coeff_port_a = coeff_bram.get_port()
        coeff_port_b = coeff_bram.get_port()
        self.specials += [coeff_bram, coeff_port_a, coeff_port_b]
        coeffs = [Signal((8, True)) for _ in range(8)]
        self.comb += [coeffs[i].eq(coeff_port_a.dat_r[32-((i+1)*8):32-(i*8)])
                      for i in range(4)]
        self.comb += [coeffs[i+4].eq(coeff_port_b.dat_r[32-((i+1)*8):32-(i*8)])
                      for i in range(4)]
        coeff_ctr = Signal(4)
        self.comb += coeff_port_a.adr.eq((coeff_ctr << 1) + 0)
        self.comb += coeff_port_b.adr.eq((coeff_ctr << 1) + 1)

        # Make the sample delay line
        shift = Signal()
        self.sync += shift.eq(coeff_ctr == 15)
        samp_adr = Signal(7)
        self.comb += in_port.adr.eq(samp_adr)
        sr = [Signal((8, True)) for _ in range(8)]
        self.sync += If(shift, sr[0].eq(in_port.dat_r))
        self.sync += [If(shift, sr[i].eq(sr[i-1])) for i in range(1, 8)]

        # Multipliers and adder tree
        muls = [Signal((16, True)) for _ in range(8)]
        self.sync += [muls[i].eq(coeffs[i] * sr[i]) for i in range(8)]
        add0 = [Signal((16, True)) for _ in range(4)]
        self.sync += [add0[i].eq(muls[2*i] + muls[2*i+1]) for i in range(4)]
        add1 = [Signal((16, True)) for _ in range(2)]
        self.sync += [add1[i].eq(add0[2*i] + add0[2*i+1]) for i in range(2)]
        add2 = Signal((8, True))
        self.sync += add2.eq((add1[0] + add1[1]) >> 8)

        # Output to BRAM
        out_adr = Signal(10)
        self.comb += out_port.adr.eq(out_adr)
        self.comb += out_port.dat_w.eq(add2)

        # Little FSM to drive the counters after being triggered
        self.submodules.fsm = FSM(reset_state="READY")
        self.fsm.act(
            "READY",
            NextValue(coeff_ctr, 0),
            NextValue(samp_adr, 0),
            # Address to start the write is offset by 8*16 to compensate for
            # the 8-sample warmup through the filter, and by 2 to compensate
            # for the adder pipeline latency (so that the final address to
            # be written is 1023).
            NextValue(out_adr, 1024 - 8*16 - 2),
            If(trigger, NextState("RUN"))
        )
        self.fsm.act(
            "RUN",
            NextValue(coeff_ctr, coeff_ctr + 1),
            NextValue(out_adr, out_adr + 1),
            If(shift, NextValue(samp_adr, samp_adr + 1)),
            If(samp_adr == 72, NextState("DONE"))
        )
        self.fsm.act(
            "DONE",
            NextState("READY"),
        )
        self.comb += out_port.we.eq(self.fsm.ongoing("RUN"))
        self.comb += self.done.eq(self.fsm.ongoing("DONE"))
