import numpy as np

from migen import (Module, Signal, Memory, ClockDomain, ClockDomainsRenamer,
                   Cat, READ_FIRST)

from bbb.platform import BBBPlatform, PLL
from bbb.tx import TX
from bbb.rx import RX
from bbb.nco import NCO
from bbb.uart import UARTTxFromMemory, DataToMem
from bbb.rgb_lcd import RGBLCD, DoubleBuffer, AR1021TouchController
from bbb.ui import UIDisplay, UIController
from bbb.sdram import SDRAM
from bbb.axi3 import AXI3ReadPort, AXI3WritePort


class ADCTest(Module):
    def __init__(self, platform):
        self.clk50 = platform.request("clk50")
        self.sys_pll = PLL(20, "sys", 1, 2)
        self.submodules += self.sys_pll
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += self.sys_pll.clk_in.eq(self.clk50)
        self.comb += self.sys.clk.eq(self.sys_pll.clk_out)

        self.adc_b = plat.request("adc_b")
        self.comb += self.adc_b.clk.eq(~self.sys.clk)

        self.dac = plat.request("dac")
        self.comb += self.dac.clk.eq(self.sys.clk)

        self.comb += self.dac.data[2:12].eq(self.adc_b.data)
        self.comb += self.dac.data[0].eq(self.adc_b.data[0])
        self.comb += self.dac.data[1].eq(self.adc_b.data[0])


class NCOTest(Module):
    def __init__(self, platform):
        self.clk50 = platform.request("clk50")
        self.sys_pll = PLL(20, "sys", 1, 2)
        self.submodules += self.sys_pll
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += self.sys_pll.clk_in.eq(self.clk50)
        self.comb += self.sys.clk.eq(self.sys_pll.clk_out)

        self.dac = plat.request("dac")
        self.comb += self.dac.clk.eq(self.sys.clk)

        self.adc_b = plat.request("adc_b")
        self.comb += self.adc_b.clk.eq(~self.sys.clk)

        self.fcw = Signal(24, reset=2**20)
        self.am = Signal((16, False), reset=2**14)
        self.fm = Signal((24, True), reset=0)
        self.pm = Signal((10, True), reset=0)
        self.nco = NCO(self.fcw, self.am, self.fm, self.pm)
        self.submodules += self.nco
        self.comb += self.dac.data.eq(self.nco.x[3:16])

        self.comb += self.fm.eq(self.adc_b.data << 8)


class UARTTest(Module):
    def __init__(self, platform):
        data = ["Hello, World! {:03}\r\n".format(x) for x in range(123)]
        data = "".join(data)
        mem = Memory(8, len(data), [ord(c) for c in data])
        port = mem.get_port(mode=READ_FIRST)
        self.specials += [mem, port]

        baud = 1000000
        divider = 50000000 // baud
        trigger = Signal()
        self.submodules.uart = UARTTxFromMemory(
            divider, port, 8, 0, len(data), trigger)

        key = plat.request("key")
        self.comb += trigger.eq(~key)

        gpio = plat.request("gpio_1")
        self.comb += gpio[0].eq(self.uart.tx_out)


