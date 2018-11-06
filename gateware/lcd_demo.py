from migen import Module, Signal, ClockDomain, Memory, Cat
from bbb.platform import BBBPlatform, PLL
from bbb.rgb_lcd import RGBLCD, DoubleBuffer, AR1021TouchController
from bbb.ui import UIDisplay, UIController
from bbb.sdram import SDRAM
from bbb.axi3 import AXI3ReadPort, AXI3WritePort
from bbb.uart import UARTTxFromMemory, DataToMem


class Top(Module):
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


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
