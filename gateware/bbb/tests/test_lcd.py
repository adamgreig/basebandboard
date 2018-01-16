from ..rgb_lcd import RGBLCD, LCDPatternGenerator, DoubleBuffer
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


def test_double_buffer():
    fb1 = Signal(25, reset=0x12345)
    fb2 = Signal(25, reset=0xABCDE)
    vsync = Signal()
    drawn = Signal()
    db = DoubleBuffer(fb1, fb2, vsync, drawn)

    def tb():
        yield drawn.eq(0)
        yield vsync.eq(0)
        for _ in range(10):
            yield

        # short hsync pulse
        yield vsync.eq(1)
        for _ in range(10):
            yield
        yield vsync.eq(0)
        for _ in range(50):
            yield

        # drawing completes
        yield drawn.eq(1)
        for _ in range(10):
            yield

        # another hsync pulse
        yield vsync.eq(1)
        for _ in range(10):
            yield
        yield vsync.eq(0)
        for _ in range(20):
            yield
        yield drawn.eq(0)
        for _ in range(30):
            yield

    run_simulation(db, tb(), vcd_name="db.vcd")


def test_patgen():
    class FakeTS(Module):
        def __init__(self):
            self.x = Signal(12)
            self.y = Signal(12)
            self.pen = Signal()
            self.newdata = Signal()

    ts = FakeTS()

    write_port = AXI3WritePort(id_width=1, addr_width=25, data_width=32)
    startaddr = Signal(25)
    patgen = LCDPatternGenerator(write_port, startaddr, ts)
    regs = [Signal(32) for _ in range(512)]
    regfile = Array(regs)
    regwriter = AXI3RegWriter(write_port, regfile)
    patgen.submodules += regwriter

    def tb():
        for _ in range(10000):
            yield
    run_simulation(patgen, tb(), vcd_name="patgen.vcd")
