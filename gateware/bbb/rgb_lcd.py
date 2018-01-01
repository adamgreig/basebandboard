"""
24bit RBG-interface LCD controller for DE0-Nano.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue, ClockDomain


class RGBLCD(Module):
    def __init__(self, lcd):
        """
        `lcd` has `data`, `pclk`, `hsync`, `vsync`, `de` members.
        """

        # Make up a pclk divider
        divider = Signal(4)
        self.sync += divider.eq(divider + 1)
        self.clock_domains.pclk = ClockDomain("pclk")
        self.comb += self.pclk.clk.eq(divider[3])
        self.comb += lcd.pclk.eq(self.pclk.clk)

        pcount = Signal(10)
        hcount = Signal(10)
        self.sync.pclk += (
            If(
                pcount == 525,
                pcount.eq(0),
                If(
                    hcount == 288,
                    hcount.eq(0))
                .Else(hcount.eq(hcount + 1)))
            .Else(pcount.eq(pcount + 1))
        )

        self.sync.pclk += If(pcount == 0,
                             lcd.hsync.eq(1)).Else(lcd.hsync.eq(0))
        self.sync.pclk += If((pcount > 40) & (pcount < 520) &
                             (hcount > 8) & (hcount < 280),
                             lcd.de.eq(1)).Else(lcd.de.eq(0))
        self.sync.pclk += If(hcount == 0,
                             lcd.vsync.eq(1)).Else(lcd.vsync.eq(0))

        self.comb += lcd.data[0:8].eq(pcount[1:9] - 20)
        self.comb += lcd.data[8:16].eq(hcount[1:9] - 4)
        self.comb += lcd.data[16:24].eq(0b00000000)
