"""
User interface.

Copyright 2018 Adam Greig
"""

from migen import Module, Signal, If, FSM, NextValue, NextState, Memory, Mux
from .axi3 import AXI3ToFromBRAM


class UIDisplay(Module):
    def __init__(self, axi3_read, axi3_write, backbuf, trigger,
                 thresh_x, thresh_y, beta, sigma2, tx_src, tx_en, noise_en):
        self.drawn = Signal()

        # Row and column counters
        row = Signal(9)
        col = Signal(9)
        run = Signal()
        self.sync += If(
            col == 479,
            col.eq(0),
            If(
                row == 272,
                row.eq(0),
            ).Else(
                row.eq(row + 1)
            )
        ).Else(
            col.eq(col + run)
        )

        # BRAM to store one line
        bram = Memory(32, 512)
        bram_pa = bram.get_port(write_capable=True)
        bram_pb = bram.get_port(write_capable=True)
        self.specials += [bram, bram_pa, bram_pb]

        # Make a counter to track the address of the current line,
        # offset for the vertical back porch and compensate for latency.
        rowaddr = Signal(backbuf.nbits)
        self.comb += rowaddr.eq(backbuf + (4*480)*(row-1))

        muxsel = Signal()
        axiaddr = Signal(backbuf.nbits)
        self.comb += axiaddr.eq(Mux(muxsel, rowaddr, rowaddr))

        # Set up an AXI3 master to read and write data through the BRAM
        axitrigger_r = Signal()
        axitrigger_w = Signal()
        axi3_bram = AXI3ToFromBRAM(axi3_read, axi3_write, bram_pb,
                                   axitrigger_r, axitrigger_w, axiaddr,
                                   480, axi3_burst_length=16)
        self.submodules += axi3_bram

        self.submodules.overlay = UIOverlay(row, col, thresh_x, thresh_y,
                                            beta, sigma2, tx_src, tx_en,
                                            noise_en)

        self.comb += bram_pa.adr.eq(col)
        self.comb += bram_pa.we.eq(1)
        self.comb += bram_pa.dat_w[0:24].eq(self.overlay.data)

        self.submodules.fsm = FSM(reset_state="READY")
        self.fsm.act(
            "READY",
            If(trigger, NextState("OVERLAY_GENERATE"))
        )
        self.fsm.act(
            "OVERLAY_GENERATE",
            If(col == 479, NextState("OVERLAY_WRITE"))
        )
        self.fsm.act(
            "OVERLAY_WRITE",
            NextState("OVERLAY_WAIT"),
        )
        self.fsm.act(
            "OVERLAY_WAIT",
            If(axi3_bram.ready,
                If(row == 272, NextState("READY"))
                .Else(NextState("OVERLAY_GENERATE")))
        )
        self.comb += self.drawn.eq(self.fsm.ongoing("READY"))
        self.comb += run.eq(self.fsm.ongoing("OVERLAY_GENERATE"))
        self.comb += axitrigger_w.eq(self.fsm.ongoing("OVERLAY_WRITE"))