class LCDTest(Module):
    def __init__(self, platform):
        # Set up clocks.
        # PLL the 50MHz to 100MHz, and PLL a -3ns phase shift for the SDRAM.
        self.clk50 = platform.request("clk50")
        sys_pll = PLL(20, "sys", 1, 2)
        self.submodules += sys_pll
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += sys_pll.clk_in.eq(self.clk50)
        self.comb += self.sys.clk.eq(sys_pll.clk_out)

        sdram_pll = PLL(20, "sdram", 1, 2, "ZERO_DELAY_BUFFER", -3000)
        self.submodules += sdram_pll
        self.clock_domains.sys_ps = ClockDomain("sys_ps")
        self.comb += sdram_pll.clk_in.eq(self.clk50)
        self.comb += self.sys_ps.clk.eq(sdram_pll.clk_out)
        self.comb += platform.request("sdram_clock").eq(self.sys_ps.clk)

        # SDRAM controller
        timings = {
            "powerup": 150*200,
            "t_cac": 2,
            "t_rcd": 3,
            "t_rc": 10,
            "t_ras": 7,
            "t_rp": 3,
            "t_mrd": 3,
            "t_ref": 750,
        }
        axirp = AXI3ReadPort(1, 25, 32)
        axiwp = AXI3WritePort(1, 25, 32)
        sdram = plat.request("sdram")
        sdramctl = SDRAM(axirp, axiwp, sdram, timings)
        self.submodules += sdramctl
        self.specials += sdramctl.dqt.get_tristate(sdram.dq)

        # LCD controller
        display = platform.request("lcd")
        backlight = platform.request("lcd_backlight")
        self.comb += backlight.eq(1)
        self.comb += display.disp.eq(1)
        frontbuf = Signal(25)
        self.submodules.lcd = RGBLCD(display, axirp, frontbuf)

        # Touchscreen controller
        touchscreen = platform.request("touchscreen")
        self.submodules.touch = AR1021TouchController(touchscreen)
        led = platform.request("user_led")
        self.comb += led.eq(~touchscreen.cs)

        # UI Controller
        self.submodules.uicontroller = UIController(self.touch)

        # UI display
        backbuf = Signal(25)
        bufswap = Signal()
        self.submodules.uidisplay = UIDisplay(
            None, axiwp, backbuf, bufswap,
            self.uicontroller.thresh_x, self.uicontroller.thresh_y,
            self.uicontroller.beta, self.uicontroller.sigma2,
            self.uicontroller.tx_src, self.uicontroller.tx_en,
            self.uicontroller.noise_en)

        # Double buffer controller for LCD
        fb1 = Signal(25, reset=0)
        fb2 = Signal(25, reset=(1 << 20))
        self.submodules.dblbuf = DoubleBuffer(
            fb1, fb2, display.vsync, self.uidisplay.drawn)
        self.comb += [
            frontbuf.eq(self.dblbuf.front),
            backbuf.eq(self.dblbuf.back),
            bufswap.eq(self.dblbuf.swapped)
        ]

        # Make a BRAM to fill with touchscreen data and dump over UART
        uart_ram = Memory(32, 4)
        uartreadport = uart_ram.get_port(mode=1)
        uartwriteport = uart_ram.get_port(write_capable=True, mode=0)
        self.specials += [uart_ram, uartreadport, uartwriteport]

        touch_x = Signal(16)
        self.comb += touch_x.eq(self.touch.x)
        touch_y = Signal(16)
        self.comb += touch_y.eq(self.touch.y)
        touchdata = Signal(32)
        self.comb += touchdata.eq(Cat(touch_x, touch_y))

        storetrig = Signal()
        self.sync += storetrig.eq(self.touch.newdata)
        touch2ram = DataToMem(touchdata, uartwriteport, 2, storetrig)
        self.submodules += touch2ram

        uarttrig = Signal()
        self.sync += uarttrig.eq(storetrig)
        ram2uart = UARTTxFromMemory(100, uartreadport, 32, 0, 2, uarttrig)
        self.submodules += ram2uart
        uart = platform.request("uart")
        self.comb += uart.eq(ram2uart.tx_out)


