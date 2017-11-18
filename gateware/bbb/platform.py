"""
Platform class for the prototype ADC/DAC and other hardware.
"""

from migen.build.generic_platform import Pins, IOStandard, Subsignal
from migen.build.platforms import de0nano


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
