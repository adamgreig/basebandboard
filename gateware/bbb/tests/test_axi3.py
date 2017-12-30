from ..axi3 import AXI3ReadPort, AXI3WritePort
from ..axi3 import AXI3SlaveReader, AXI3SlaveWriter
from ..axi3 import BURST_TYPE_INCR, BURST_SIZE_4, RESP_OKAY, RESP_SLVERR
from migen import Array, Signal
from migen.sim import run_simulation


def test_axi3_slave_reader():
    port = AXI3ReadPort(id_width=12, addr_width=21, data_width=32)

    # Make a very simple fake register file.
    reg0 = Signal(32, reset=0x12345678)
    reg1 = Signal(32, reset=0xDEADBEEF)
    reg2 = Signal(32, reset=0xCAFEBABE)
    reg3 = Signal(32, reset=0xABCD1234)
    regfile = Array([reg0, reg1, reg2, reg3])

    axi3sr = AXI3SlaveReader(port, regfile)

    def tb():
        # ID 0x123
        # Set up a 4-burst read from address 0
        yield port.arid.eq(0x123)
        yield port.araddr.eq(0x0)
        yield port.arlen.eq(4-1)
        yield port.arsize.eq(0b010)
        yield port.arburst.eq(0b01)
        yield port.arvalid.eq(0)
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.arready)
        yield port.arvalid.eq(1)
        yield
        yield
        yield port.arvalid.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x123)
        assert (yield port.rdata == reg0)
        assert (yield port.rresp == RESP_OKAY)
        assert (yield port.rlast == 0)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x123)
        assert (yield port.rdata == reg1)
        assert (yield port.rresp == RESP_OKAY)
        assert (yield port.rlast == 0)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x123)
        assert (yield port.rdata == reg2)
        assert (yield port.rresp == 0b00)
        assert (yield port.rlast == 0)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x123)
        assert (yield port.rdata == reg3)
        assert (yield port.rresp == 0b00)
        assert (yield port.rlast == 1)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield

        # ID 0x124. Single read from address 0.
        yield port.arid.eq(0x124)
        yield port.araddr.eq(0x0)
        yield port.arlen.eq(1-1)
        yield port.arsize.eq(0b010)
        yield port.arburst.eq(0b00)
        yield port.arvalid.eq(0)
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.arready)
        yield port.arvalid.eq(1)
        yield
        yield
        yield port.arvalid.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x124)
        assert (yield port.rdata == reg0)
        assert (yield port.rresp == 0b00)
        assert (yield port.rlast == 1)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield

        # ID 0x125. Single read from reg2 (= address 2*4=8).
        yield port.arid.eq(0x125)
        yield port.araddr.eq(0x8)
        yield port.arlen.eq(1-1)
        yield port.arsize.eq(0b010)
        yield port.arburst.eq(0b00)
        yield port.arvalid.eq(0)
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.arready)
        yield port.arvalid.eq(1)
        yield
        yield
        yield port.arvalid.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x125)
        assert (yield port.rdata == reg2)
        assert (yield port.rresp == 0b00)
        assert (yield port.rlast == 1)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield

        # ID 0x126. Error read due to ARSIZE != 0b010.
        yield port.arid.eq(0x126)
        yield port.araddr.eq(0x0)
        yield port.arlen.eq(1-1)
        yield port.arsize.eq(0b001)
        yield port.arburst.eq(0b01)
        yield port.arvalid.eq(0)
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.arready)
        yield port.arvalid.eq(1)
        yield
        yield
        yield port.arvalid.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x126)
        assert (yield port.rresp == 0b10)
        assert (yield port.rlast == 1)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield
        yield

        # ID 0x127. Error read due to address too big.
        yield port.arid.eq(0x127)
        yield port.araddr.eq(5*8)
        yield port.arlen.eq(1-1)
        yield port.arsize.eq(0b010)
        yield port.arburst.eq(0b01)
        yield port.arvalid.eq(0)
        yield port.rready.eq(0)
        yield
        yield
        assert (yield port.arready)
        yield port.arvalid.eq(1)
        yield
        yield
        yield port.arvalid.eq(0)
        yield
        yield
        assert (yield port.rvalid)
        assert (yield port.rid == 0x127)
        assert (yield port.rresp == 0b10)
        assert (yield port.rlast == 1)
        yield port.rready.eq(1)
        yield
        yield port.rready.eq(0)
        yield
        yield
        yield

    run_simulation(axi3sr, tb(), vcd_name="axi3sr.vcd")


