from ..rgb_lcd import RGBLCD, LCDPatternGenerator
from ..axi3 import AXI3ReadPort, AXI3WritePort, AXI3RegWriter
from migen import Signal, Module, Array
from migen.sim import run_simulation


def test_lcd():
    read_port = AXI3ReadPort(id_width=1, addr_width=25, data_width=32)

    class FakeLCD(Module):
        def __init__(self):
            self.data = Signal(25)
            self.hsync = Signal()
            self.vsync = Signal()
            self.pclk = Signal()
            self.de = Signal()
    lcd = FakeLCD()
    startaddr = Signal(24)

    rgblcd = RGBLCD(lcd, read_port, startaddr)

    def tb():
        for _ in range(10000):
            yield

    run_simulation(rgblcd, tb(), vcd_name="lcd.vcd",
                   clocks={"sys": 10, "pclk": 20})


def test_patgen():
    write_port = AXI3WritePort(id_width=1, addr_width=25, data_width=32)
    startaddr = Signal(25)
    patgen = LCDPatternGenerator(write_port, startaddr)
    regs = [Signal(32) for _ in range(512)]
    regfile = Array(regs)
    regwriter = AXI3RegWriter(write_port, regfile)
    patgen.submodules += regwriter

    def tb():
        for _ in range(10000):
            yield
    run_simulation(patgen, tb(), vcd_name="patgen.vcd")