class Top(Module):
    def __init__(self, platform):
        # Set up clocking.
        self.clk50 = platform.request("clk50")

        # PLL for SDRAM with -3ns delay
        self.submodules.sdram_pll = PLL(
            20, "sdram", 1, 2, "ZERO_DELAY_BUFFER", -3000)
        self.clock_domains.sys_ps = ClockDomain("sys_ps")
        self.comb += self.sdram_pll.clk_in.eq(self.clk50)
        self.comb += self.sys_ps.clk.eq(self.sdram_pll.clk_out)
        self.comb += platform.request("sdram_clock").eq(self.sys_ps.clk)

        # PLL for transmitter clock
        # (1, 1) gives a 50MHz clock for 50/8=6.25Mbps
        # Go up to (1, 4) for a 200MHz clock and 200/8=25Mbps
        self.submodules.tx_pll = PLL(20, "tx", 1, 1)
        self.clock_domains.tx = ClockDomain("tx")
        self.comb += self.tx_pll.clk_in.eq(self.clk50)
        self.comb += self.tx.clk.eq(self.tx_pll.clk_out)

        # PLL for receiver clock
        # (1, 2) gives a 100MHz clock, the max for the ADC
        # 100MHz RX and 50MHz TX gives 16 ADC samples per TX bit
        self.submodules.rx_pll = PLL(20, "rx", 1, 2)
        self.clock_domains.rx = ClockDomain("rx")
        self.comb += self.rx_pll.clk_in.eq(self.clk50)
        self.comb += self.rx.clk.eq(self.rx_pll.clk_out)
        adc_samples_per_tx_bit = 16

        # Clock the rest of the system logic off the RX PLL
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += self.sys.clk.eq(self.rx_pll.clk_out)

        # SDRAM controller
        timings = {
            "powerup": 150*200,
            "t_cac": 2,
            "t_rcd": 3,
            "t_rc": 10,
            "t_ras": 7,
            "t_rp": 3,
            "t_mrd": 3,
            "t_ref": 750,
        }
        axirp = AXI3ReadPort(1, 25, 32)
        axiwp = AXI3WritePort(1, 25, 32)
        sdram = plat.request("sdram")
        sdramctl = SDRAM(axirp, axiwp, sdram, timings)
        self.submodules += sdramctl
        self.specials += sdramctl.dqt.get_tristate(sdram.dq)

        # LCD controller
        display = platform.request("lcd")
        backlight = platform.request("lcd_backlight")
        self.comb += backlight.eq(1)
        self.comb += display.disp.eq(1)
        frontbuf = Signal(25)
        self.submodules.lcd = RGBLCD(display, axirp, frontbuf)

        # Touchscreen controller
        touchscreen = platform.request("touchscreen")
        self.submodules.touch = AR1021TouchController(touchscreen)

        # UI Controller
        self.submodules.uicontroller = UIController(self.touch)

        # UI display
        backbuf = Signal(25)
        bufswap = Signal()
        self.submodules.uidisplay = UIDisplay(
            None, axiwp, backbuf, bufswap,
            self.uicontroller.thresh_x, self.uicontroller.thresh_y,
            self.uicontroller.beta, self.uicontroller.sigma2,
            self.uicontroller.tx_src, self.uicontroller.tx_en,
            self.uicontroller.noise_en)

        # Double buffer controller for LCD
        fb1 = Signal(25, reset=0)
        fb2 = Signal(25, reset=(1 << 20))
        self.submodules.dblbuf = DoubleBuffer(
            fb1, fb2, display.vsync, self.uidisplay.drawn)
        self.comb += [
            frontbuf.eq(self.dblbuf.front),
            backbuf.eq(self.dblbuf.back),
            bufswap.eq(self.dblbuf.swapped)
        ]

        # Set up the DAC and ADC peripherals
        self.dac = plat.request("dac")
        self.comb += self.dac.clk.eq(self.tx.clk)
        self.adc_b = plat.request("adc_b")
        self.comb += self.adc_b.clk.eq(~self.rx.clk)

        # Create a transmitter.
        self.prbs_k = 31
        self.submodules.tx = ClockDomainsRenamer("tx")(
            TX(self.prbs_k,
               self.uicontroller.tx_en,
               self.uicontroller.tx_src,
               self.uicontroller.beta[2:7],
               self.uicontroller.noise_en,
               self.uicontroller.sigma2[3:7]))

        # Wire the transmitter up
        self.comb += self.dac.data.eq(self.tx.x << 2)

        # Create a receiver.
        delay_bits = int(np.log2(adc_samples_per_tx_bit))
        self.sample_delay = Signal(delay_bits, reset=0)
        self.submodules.rx = ClockDomainsRenamer("rx")(
            RX(self.prbs_k, self.sample_delay,
               adc_samples_per_tx_bit, self.adc_b.data))

        # Output the bit clock, PRBS, etc
        leds = [plat.request("user_led", i) for i in range(8)]

        self.comb += [
            leds[6].eq(self.rx.prbsdet.reload),
            leds[7].eq(self.rx.err),
        ]


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
