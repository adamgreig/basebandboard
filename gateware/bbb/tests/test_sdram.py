from ..sdram import SDRAM
from ..axi3 import AXI3ReadPort, AXI3WritePort
from ..axi3 import BURST_TYPE_INCR, BURST_SIZE_4, RESP_OKAY, RESP_SLVERR
from migen import Signal, Module
from migen.sim import run_simulation


def test_sdram():
    read_port = AXI3ReadPort(id_width=12, addr_width=25, data_width=32)
    write_port = AXI3WritePort(id_width=12, addr_width=25, data_width=32)

    class FakeRAM(Module):
        def __init__(self):
            self.a = Signal(13)
            self.ba = Signal(2)
            self.cs_n = Signal()
            self.cke = Signal()
            self.ras_n = Signal()
            self.cas_n = Signal()
            self.we_n = Signal()
            self.dq = Signal(16)
            self.dm = Signal()
    ram = FakeRAM()
    timings = {
        "powerup": 50,
        "t_cac": 2,
        "t_rcd": 3,
        "t_rc": 10,
        "t_ras": 7,
        "t_rp": 3,
        "t_mrd": 3,
        "t_ref": 750,
    }

    sdram = SDRAM(read_port, write_port, ram, timings)

    def tb():
        # Give some time to observe initialisation
        for _ in range(500):
            yield

        # 4-long burst write
        yield write_port.awid.eq(0x123)
        yield write_port.awaddr.eq(0xABCD00)
        yield write_port.awlen.eq(4-1)
        yield write_port.awsize.eq(BURST_SIZE_4)
        yield write_port.awburst.eq(BURST_TYPE_INCR)
        yield write_port.awvalid.eq(1)
        while not (yield write_port.awready):
            yield
        yield
        yield write_port.awvalid.eq(0)
        while not (yield write_port.wready):
            yield
        yield
        yield write_port.wid.eq(0x123)
        yield write_port.wdata.eq(0xDEADBEEF)
        yield write_port.wstrb.eq(0xF)
        yield write_port.wlast.eq(0)
        yield write_port.wvalid.eq(1)
        yield
        yield write_port.wvalid.eq(0)
        yield
        while not (yield write_port.wready):
            yield
        yield
        yield write_port.wvalid.eq(1)
        yield write_port.wdata.eq(0xCAFEBABE)
        yield
        yield write_port.wvalid.eq(0)
        yield
        while not (yield write_port.wready):
            yield
        yield
        yield write_port.wvalid.eq(1)
        yield write_port.wdata.eq(0x12345678)
        yield
        yield write_port.wvalid.eq(0)
        yield
        while not (yield write_port.wready):
            yield
        yield
        yield write_port.wvalid.eq(1)
        yield write_port.wlast.eq(1)
        yield write_port.wdata.eq(0xABCDEF00)
        yield
        yield write_port.wvalid.eq(0)
        yield write_port.wlast.eq(0)
        yield
        while not (yield write_port.bvalid):
            yield
        yield
        assert (yield write_port.bid) == 0x123
        assert (yield write_port.bresp) == RESP_OKAY
        yield write_port.bready.eq(1)
        yield
        yield
        yield write_port.bready.eq(0)
        yield
        yield
        yield write_port.awid.eq(0)
        yield write_port.awaddr.eq(0)
        yield write_port.awlen.eq(0)
        yield write_port.awsize.eq(0)
        yield write_port.awburst.eq(0)
        yield write_port.awvalid.eq(0)
        yield write_port.wid.eq(0)
        yield write_port.wdata.eq(0)
        yield write_port.wstrb.eq(0)
        yield write_port.wlast.eq(0)
        yield write_port.wvalid.eq(0)
        yield

        for _ in range(600):
            yield

        # 4-long burst read
        yield read_port.arid.eq(0x123)
        yield read_port.araddr.eq(0xABCD00)
        yield read_port.arlen.eq(4-1)
        yield read_port.arsize.eq(0b010)
        yield read_port.arburst.eq(0b01)
        yield read_port.arvalid.eq(0)
        yield read_port.rready.eq(0)
        yield
        yield read_port.arvalid.eq(1)
        while not (yield read_port.arready):
            yield
        yield
        yield read_port.arvalid.eq(0)
        yield read_port.rready.eq(1)
        yield
        yield
        yield
        yield
        yield
        yield sdram.dqt.i.eq(0x1234)
        yield
        yield sdram.dqt.i.eq(0x4321)
        while not (yield read_port.rvalid):
            yield
        assert (yield read_port.rid) == 0x123
        assert (yield read_port.rdata) == 0x43211234
        assert (yield read_port.rresp) == RESP_OKAY
        assert (yield read_port.rlast) == 0
        yield read_port.rready.eq(0)
        yield
        yield
        yield sdram.dqt.i.eq(0x5678)
        yield read_port.rready.eq(1)
        yield
        yield sdram.dqt.i.eq(0x8765)
        while not (yield read_port.rvalid):
            yield
        assert (yield read_port.rid) == 0x123
        assert (yield read_port.rdata) == 0x87655678
        assert (yield read_port.rresp) == RESP_OKAY
        assert (yield read_port.rlast) == 0
        yield read_port.rready.eq(0)
        yield
        yield
        yield sdram.dqt.i.eq(0xABCD)
        yield read_port.rready.eq(1)
        yield
        yield sdram.dqt.i.eq(0xDCBA)
        while not (yield read_port.rvalid):
            yield
        assert (yield read_port.rid) == 0x123
        assert (yield read_port.rdata) == 0xDCBAABCD
        assert (yield read_port.rresp) == RESP_OKAY
        assert (yield read_port.rlast) == 0
        yield read_port.rready.eq(0)
        yield
        yield
        yield sdram.dqt.i.eq(0xEF01)
        yield read_port.rready.eq(1)
        yield
        yield sdram.dqt.i.eq(0x10FE)
        while not (yield read_port.rvalid):
            yield
        assert (yield read_port.rid) == 0x123
        assert (yield read_port.rdata) == 0x10FEEF01
        assert (yield read_port.rresp) == RESP_OKAY
        assert (yield read_port.rlast) == 1
        yield read_port.rready.eq(0)
        yield
        yield

        yield read_port.arid.eq(0)
        yield read_port.araddr.eq(0)
        yield read_port.arlen.eq(0)
        yield read_port.arsize.eq(0)
        yield read_port.arburst.eq(0)
        yield read_port.arvalid.eq(0)
        yield read_port.rready.eq(0)
        yield sdram.dqt.i.eq(0)

        for _ in range(1000):
            yield

    run_simulation(sdram, tb(), vcd_name="sdram.vcd")
