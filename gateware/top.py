from migen import Module, Signal, ClockDomain

from bbb.platform import BBBPlatform, PLL
from bbb.tx import TX


class Top(Module):
    def __init__(self, platform):
        # Set up clocking.
        self.clk50 = platform.request("clk50")
        self.sys_pll = PLL(20, "sys", 1, 4)
        self.submodules += self.sys_pll
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += self.sys_pll.clk_in.eq(self.clk50)
        self.comb += self.sys.clk.eq(self.sys_pll.clk_out)

        # Set up the DAC and ADC peripherals
        self.dac = plat.request("dac")
        self.comb += self.dac.clk.eq(self.sys.clk)

        # Create a transmitter.
        self.prbs_k = 9
        self.bit_en = Signal()
        self.shape_sel = Signal(5, reset=0)
        self.noise_en = Signal()
        self.noise_var = Signal((4, True), reset=10)
        self.tx = TX(self.prbs_k, self.bit_en, self.shape_sel,
                     self.noise_en, self.noise_var)
        self.submodules += self.tx

        # Wire the transmitter up
        leds = [plat.request("user_led", i) for i in range(8)]
        sw = [plat.request("sw", i) for i in range(4)]
        self.comb += [
            self.bit_en.eq(sw[0]),
            self.noise_en.eq(sw[1]),
            self.shape_sel[0].eq(sw[2]),
            self.shape_sel[1].eq(sw[3]),
            self.dac.data.eq(self.tx.x << 2),
        ]
        self.comb += [
            leds[0].eq(self.bit_en),
            leds[1].eq(self.noise_en),
            leds[2].eq(self.shape_sel[0]),
            leds[3].eq(self.shape_sel[1]),
        ]

        # Output the bit clock somewhere too
        gpio1 = plat.request("gpio_1")
        self.comb += gpio1[0].eq(self.tx.shaper.prbsclk.clk)


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
