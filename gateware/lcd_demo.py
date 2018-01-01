from migen import Module, Signal, ClockDomain
from bbb.platform import BBBPlatform, PLL
from bbb.rgb_lcd import RGBLCD, LCDPatternGenerator
from bbb.sdram import SDRAM
from bbb.axi3 import AXI3ReadPort, AXI3WritePort


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
        axirp = AXI3ReadPort(1, 24, 32)
        axiwp = AXI3WritePort(1, 24, 32)
        sdram = plat.request("sdram")
        sdramctl = SDRAM(axirp, axiwp, sdram, timings)
        self.submodules += sdramctl
        self.specials += sdramctl.dqt.get_tristate(sdram.dq)

        # LCD controller
        display = platform.request("lcd")
        backlight = platform.request("lcd_backlight")
        self.comb += backlight.eq(1)
        self.comb += display.disp.eq(1)
        startaddr = Signal(24)
        self.submodules.lcd = RGBLCD(display, axirp, startaddr)

        # LCD test pattern generator
        self.submodules.patgen = LCDPatternGenerator(axiwp, startaddr)


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