def test_axi3_slave_writer():
    port = AXI3WritePort(id_width=12, addr_width=21, data_width=32)

    # Make a very simple fake register file.
    reg0 = Signal(32, reset=0)
    reg1 = Signal(32, reset=0)
    reg2 = Signal(32, reset=0)
    reg3 = Signal(32, reset=0)
    regfile = Array([reg0, reg1, reg2, reg3])

    axi3sw = AXI3SlaveWriter(port, regfile)

    def tb():
        # ID 0x123
        # Set up a 4-burst write to address 0+
        yield port.awid.eq(0x123)
        yield port.awaddr.eq(0x0)
        yield port.awlen.eq(4-1)
        yield port.awsize.eq(BURST_SIZE_4)
        yield port.awburst.eq(BURST_TYPE_INCR)
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.awready)
        yield port.awvalid.eq(1)
        yield
        yield
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.wready)
        yield port.wid.eq(0x123)
        yield port.wdata.eq(0xDEADBEEF)
        yield port.wstrb.eq(0xF)
        yield port.wlast.eq(0)
        yield port.wvalid.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield
        assert (yield port.wready)
        yield port.wvalid.eq(1)
        yield port.wdata.eq(0xCAFEBABE)
        yield
        yield port.wvalid.eq(0)
        yield
        assert (yield port.wready)
        yield port.wvalid.eq(1)
        yield port.wdata.eq(0x12345678)
        yield
        yield port.wvalid.eq(0)
        yield
        assert (yield port.wready)
        yield port.wvalid.eq(1)
        yield port.wlast.eq(1)
        yield port.wdata.eq(0xABCDEF00)
        yield
        yield port.wvalid.eq(0)
        yield port.wlast.eq(0)
        yield
        yield
        assert (yield port.bvalid)
        assert (yield port.bid == 0x123)
        assert (yield port.bresp == RESP_OKAY)
        yield port.bready.eq(1)
        yield
        yield
        yield port.bready.eq(0)
        yield
        yield
        assert (yield reg0) == 0xDEADBEEF
        assert (yield reg1) == 0xCAFEBABE
        assert (yield reg2) == 0x12345678
        assert (yield reg3) == 0xABCDEF00

        # ID 0x124
        # Single write to address 4.
        yield port.awid.eq(0x124)
        yield port.awaddr.eq(0x4)
        yield port.awlen.eq(1-1)
        yield port.awsize.eq(BURST_SIZE_4)
        yield port.awburst.eq(BURST_TYPE_INCR)
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.awready)
        yield port.awvalid.eq(1)
        yield
        yield
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.wready)
        yield port.wid.eq(0x124)
        yield port.wdata.eq(0xABAD1DEA)
        yield port.wstrb.eq(0xF)
        yield port.wlast.eq(1)
        yield port.wvalid.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield port.wlast.eq(0)
        yield
        yield
        assert (yield port.bvalid)
        assert (yield port.bid == 0x124)
        assert (yield port.bresp == RESP_OKAY)
        yield port.bready.eq(1)
        yield
        yield port.bready.eq(0)
        yield
        yield
        assert (yield reg1) == 0xABAD1DEA

        # ID 0x124
        # Error because burst went over the maximum address.
        yield port.awid.eq(0x125)
        yield port.awaddr.eq(0x4)
        yield port.awlen.eq(4-1)
        yield port.awsize.eq(BURST_SIZE_4)
        yield port.awburst.eq(BURST_TYPE_INCR)
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.awready)
        yield port.awvalid.eq(1)
        yield
        yield
        yield port.awvalid.eq(0)
        yield
        yield
        assert (yield port.wready)
        yield port.wid.eq(0x125)
        yield port.wdata.eq(0xC0FFEE00)
        yield port.wstrb.eq(0xF)
        yield port.wvalid.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield
        yield port.wvalid.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield
        yield port.wvalid.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield
        yield port.wvalid.eq(1)
        yield port.wlast.eq(1)
        yield
        yield port.wvalid.eq(0)
        yield port.wlast.eq(0)
        yield
        yield
        yield
        assert (yield port.bvalid)
        assert (yield port.bid == 0x125)
        assert (yield port.bresp == RESP_SLVERR)
        yield port.bready.eq(1)
        yield
        yield port.bready.eq(0)
        yield
        yield

    run_simulation(axi3sw, tb(), vcd_name="axi3sw.vcd")
