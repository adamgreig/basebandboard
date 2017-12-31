from migen import Module, Signal, Memory, ClockDomain, FSM, NextState, If
from bbb.platform import BBBPlatform, PLL
from bbb.uart import UARTTxFromMemory, DataToMem
from bbb.nco import NCO
from bbb.sdram import SDRAM
from bbb.axi3 import AXI3ReadPort, AXI3WritePort
from bbb.axi3 import AXI3ToBRAM, BRAMToAXI3


class Top(Module):
    def __init__(self, platform):

        # Set up clocks. PLL the 50MHz to 100MHz, and PLL a -3ns phase shift
        # for the SDRAM clock.
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

        # Set up the DAC and ADC
        self.dac = platform.request("dac")
        self.comb += self.dac.clk.eq(self.sys.clk)
        self.adc_b = platform.request("adc_b")
        self.comb += self.adc_b.clk.eq(~self.sys.clk)

        # Set up an NCO to run a fixed frequency output on the DAC
        self.fcw = Signal(24, reset=2**17)
        self.am = Signal((16, False), reset=2**14)
        self.fm = Signal((24, True))
        self.pm = Signal((10, True))
        self.nco = NCO(self.fcw, self.am, self.fm, self.pm)
        self.submodules += self.nco
        self.comb += self.dac.data.eq(self.nco.x[3:16])

        # Make a BRAM to dump ADC readings into
        adc_ram = Memory(32, 512, list(range(512)))
        adcreadport = adc_ram.get_port(mode=1)
        adcwriteport = adc_ram.get_port(write_capable=True, mode=0)
        self.specials += [adc_ram, adcreadport, adcwriteport]
        adc2bramtrig = Signal()
        adcdata = Signal((10, True))
        self.comb += adcdata.eq(self.adc_b.data)
        adc2ram = DataToMem(adcdata, adcwriteport, 512, adc2bramtrig)
        self.submodules += adc2ram

        # Make a BRAM to dump over the UART
        uart_ram = Memory(32, 512, list(range(512)))
        uartreadport = uart_ram.get_port(mode=1)
        uartwriteport = uart_ram.get_port(write_capable=True, mode=0)
        self.specials += [uart_ram, uartreadport, uartwriteport]
        bram2uarttrig = Signal()
        ram2uart = UARTTxFromMemory(100, uartreadport,
                                    32, 0, 511, bram2uarttrig)
        self.submodules += ram2uart

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

        # SDRAM to/from BRAM via AXI3
        bram2sdramtrig = Signal()
        sdram2bramtrig = Signal()
        sdram2bram = AXI3ToBRAM(axirp, uartwriteport, sdram2bramtrig, 0, 512,
                                axi3_burst_length=4)
        bram2sdram = BRAMToAXI3(axiwp, adcreadport, bram2sdramtrig, 0, 512,
                                axi3_burst_length=8)
        self.submodules += [sdram2bram, bram2sdram]

        # FSM to sequence moving data around
        fsm_trig = Signal()
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.fsm.act(
            "IDLE",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            If(fsm_trig, NextState("ADC2BRAM"))
        )
        self.fsm.act(
            "ADC2BRAM",
            adc2bramtrig.eq(1),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            NextState("ADC2BRAM_WAIT")
        )
        self.fsm.act(
            "ADC2BRAM_WAIT",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            If(adc2ram.ready, NextState("BRAM2SDRAM"))
        )
        self.fsm.act(
            "BRAM2SDRAM",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(1),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            NextState("BRAM2SDRAM_WAIT")
        )
        self.fsm.act(
            "BRAM2SDRAM_WAIT",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            If(bram2sdram.ready, NextState("SDRAM2BRAM"))
        )
        self.fsm.act(
            "SDRAM2BRAM",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(1),
            bram2uarttrig.eq(0),

            NextState("SDRAM2BRAM_WAIT")
        )
        self.fsm.act(
            "SDRAM2BRAM_WAIT",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            If(sdram2bram.ready, NextState("BRAM2UART"))
        )
        self.fsm.act(
            "BRAM2UART",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(1),

            NextState("BRAM2UART_WAIT")
        )
        self.fsm.act(
            "BRAM2UART_WAIT",
            adc2bramtrig.eq(0),
            bram2sdramtrig.eq(0),
            sdram2bramtrig.eq(0),
            bram2uarttrig.eq(0),

            If(ram2uart.ready & (fsm_trig == 0), NextState("IDLE"))
        )

        # Wire up the keys and LEDs and UART
        gpio1 = plat.request("gpio_1")
        leds = [plat.request("user_led") for _ in range(8)]
        self.comb += [
            leds[0].eq(self.fsm.ongoing("ADC2BRAM")),
            leds[1].eq(self.fsm.ongoing("ADC2BRAM_WAIT")),
            leds[2].eq(self.fsm.ongoing("BRAM2SDRAM")),
            leds[3].eq(self.fsm.ongoing("BRAM2SDRAM_WAIT")),
            leds[4].eq(self.fsm.ongoing("SDRAM2BRAM")),
            leds[5].eq(self.fsm.ongoing("SDRAM2BRAM_WAIT")),
            leds[6].eq(self.fsm.ongoing("BRAM2UART")),
            leds[7].eq(self.fsm.ongoing("BRAM2UART_WAIT")),
            gpio1[25].eq(self.fsm.ongoing("SDRAM2BRAM")),
            gpio1[27].eq(self.fsm.ongoing("BRAM2SDRAM")),
            #gpio1[27].eq(sdram.we_n),
        ]
        key0 = plat.request("key")
        self.comb += fsm_trig.eq(~key0)
        self.comb += gpio1[0].eq(ram2uart.tx_out)


if __name__ == "__main__":
    plat = BBBPlatform()
    top = Top(plat)
    plat.build(top)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")