class UIOverlay(Module):
    def __init__(self, row, col,
                 thresh_x, thresh_y, beta, sigma2, tx_src, tx_en, noise_en):
        self.data = Signal(24)

        red = 0b000000000000000011111111
        grn = 0b000000001111111100000000
        blu = 0b111111110000000000000000
        wte = 0b111111111111111111111111
        blk = 0b000000000000000000000000
        gry = 0b001111110011111100111111

        self.sync += If(
            # Draw white box around display reticule
            (((col == 8) | (col == 264)) & ((row > 7) & (row < 265)))
            |
            (((row == 8) | (row == 264)) & ((col > 7) & (col < 265))),
            self.data.eq(wte)
        ).Elif(
            # Inside reticule
            (col > 7) & (col < 264) & (row > 7) & (row < 264),
            If(
                # Draw target lines
                ((col - 8) == thresh_x) | ((row - 8) == thresh_y),
                self.data.eq(grn)
            ).Elif(
                # Draw reticule dots
                (((col - 8) & 0b1111) == 0) & (((row - 8) & 0b1111) == 0),
                self.data.eq(wte)
            ).Else(
                self.data.eq(blk)
            )
        ).Elif(
            # Draw beta slider
            (row > 47) & (row < 64) & (col > 279),
            If(
                col < (280 + beta),
                self.data.eq(grn | blu)
            ).Elif(
                col < 464,
                self.data.eq(wte)
            ).Else(
                self.data.eq(blk)
            )
        ).Elif(
            # Draw sigma2 slider
            (row > 79) & (row < 96) & (col > 279),
            If(
                col < (280 + sigma2),
                self.data.eq(grn | blu)
            ).Elif(
                col < 464,
                self.data.eq(wte)
            ).Else(
                self.data.eq(blk)
            )
        ).Elif(
            # Draw source select toggle
            (row > 111) & (row < 128) & (col > 279),
            If(
                col < 340,
                If(tx_src, self.data.eq(gry)).Else(self.data.eq(red | grn))
            ).Elif(
                col < 404,
                self.data.eq(blk)
            ).Elif(
                col < 464,
                If(tx_src, self.data.eq(red | blu)).Else(self.data.eq(gry))
            ).Else(
                self.data.eq(blk)
            )
        ).Elif(
            # Draw tx enabled toggle
            (row > 143) & (row < 160) & (col > 279),
            If(
                col < 340,
                If(tx_en, self.data.eq(gry)).Else(self.data.eq(red))
            ).Elif(
                col < 404,
                self.data.eq(blk)
            ).Elif(
                col < 464,
                If(tx_en, self.data.eq(grn)).Else(self.data.eq(gry))
            ).Else(
                self.data.eq(blk)
            )
        ).Elif(
            # Draw noise enabled toggle
            (row > 175) & (row < 192) & (col > 279),
            If(
                col < 340,
                If(noise_en, self.data.eq(gry)).Else(self.data.eq(red))
            ).Elif(
                col < 404,
                self.data.eq(blk)
            ).Elif(
                col < 464,
                If(noise_en, self.data.eq(grn)).Else(self.data.eq(gry))
            ).Else(
                self.data.eq(blk)
            )
        ).Else(
            self.data.eq(blk)
        )


class UIController(Module):
    def __init__(self, touchscreen):
        self.thresh_x = Signal(8, reset=127)
        self.thresh_y = Signal(8, reset=127)
        self.beta = Signal(8, reset=100)
        self.sigma2 = Signal(8, reset=100)
        self.tx_src = Signal(1, reset=1)
        self.tx_en = Signal(1, reset=1)
        self.noise_en = Signal(1, reset=0)

        tx_sub = Signal(18)
        tx_mul = Signal(36)
        x = Signal(9)

        self.sync += [
            tx_sub.eq(3958 - touchscreen.x),
            tx_mul.eq(tx_sub * 127),
            x.eq(tx_mul >> 10)
        ]

        ty_sub = Signal(18)
        ty_mul = Signal(36)
        y = Signal(9)

        self.sync += [
            ty_sub.eq(touchscreen.y - 377),
            ty_mul.eq(ty_sub * 79),
            y.eq(ty_mul >> 10)
        ]

        pen = Signal()
        self.sync += pen.eq(touchscreen.pen)

        self.sync += If(
            pen,
            If(
                # Target inside reticule
                (x > 7) & (x < 264) & (y > 7) & (y < 264),
                self.thresh_x.eq(x - 8),
                self.thresh_y.eq(y - 8)
            ).Elif(
                # Beta slider
                (y > 47) & (y < 64) & (x > 279) & (x < 464),
                self.beta.eq(x - 279)
            ).Elif(
                # Sigma slider
                (y > 49) & (y < 96) & (x > 279) & (x < 464),
                self.sigma2.eq(x - 279)
            ).Elif(
                # tx src toggle left
                (y > 111) & (y < 128) & (x > 279) & (x < 340),
                self.tx_src.eq(0)
            ).Elif(
                # tx src toggle right
                (y > 111) & (y < 128) & (x > 404) & (x < 464),
                self.tx_src.eq(1)
            ).Elif(
                # tx en toggle off
                (y > 143) & (y < 160) & (x > 279) & (x < 340),
                self.tx_en.eq(0)
            ).Elif(
                # tx en toggle on
                (y > 143) & (y < 160) & (x > 404) & (x < 464),
                self.tx_en.eq(1)
            ).Elif(
                # noise en toggle off
                (y > 175) & (y < 192) & (x > 279) & (x < 340),
                self.noise_en.eq(0)
            ).Elif(
                # noise en toggle on
                (y > 175) & (y < 192) & (x > 404) & (x < 464),
                self.noise_en.eq(1)
            )
        )
