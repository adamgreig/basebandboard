"""
24bit RBG-interface LCD controller for DE0-Nano.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, Cat, If, ClockDomain, Memory, Array, Cat
from migen import FSM, NextValue, NextState, Mux
from .axi3 import AXI3ToBRAM, BRAMToAXI3


class RGBLCD(Module):
    """
    RGB LCD controller.
    Reads a frame buffer over AXI3 starting from the given address and
    outputs it to the LCD.

    Currently hardcoded for 272x480 24-bit RGB LCDs.
    """
    def __init__(self, lcd, axi3_port, framebuf):
        """
        `lcd`: has `data`, `pclk`, `hsync`, `vsync`, `de` members.
        `axi3_port`: an AXI3ReadPort connected to memory etc. will be mastered
                     to command reads of screen data.
        `framebuf`: the initial address of the frame buffer (for axi3)
        """
        rows = 272
        cols = 480
        hbp = 40
        hfp = 5
        vbp = 8
        vfp = 8

        # Make up a pclk divider
        divider = Signal(4)
        self.sync += divider.eq(divider + 1)
        self.clock_domains.pclk = ClockDomain("pclk")
        self.comb += self.pclk.clk.eq(divider[3])
        self.comb += lcd.pclk.eq(~self.pclk.clk)

        # Store current col (pclk) and row (hsync) counts
        pcount = Signal(max=cols+hbp+hfp+1)
        hcount = Signal(max=rows+vbp+vfp+1)

        # Make a BRAM to store one line worth
        bram = Memory(32, cols)
        bram_rp = bram.get_port()
        bram_wp = bram.get_port(write_capable=True)
        self.specials += [bram, bram_rp, bram_wp]

        # Pixel data is the output of the BRAM at the current pixel count,
        # adjusted to compensate for the back porch and memory read latency
        self.comb += bram_rp.adr.eq(pcount - hbp - 1)
        self.comb += lcd.data.eq(bram_rp.dat_r[0:24])

        # Set up an AXI3 master to read data into the BRAM when triggered
        # by the HSYNC signal
        axitrig = Signal()
        self.comb += axitrig.eq((lcd.hsync == 0)
                                & (hcount >= vbp) & (hcount < (rows + vbp)))
        axiaddr = Signal(framebuf.nbits)
        self.comb += axiaddr.eq(framebuf + (4*cols)*(hcount - vbp))
        axi_to_bram = AXI3ToBRAM(axi3_port, bram_wp, axitrig, axiaddr,
                                 cols, axi3_burst_length=16)
        self.submodules += axi_to_bram

        # Count up pclks and hsyncs, resetting at the end of each period
        self.sync.pclk += (
            If(
                pcount == cols + hbp + hfp - 1,
                pcount.eq(0),
                If(
                    hcount == rows + vbp + vfp - 1,
                    hcount.eq(0))
                .Else(hcount.eq(hcount + 1)))
            .Else(pcount.eq(pcount + 1))
        )

        # Output hsyncs at the start of each line
        self.sync.pclk += If(pcount == 0,
                             lcd.hsync.eq(0)).Else(lcd.hsync.eq(1))
        # Output DE during the active area of each line
        self.sync.pclk += If((pcount >= hbp) & (pcount < (cols + hbp)) &
                             (hcount >= vbp) & (hcount < (rows + vbp)),
                             lcd.de.eq(1)).Else(lcd.de.eq(0))
        # Output vsyncs at the start of each frame
        self.sync.pclk += If(hcount == 0,
                             lcd.vsync.eq(0)).Else(lcd.vsync.eq(1))


class DoubleBuffer(Module):
    """
    Manages two buffers, so the front buffer can be displayed and then
    swapped with a back buffer when it has been drawn.
    """
    def __init__(self, framebuf1, framebuf2, hsync, drawn):
        """
        `framebuf1`: address of the first framebuf
        `framebuf2`: address of the second framebuf
        `hsync`: hsync output from LCD
        `drawn`: drawing-complete output from drawer

        Outputs `self.swapped` which pulses whenever the buffers swap.
        """
        self.swapped = Signal()

        assert(framebuf1.nbits == framebuf2.nbits)
        front = Signal(framebuf1.nbits)
        back = Signal(framebuf1.nbits)
        sel = Signal()

        # Output whichever is the correct address based on the sel line
        self.sync += front.eq(Mux(sel, framebuf1, framebuf2))
        self.sync += back.eq(Mux(sel, framebuf2, framebuf1))

        # Shorten hsync pulse
        hsync_prev = Signal()
        hsync_pulse = Signal()
        self.sync += hsync_prev.eq(hsync)
        self.sync += hsync_pulse.eq(hsync & ~hsync_prev)

        self.sync += sel.eq((hsync_pulse & drawn) ^ sel)
        self.sync += self.swapped.eq(hsync_pulse & drawn)


class LCDPatternGenerator(Module):
    def __init__(self, axi3_port, framebuf, ts):
        """
        `axi3_port`: an AXI3WritePort connected to memory etc. will be mastered
                     to command writes of test pattern data.
        `framebuf`: the initial address of the frame buffer.
        `ts`: touchscreen
        """
        # Maintain row and column counters
        vsd = Signal(9)
        row = Signal(9)
        hsd = Signal(9)
        col = Signal(9)
        run = Signal()
        self.sync += If(
            hsd == 480 + 16 - 1,
            hsd.eq(0),
            If(
                vsd == 280 + 8 - 1,
                vsd.eq(0),
            ).Else(
                vsd.eq(vsd + 1)
            )
        ).Else(
            hsd.eq(hsd + run)
        )
        self.comb += col.eq(hsd - 16)
        self.comb += row.eq(vsd - 8)

        # Make a BRAM to store one line worth.
        # We give it a little slack at the end to simplify timing.
        bram = Memory(32, 512)
        bram_rp = bram.get_port()
        bram_wp = bram.get_port(write_capable=True)
        self.specials += [bram, bram_rp, bram_wp]
        self.comb += bram_wp.we.eq(0)

        # Make a counter to track the address of the current line,
        # offset for the vertical back porch and compensate for latency.
        axiaddr = Signal(framebuf.nbits)
        self.comb += axiaddr.eq(framebuf + (4*480)*(row - 1))

        # Set up an AXI3 master to write data into the BRAM
        axitrigger = Signal()
        self.sync += axitrigger.eq(col == 480 - 1)
        bram_to_axi = BRAMToAXI3(axi3_port, bram_rp, axitrigger, axiaddr,
                                 480, axi3_burst_length=16)
        self.comb += run.eq(bram_to_axi.ready)
        self.submodules += bram_to_axi

        data = Signal(24)
        self.comb += bram_wp.adr.eq(col)
        self.comb += bram_wp.we.eq(1)
        self.comb += bram_wp.dat_w[0:24].eq(data)

        tx = Signal(9)
        ty = Signal(9)
        tp = Signal()
        self.sync += tx.eq(512 - (ts.x >> 3))
        self.sync += ty.eq(ts.y >> 4)
        self.sync += tp.eq(ts.pen)

        near_tx = Signal()
        near_ty = Signal()
        self.comb += near_tx.eq(
            ((col >= tx) & (col - tx < 8))
            |
            ((col <= tx) & (tx - col < 8))
        )
        self.comb += near_ty.eq(
            ((row >= ty) & (row - ty < 8))
            |
            ((row <= ty) & (ty - row < 8))
        )

        red = 0b00000000000000000000000011111111
        grn = 0b00000000000000001111111100000000
        blu = 0b00000000111111110000000000000000
        wte = 0b00000000111111111111111111111111
        blk = 0b00000000000000000000000000000000

        self.comb += If(
            (tp == 0) & near_tx & near_ty,
            data.eq(red)
        ).Elif(
            (tp == 1) & near_tx & near_ty,
            data.eq(blu)
        ).Elif(
            (col == 0) | (col == 479) | (row == 0) | (row == 271),
            data.eq(wte)
        ).Elif(
            (col & 0b111 == 0) | (row & 0b111 == 0),
            data.eq(grn)
        ).Else(
            data.eq(blk)
        )


class AR1021TouchController(Module):
    """
    Receive touchscreen events from an AR1021 over SPI.
    """
    def __init__(self, touchscreen):
        # Output signals
        self.pen = Signal()
        self.x = Signal(12)
        self.y = Signal(12)
        self.newdata = Signal()

        # Timing parameters
        clkfreq = 100e6
        interbyte_delay = 50e-6
        spi_clkfreq = 100e3
        bytedelay = int(clkfreq * interbyte_delay)
        bitdelay = int(clkfreq / spi_clkfreq)//2
        delaycnt = Signal(max=bytedelay+1)
        clkcnt = Signal(max=bitdelay+1)

        # Manage accumulating the input data
        data = Signal(5*8)
        data_a = Array(data)
        bitno = Signal(4)
        byteno = Signal(3)

        # Synchronise inputs
        interrupt = Signal()
        miso = Signal()
        self.sync += interrupt.eq(touchscreen.int)
        self.sync += miso.eq(touchscreen.miso)

        self.submodules.fsm = FSM()
        self.fsm.act(
            "IDLE",
            touchscreen.cs.eq(1),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Reset counters
            NextValue(delaycnt, 0),
            NextValue(byteno, 0),

            # Transition when we see an interrupt from the controller
            If(interrupt, NextState("WAIT"))
        )
        self.fsm.act(
            "WAIT",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Wait for the inter-byte delay timer
            NextValue(clkcnt, 0),
            NextValue(bitno, 0),
            NextValue(delaycnt, delaycnt + 1),
            If(delaycnt >= bytedelay, NextState("CLKH"))
        )
        self.fsm.act(
            "CLKH",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(1),
            touchscreen.mosi.eq(0),

            # Wait for half the SPI clock period
            NextValue(delaycnt, 0),
            NextValue(clkcnt, clkcnt + 1),
            If(clkcnt == bitdelay, NextState("READBIT")),
        )
        self.fsm.act(
            "READBIT",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Reset SPI clock counter
            NextValue(clkcnt, 0),

            # Store this bit (at the clock falling edge)
            NextValue(data_a[byteno*8+bitno], miso),
            NextValue(bitno, bitno + 1),
            NextState("CLKL"),
        )
        self.fsm.act(
            "CLKL",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Wait for half the SPI clock period, minus one for previous state.
            If(clkcnt == bitdelay - 1, (
                NextValue(clkcnt, 0),
                # Either read the next bit or move on to the next byte.
                If(bitno < 8, NextState("CLKH"))
                .Else(NextState("BYTE"))
            )).Else(NextValue(clkcnt, clkcnt + 1))
        )
        self.fsm.act(
            "BYTE",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Incremenet byte counter, then either read another byte or finish.
            NextValue(byteno, byteno + 1),
            If(byteno < 4, NextState("WAIT")).Else(NextState("END"))
        )
        self.fsm.act(
            "END",
            touchscreen.cs.eq(0),
            touchscreen.sclk.eq(0),
            touchscreen.mosi.eq(0),

            # Assign loaded data to output registers
            NextValue(self.pen, data[7]),
            NextValue(self.x, Cat(
                data[15], data[14], data[13], data[12], data[11], data[10],
                data[9], data[23], data[22], data[21], data[20], data[19])),
            NextValue(self.y, Cat(
                data[31], data[30], data[29], data[28], data[27], data[26],
                data[25], data[39], data[38], data[37], data[36], data[35])),

            # Restart the state machine
            NextState("IDLE"),
        )

        # Output a pulse at the end of each packet
        self.newdata = self.fsm.ongoing("END")
