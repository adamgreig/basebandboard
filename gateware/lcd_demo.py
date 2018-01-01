from migen import Module, Signal, ClockDomain
from bbb.platform import BBBPlatform, PLL
from bbb.rgb_lcd import RGBLCD


class Top(Module):
    def __init__(self, platform):
        self.clk50 = platform.request("clk50")
        sys_pll = PLL(20, "sys", 1, 2)
        self.submodules += sys_pll
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += sys_pll.clk_in.eq(self.clk50)
        self.comb += self.sys.clk.eq(sys_pll.clk_out)

        display = platform.request("lcd")
        backlight = platform.request("lcd_backlight")

        key0 = platform.request("key")
        key1 = platform.request("key")
        self.comb += backlight.eq(key0)
        self.comb += display.disp.eq(key1)

        self.submodules.lcd = RGBLCD(display)


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
