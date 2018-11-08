"""
Virtual DSO. Ish.

Copyright 2018 Adam Greig
"""

import numpy as np
from migen import Module, Signal, Memory, FSM, Cat, NextValue, NextState, If
from migen import run_simulation


class DSO(Module):
    def __init__(self, line, frame, sample):
        """
        A virtual digital-storage-scope.
        Stores overlapping lines of samples, cleared occasionally.

        Memory is arranged into 256 rows of 64 columns.
        When `line` is pulsed, 64 successive values of sample are read,
        and the row corresponding to the value of sample is set to 1.
        When `frame` is pulsed, all memory is zeroed.

        Inputs:
        `line`: pulse high at the start of a new line of samples
        `frame`: pulse high at the start of a new frame of samples
                 (i.e., clear existing persistence)
        `sample`: 8-bit signed sample value

        Outputs:
        `readport`: a Memory port you can read to access the persisted data.
                    The address is 6 bits of column in the LSb and 8 bits
                    of row in the MSb. (0, 0) is top-left. Sample values of
                    0 are drawn in the 128th row.
        """
        self.mem = Memory(1, 64*256)
        self.readport = self.mem.get_port()
        self.writeport = self.mem.get_port(write_capable=True)
        self.specials += [self.mem, self.readport, self.writeport]

        self.rowctr = Signal(8)
        self.colctr = Signal(6)
        self.comb += self.writeport.adr.eq(Cat(self.colctr, self.rowctr))

        self.submodules.fsm = FSM(reset_state="WAIT")

        self.comb += self.writeport.we.eq(
            self.fsm.ongoing("CLEAR") | self.fsm.ongoing("WRITELINE"))
        self.comb += self.writeport.dat_w.eq(
            self.fsm.ongoing("WRITELINE"))

        self.fsm.act(
            "CLEAR",
            NextValue(self.colctr, self.colctr + 1),
            If(self.colctr == 63, NextValue(self.rowctr, self.rowctr + 1)),
            If(self.rowctr == 255, NextState("WAIT")),
        )

        self.fsm.act(
            "WAIT",
            NextValue(self.rowctr, 0),
            NextValue(self.colctr, 0),
            If(line == 1, NextState("WRITELINE"))
            .Elif(frame == 1, NextState("CLEAR"))
        )

        self.fsm.act(
            "WRITELINE",
            self.rowctr.eq(127 - sample),
            NextValue(self.colctr, self.colctr + 1),
            If(self.colctr == 63, NextState("WAIT")),
        )


def test_dso():
    line = Signal()
    frame = Signal()
    sample = Signal((8, True))
    dso = DSO(line, frame, sample)

    def tb():
        yield

        # Clear
        # (yield frame.eq(1))
        # yield
        # (yield frame.eq(0))
        # for _ in range(64*256 + 10):
        #   # yield

        target = np.zeros((64, 256), dtype=np.uint8)

        # Send a line
        (yield line.eq(1))
        yield
        (yield line.eq(0))
        for i in range(64):
            target[i][127 - i] = 1
            (yield sample.eq(i))
            yield

        for _ in range(10):
            yield

        # Send another line
        (yield line.eq(1))
        yield
        (yield line.eq(0))
        for i in range(64):
            x = -128 + i*4
            target[i][127 - x] = 1
            (yield sample.eq(x))
            yield

        for _ in range(10):
            yield

        # Dump memory contents
        mem = np.empty((64, 256), dtype=np.uint8)
        for row in range(256):
            for col in range(64):
                mem[col, row] = (yield dso.mem[row << 6 | col])
            # print(f'{row:03d}', ''.join(f'{x}' for x in mem[:, row]))
        assert np.all(mem == target)

    run_simulation(dso, tb(), vcd_name="dso.vcd")
