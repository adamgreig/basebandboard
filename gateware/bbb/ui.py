"""
User interface.

Copyright 2018 Adam Greig
"""

from migen import Module, Signal, If, FSM, NextValue, NextState, Memory, Mux
from migen import Cat
from .axi3 import AXI3ToFromBRAM
import numpy as np


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
        cyn = grn | blu
        ylw = red | grn
        mgn = red | blu

        char = Signal(7)
        fontrow = Signal(4)
        fontcol = Signal(3)
        fontfg = Signal(24)
        fontbg = Signal(24)
        fontpx = Signal(24)
        self.submodules.font = UIFont(
            char, fontrow, fontcol, fontfg, fontbg)
        self.comb += [
            fontrow.eq(row & 0b1111),
            fontcol.eq(col & 0b111),
            fontpx.eq(self.font.pixel),
        ]

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
                (col > 359) & (col < (359 + 4*8)),
                fontfg.eq(blk),
                If(
                    col < (280 + beta),
                    fontbg.eq(cyn))
                .Else(
                    fontbg.eq(wte)),
                If(
                    col > 360,
                    self.data.eq(fontpx),
                ).Else(
                    If(
                        col < (280 + beta),
                        self.data.eq(cyn)
                    ).Else(
                        self.data.eq(wte)
                    )
                ),
                If(
                    col < (359 + 1*8),
                    char.eq(ord('B')),
                ).Elif(
                    col < (359 + 2*8),
                    char.eq(ord('E')),
                ).Elif(
                    col < (359 + 3*8),
                    char.eq(ord('T')),
                ).Else(
                    char.eq(ord('A')),
                )
            ).Elif(
                col < (280 + beta),
                self.data.eq(cyn)
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
                (col > 359) & (col < (359 + 5*8)),
                fontfg.eq(blk),
                If(
                    col < (280 + sigma2),
                    fontbg.eq(cyn)
                ).Else(
                    fontbg.eq(wte)
                ),
                If(
                    col > 360,
                    self.data.eq(fontpx),
                ).Else(
                    If(
                        col < (280 + sigma2),
                        self.data.eq(cyn)
                    ).Else(
                        self.data.eq(wte)
                    )
                ),
                If(
                    col < (359 + 1*8),
                    char.eq(ord('S')),
                ).Elif(
                    col < (359 + 2*8),
                    char.eq(ord('I')),
                ).Elif(
                    col < (359 + 3*8),
                    char.eq(ord('G')),
                ).Elif(
                    col < (359 + 4*8),
                    char.eq(ord('M')),
                ).Else(
                    char.eq(ord('A')),
                )
            ).Elif(
                col < (280 + sigma2),
                self.data.eq(cyn)
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
                If(
                    tx_src,
                    fontbg.eq(gry),
                    fontfg.eq(wte),
                ).Else(
                    fontbg.eq(ylw),
                    fontfg.eq(blk),
                ),
                If(
                    col > 280,
                    self.data.eq(fontpx),
                ).Else(
                    If(
                        tx_src,
                        self.data.eq(gry),
                    ).Else(
                        self.data.eq(ylw),
                    )
                ),
                If(
                    col < (279 + 1*8),
                    char.eq(ord('P')),
                ).Elif(
                    col < (279 + 2*8),
                    char.eq(ord('U')),
                ).Elif(
                    col < (279 + 3*8),
                    char.eq(ord('L')),
                ).Elif(
                    col < (279 + 4*8),
                    char.eq(ord('S')),
                ).Elif(
                    col < (279 + 5*8),
                    char.eq(ord('E')),
                ).Else(
                    char.eq(ord(' ')),
                )
            ).Elif(
                col < 360,
                self.data.eq(blk),
                fontbg.eq(blk),
            ).Elif(
                col < 384,
                self.data.eq(fontpx),
                fontbg.eq(blk),
                fontfg.eq(wte),
                If(
                    col < (359 + 1*8),
                    char.eq(ord('S')),
                ).Elif(
                    col < (359 + 2*8),
                    char.eq(ord('R')),
                ).Else(
                    char.eq(ord('C')),
                )
            ).Elif(
                col < 408,
                self.data.eq(blk),
                fontbg.eq(blk),
            ).Elif(
                col < 464,
                If(
                    tx_src,
                    fontbg.eq(mgn),
                    fontfg.eq(blk),
                ).Else(
                    fontbg.eq(gry),
                    fontfg.eq(wte),
                ),
                If(
                    col > 409,
                    self.data.eq(fontpx),
                ).Else(
                    If(
                        tx_src,
                        self.data.eq(mgn),
                    ).Else(
                        self.data.eq(gry),
                    )
                ),
                If(
                    col < (407 + 1*8),
                    char.eq(ord('P')),
                ).Elif(
                    col < (407 + 2*8),
                    char.eq(ord('R')),
                ).Elif(
                    col < (407 + 3*8),
                    char.eq(ord('B')),
                ).Elif(
                    col < (407 + 4*8),
                    char.eq(ord('S')),
                ).Else(
                    char.eq(ord(' ')),
                )
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
                col < 352,
                self.data.eq(blk),
                fontbg.eq(blk),
                char.eq(ord(' ')),
            ).Elif(
                col < 392,
                self.data.eq(fontpx),
                fontbg.eq(blk),
                fontfg.eq(wte),
                If(
                    col < (351 + 1*8),
                    char.eq(ord('T'))
                ).Elif(
                    col < (351 + 2*8),
                    char.eq(ord('X'))
                ).Elif(
                    col < (351 + 3*8),
                    char.eq(ord(' '))
                ).Elif(
                    col < (351 + 4*8),
                    char.eq(ord('E'))
                ).Else(
                    char.eq(ord('N'))
                )
            ).Elif(
                col < 408,
                self.data.eq(blk),
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
                col < 352,
                self.data.eq(blk),
                fontbg.eq(blk),
            ).Elif(
                col < 392,
                self.data.eq(fontpx),
                fontbg.eq(blk),
                fontfg.eq(wte),
                If(
                    col < (351 + 1*8),
                    char.eq(ord('N'))
                ).Elif(
                    col < (351 + 2*8),
                    char.eq(ord('O'))
                ).Elif(
                    col < (351 + 3*8),
                    char.eq(ord('I'))
                ).Elif(
                    col < (351 + 4*8),
                    char.eq(ord('S'))
                ).Else(
                    char.eq(ord('E'))
                )
            ).Elif(
                col < 408,
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
        self.thresh_x = Signal(8, reset=128)
        self.thresh_y = Signal(8, reset=128)
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


class UIFont(Module):
    def __init__(self, char, row, col, fgcolour, bgcolour):
        """
        `char`: 7 bit character select. ASCII.
        `row`: 4 bit row select.
        `col`: 3 bit col select.
        `fgcolour`: 24 bit colour for text.
        `bgcolour`: 24 bit colour for background.
        `self.pixel`: 24-bit RGB output.
        """
        font = np.load("font.npz")['font'].tolist()
        bram = Memory(1, 2**14, font)
        port = bram.get_port()
        self.specials += [bram, port]
        self.comb += port.adr.eq((char << 7) | (row << 3) | col)
        self.pixel = Signal(24)
        self.comb += self.pixel.eq(Mux(port.dat_r, fgcolour, bgcolour))
