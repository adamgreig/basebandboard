from migen import Module, Signal, ClockDomain, ClockDomainsRenamer

from bbb.platform import BBBPlatform, PLL
from bbb.tx import TX
from bbb.rx import RX
from bbb.nco import NCO


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


class Top(Module):
    def __init__(self, platform):
        # Set up clocking.
        self.clk50 = platform.request("clk50")

        self.submodules.tx_pll = PLL(20, "tx", 100, 4)
        self.clock_domains.tx = ClockDomain("tx")
        self.comb += self.tx_pll.clk_in.eq(self.clk50)
        self.comb += self.tx.clk.eq(self.tx_pll.clk_out)

        self.submodules.rx_pll = PLL(20, "rx", 100, 2)
        self.clock_domains.rx = ClockDomain("rx")
        self.comb += self.rx_pll.clk_in.eq(self.clk50)
        self.comb += self.rx.clk.eq(self.rx_pll.clk_out)

        # Set up the DAC and ADC peripherals
        self.dac = plat.request("dac")
        self.comb += self.dac.clk.eq(self.tx.clk)
        self.adc_b = plat.request("adc_b")
        self.comb += self.adc_b.clk.eq(self.rx.clk)

        # Create a transmitter.
        self.prbs_k = 9
        self.bit_en = Signal()
        self.shape_sel = Signal(5, reset=0)
        self.noise_en = Signal()
        self.noise_var = Signal(4, reset=10)
        self.submodules.tx = ClockDomainsRenamer("tx")(
            TX(self.prbs_k, self.bit_en, self.shape_sel,
               self.noise_en, self.noise_var))

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

        # Create a receiver
        self.sample_delay = Signal(2, reset=2)
        self.submodules.rx = ClockDomainsRenamer("rx")(
            RX(self.prbs_k, self.sample_delay, self.adc_b.data))

        # Output the bit clock, PRBS, etc
        gpio1 = plat.request("gpio_1")
        self.comb += [
            gpio1[0].eq(self.tx.shaper.prbsclk.clk),
            gpio1[1].eq(self.tx.shaper.prbs.x),
            gpio1[2].eq(self.rx.prbsclk.clk),
            gpio1[3].eq(self.rx.sliced),
            gpio1[4].eq(self.rx.delay.x),
            gpio1[5].eq(self.rx.prbsdet.feedback_bit),
            gpio1[6].eq(self.rx.err),
        ]


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    # top = NCOTest(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
