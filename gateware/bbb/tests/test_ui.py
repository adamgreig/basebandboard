from ..ui import UIDisplay
from ..axi3 import AXI3ReadPort, AXI3WritePort
from ..axi3 import AXI3RegReader, AXI3RegWriter
from migen import Signal, Array
from migen.sim import run_simulation


def test_ui():
    axi3_read = AXI3ReadPort(id_width=2, addr_width=24, data_width=32)
    axi3_write = AXI3WritePort(id_width=2, addr_width=24, data_width=32)
    regs = [Signal(32) for _ in range(480)]
    regfile = Array(regs)
    axi3rw = AXI3RegWriter(axi3_write, regfile)

    backbuf = Signal(24)
    trigger = Signal()

    thresh_x = Signal(8, reset=5)
    thresh_y = Signal(8, reset=3)
    beta = Signal(5, reset=17)
    sigma2 = Signal(4, reset=11)
    tx_src = Signal()
    tx_en = Signal()
    noise_en = Signal()

    ui = UIDisplay(axi3_read, axi3_write, backbuf, trigger,
                   thresh_x, thresh_y, beta, sigma2, tx_src, tx_en, noise_en)

    ui.submodules += axi3rw

    def tb():
        for _ in range(10):
            yield
        yield trigger.eq(1)
        yield
        yield trigger.eq(0)
        yield
        for _ in range(10000):
            yield

    run_simulation(ui, tb(), vcd_name="ui.vcd")
