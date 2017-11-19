"""
Platform class for the prototype ADC/DAC and other hardware.
"""

from migen import Signal, Module, Instance
from migen.build.generic_platform import Pins, IOStandard, Subsignal
from migen.build.platforms import de0nano


class PLL(Module):
    """Helper for instantiating onboard PLLs"""
    def __init__(self, period_in, name, divide_by, multiply_by):
        self.clk_in = Signal()
        self.clk_out = Signal()
        self.specials += Instance("ALTPLL",
                                  p_bandwidth_type="AUTO",
                                  p_clk0_divide_by=divide_by,
                                  p_clk0_duty_cycle=50,
                                  p_clk0_multiply_by=multiply_by,
                                  p_clk0_phase_shift="0",
                                  p_compensate_clock="CLK0",
                                  p_inclk0_input_frequency=int(period_in*1000),
                                  p_intended_device_family="Cyclone IV E",
                                  p_lpm_hint="CBX_MODULE_PREFIX={}_pll"
                                             .format(name),
                                  p_lpm_type="altpll",
                                  p_operation_mode="NORMAL",
                                  i_inclk=self.clk_in,
                                  o_clk=self.clk_out,
                                  i_areset=0,
                                  i_clkena=0x3f,
                                  i_clkswitch=0,
                                  i_configupdate=0,
                                  i_extclkena=0xf,
                                  i_fbin=1,
                                  i_pfdena=1,
                                  i_phasecounterselect=0xf,
                                  i_phasestep=1,
                                  i_phaseupdown=1,
                                  i_pllena=1,
                                  i_scanaclr=0,
                                  i_scanclk=0,
                                  i_scanclkena=1,
                                  i_scandata=0,
                                  i_scanread=0,
                                  i_scanwrite=0)


_dac = [
    ("dac", 0,
        Subsignal("data", Pins("D12 D11 A12 B11 C11 E10 E11 D9 C9 E9 F9 F8")),
        Subsignal("clk", Pins("E8")),
        IOStandard("3.3-V LVTTL")),
]


class BBBPlatform(de0nano.Platform):
    def __init__(self):
        de0nano.AlteraPlatform.__init__(self, "EP4CE22F17C6",
                                        de0nano._io + _dac)
