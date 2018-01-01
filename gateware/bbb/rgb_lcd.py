"""
24bit RBG-interface LCD controller for DE0-Nano.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, Cat, If, ClockDomain, Memory
from .axi3 import AXI3ToBRAM, BRAMToAXI3


class RGBLCD(Module):
    """
    RGB LCD controller.
    Reads a frame buffer over AXI3 starting from the given address and
    outputs it to the LCD.

    Currently hardcoded for 272x480 24-bit RGB LCDs.
    """
    def __init__(self, lcd, axi3_port, start_addr):
        """
        `lcd`: has `data`, `pclk`, `hsync`, `vsync`, `de` members.
        `axi3_port`: an AXI3ReadPort connected to memory etc. will be mastered
                     to command reads of screen data.
        `start_addr`: the initial address of the frame buffer (for axi3)
        """
        # Make up a pclk divider
        divider = Signal(4)
        self.sync += divider.eq(divider + 1)
        self.clock_domains.pclk = ClockDomain("pclk")
        self.comb += self.pclk.clk.eq(divider[3])
        self.comb += lcd.pclk.eq(~self.pclk.clk)

        # Store current col (pclk) and row (hsync) counts
        pcount = Signal(10)
        hcount = Signal(10)

        # Make a counter to track the address of the current line,
        # offset for the vertical back porch and compensate for latency.
        axiaddr = Signal(start_addr.nbits)
        self.comb += axiaddr.eq(start_addr + (4*480)*(hcount - 8))

        # Make a BRAM to store one line worth
        bram = Memory(32, 512)
        bram_rp = bram.get_port()
        bram_wp = bram.get_port(write_capable=True)
        self.specials += [bram, bram_rp, bram_wp]

        # Set up an AXI3 master to read data into the BRAM when triggered
        # by the HSYNC signal
        axitrig = Signal()
        self.comb += axitrig.eq((lcd.hsync == 0)
                                & (hcount > 7) & (hcount < 281))
        axi_to_bram = AXI3ToBRAM(axi3_port, bram_wp, axitrig, axiaddr,
                                 484, axi3_burst_length=4)
        self.submodules += axi_to_bram

        # Count up pclks and hsyncs, resetting at the end of each period
        self.sync.pclk += (
            If(
                pcount == 524,
                pcount.eq(0),
                If(
                    hcount == 287,
                    hcount.eq(0))
                .Else(hcount.eq(hcount + 1)))
            .Else(pcount.eq(pcount + 1))
        )

        # Output hsyncs at the start of each line
        self.sync.pclk += If(pcount == 0,
                             lcd.hsync.eq(0)).Else(lcd.hsync.eq(1))
        # Output DE during the active area of each line
        self.sync.pclk += If((pcount > 39) & (pcount < 521) &
                             (hcount > 7) & (hcount < 281),
                             lcd.de.eq(1)).Else(lcd.de.eq(0))
        # Output vsyncs at the start of each frame
        self.sync.pclk += If(hcount == 0,
                             lcd.vsync.eq(0)).Else(lcd.vsync.eq(1))

        # Pixel data is the output of the BRAM at the current pixel count,
        # adjusted to compensate for the back porch and memory read latency
        self.comb += bram_rp.adr.eq(pcount - 41)
        self.comb += lcd.data.eq(bram_rp.dat_r[0:24])


class LCDPatternGenerator(Module):
    def __init__(self, axi3_port, start_addr):
        """
        `axi3_port`: an AXI3WritePort connected to memory etc. will be mastered
                     to command writes of test pattern data.
        `start_addr`: the initial address of the frame buffer.
        """
        # Maintain row and column counters
        row = Signal(9, reset=136)
        col = Signal(9)
        run = Signal()
        self.sync += If(
            col == 510,
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

        # Make a BRAM to store one line worth.
        # We give it a little slack at the end to simplify timing.
        red = 0b00000000111111110000000000000000
        grn = 0b11111111000000000000000000000000
        blu = 0b00000000000000000000000011111111
        wte = 0b11111111111111110000000011111111
        initial = [wte]*2 + [0, 0, 0, grn, 0, 0, 0]*68 + [blu]*2
        bram = Memory(32, 512, initial)
        bram_rp = bram.get_port()
        bram_wp = bram.get_port(write_capable=True)
        self.specials += [bram, bram_rp, bram_wp]
        self.comb += bram_wp.we.eq(0)

        # Make a counter to track the address of the current line,
        # offset for the vertical back porch and compensate for latency.
        axiaddr = Signal(start_addr.nbits)
        self.comb += axiaddr.eq(start_addr + (4*480)*row)

        # Set up an AXI3 master to write data into the BRAM
        bram_to_axi = BRAMToAXI3(axi3_port, bram_rp, col == 480, axiaddr,
                                 484, axi3_burst_length=4)
        self.comb += run.eq(bram_to_axi.ready)
        self.submodules += bram_to_axi

        # Generate test pattern
        red = Signal(8)
        grn = Signal(8)
        blu = Signal(8)
        #self.comb += bram_wp.dat_w[0:24].eq(Cat(red, grn, blu))
        #self.comb += bram_wp.adr.eq(col - 8)
        #self.comb += bram_wp.we.eq(1)

        #self.comb += red.eq(((col & 0b1111)) << 7)
        #self.comb += grn.eq(((col & 0b1111)) << 7)
        #self.comb += blu.eq(((col & 0b1111)) << 7)

        self.comb += red.eq(0b11111111)
        self.comb += grn.eq(0b11111111)
        self.comb += blu.eq(0b00000000)
