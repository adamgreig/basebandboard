from ..axi3 import AXI3SlaveReader, AXI3SlaveWriter
from ..axi3 import BURST_TYPE_INCR, BURST_SIZE_4, RESP_OKAY
from ..axi3 import RESP_SLVERR
from migen import Array, Signal
from migen.sim import run_simulation


def test_axi3_slave_reader():
    # These are the signals we spoof from the AXI3 master.
    arid = Signal(12)
    araddr = Signal(21)
    arlen = Signal(4)
    arsize = Signal(3)
    arburst = Signal(2)
    arvalid = Signal()
    rready = Signal()

    # Make a very simple fake register file.
    reg0 = Signal(32, reset=0x12345678)
    reg1 = Signal(32, reset=0xDEADBEEF)
    reg2 = Signal(32, reset=0xCAFEBABE)
    reg3 = Signal(32, reset=0xABCD1234)
    regfile = Array([reg0, reg1, reg2, reg3])

    axi3sr = AXI3SlaveReader(arid, araddr, arlen, arsize, arburst, arvalid,
                             rready, regfile)

    def tb():
        # ID 0x123
        # Set up a 4-burst read from address 0
        yield arid.eq(0x123)
        yield araddr.eq(0x0)
        yield arlen.eq(4-1)
        yield arsize.eq(0b010)
        yield arburst.eq(0b01)
        yield arvalid.eq(0)
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.arready)
        yield arvalid.eq(1)
        yield
        yield
        yield arvalid.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x123)
        assert (yield axi3sr.rdata == reg0)
        assert (yield axi3sr.rresp == RESP_OKAY)
        assert (yield axi3sr.rlast == 0)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x123)
        assert (yield axi3sr.rdata == reg1)
        assert (yield axi3sr.rresp == RESP_OKAY)
        assert (yield axi3sr.rlast == 0)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x123)
        assert (yield axi3sr.rdata == reg2)
        assert (yield axi3sr.rresp == 0b00)
        assert (yield axi3sr.rlast == 0)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x123)
        assert (yield axi3sr.rdata == reg3)
        assert (yield axi3sr.rresp == 0b00)
        assert (yield axi3sr.rlast == 1)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield

        # ID 0x124. Single read from address 0.
        yield arid.eq(0x124)
        yield araddr.eq(0x0)
        yield arlen.eq(1-1)
        yield arsize.eq(0b010)
        yield arburst.eq(0b00)
        yield arvalid.eq(0)
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.arready)
        yield arvalid.eq(1)
        yield
        yield
        yield arvalid.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x124)
        assert (yield axi3sr.rdata == reg0)
        assert (yield axi3sr.rresp == 0b00)
        assert (yield axi3sr.rlast == 1)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield

        # ID 0x125. Single read from reg2 (= address 2*4=8).
        yield arid.eq(0x125)
        yield araddr.eq(0x8)
        yield arlen.eq(1-1)
        yield arsize.eq(0b010)
        yield arburst.eq(0b00)
        yield arvalid.eq(0)
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.arready)
        yield arvalid.eq(1)
        yield
        yield
        yield arvalid.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x125)
        assert (yield axi3sr.rdata == reg2)
        assert (yield axi3sr.rresp == 0b00)
        assert (yield axi3sr.rlast == 1)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield

        # ID 0x126. Error read due to ARSIZE != 0b010.
        yield arid.eq(0x126)
        yield araddr.eq(0x0)
        yield arlen.eq(1-1)
        yield arsize.eq(0b001)
        yield arburst.eq(0b01)
        yield arvalid.eq(0)
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.arready)
        yield arvalid.eq(1)
        yield
        yield
        yield arvalid.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x126)
        assert (yield axi3sr.rresp == 0b10)
        assert (yield axi3sr.rlast == 1)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield
        yield

        # ID 0x127. Error read due to address too big.
        yield arid.eq(0x127)
        yield araddr.eq(5*8)
        yield arlen.eq(1-1)
        yield arsize.eq(0b010)
        yield arburst.eq(0b01)
        yield arvalid.eq(0)
        yield rready.eq(0)
        yield
        yield
        assert (yield axi3sr.arready)
        yield arvalid.eq(1)
        yield
        yield
        yield arvalid.eq(0)
        yield
        yield
        assert (yield axi3sr.rvalid)
        assert (yield axi3sr.rid == 0x127)
        assert (yield axi3sr.rresp == 0b10)
        assert (yield axi3sr.rlast == 1)
        yield rready.eq(1)
        yield
        yield rready.eq(0)
        yield
        yield
        yield

    run_simulation(axi3sr, tb(), vcd_name="axi3sr.vcd")


def test_axi3_slave_writer():
    # These are the signals we spoof from the AXI3 master.
    awid = Signal(12)
    awaddr = Signal(21)
    awlen = Signal(4)
    awsize = Signal(3)
    awburst = Signal(2)
    awvalid = Signal()
    wid = Signal(12)
    wdata = Signal(32)
    wstrb = Signal(4)
    wlast = Signal()
    wvalid = Signal()
    bready = Signal()

    # Make a very simple fake register file.
    reg0 = Signal(32, reset=0)
    reg1 = Signal(32, reset=0)
    reg2 = Signal(32, reset=0)
    reg3 = Signal(32, reset=0)
    regfile = Array([reg0, reg1, reg2, reg3])

    axi3sw = AXI3SlaveWriter(awid, awaddr, awlen, awsize, awburst, awvalid,
                             wid, wdata, wstrb, wlast, wvalid, bready, regfile)

    def tb():
        # ID 0x123
        # Set up a 4-burst write to address 0+
        yield awid.eq(0x123)
        yield awaddr.eq(0x0)
        yield awlen.eq(4-1)
        yield awsize.eq(BURST_SIZE_4)
        yield awburst.eq(BURST_TYPE_INCR)
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.awready)
        yield awvalid.eq(1)
        yield
        yield
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.wready)
        yield wid.eq(0x123)
        yield wdata.eq(0xDEADBEEF)
        yield wstrb.eq(0xF)
        yield wlast.eq(0)
        yield wvalid.eq(1)
        yield
        yield wvalid.eq(0)
        yield
        assert (yield axi3sw.wready)
        yield wvalid.eq(1)
        yield wdata.eq(0xCAFEBABE)
        yield
        yield wvalid.eq(0)
        yield
        assert (yield axi3sw.wready)
        yield wvalid.eq(1)
        yield wdata.eq(0x12345678)
        yield
        yield wvalid.eq(0)
        yield
        assert (yield axi3sw.wready)
        yield wvalid.eq(1)
        yield wlast.eq(1)
        yield wdata.eq(0xABCDEF00)
        yield
        yield wvalid.eq(0)
        yield wlast.eq(0)
        yield
        yield
        assert (yield axi3sw.bvalid)
        assert (yield axi3sw.bid == 0x123)
        assert (yield axi3sw.bresp == RESP_OKAY)
        yield bready.eq(1)
        yield
        yield
        yield bready.eq(0)
        yield
        yield
        assert (yield reg0) == 0xDEADBEEF
        assert (yield reg1) == 0xCAFEBABE
        assert (yield reg2) == 0x12345678
        assert (yield reg3) == 0xABCDEF00

        # ID 0x124
        # Single write to address 4.
        yield awid.eq(0x124)
        yield awaddr.eq(0x4)
        yield awlen.eq(1-1)
        yield awsize.eq(BURST_SIZE_4)
        yield awburst.eq(BURST_TYPE_INCR)
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.awready)
        yield awvalid.eq(1)
        yield
        yield
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.wready)
        yield wid.eq(0x124)
        yield wdata.eq(0xABAD1DEA)
        yield wstrb.eq(0xF)
        yield wlast.eq(1)
        yield wvalid.eq(1)
        yield
        yield wvalid.eq(0)
        yield wlast.eq(0)
        yield
        yield
        assert (yield axi3sw.bvalid)
        assert (yield axi3sw.bid == 0x124)
        assert (yield axi3sw.bresp == RESP_OKAY)
        yield bready.eq(1)
        yield
        yield bready.eq(0)
        yield
        yield
        assert (yield reg1) == 0xABAD1DEA

        # ID 0x124
        # Error because burst went over the maximum address.
        yield awid.eq(0x125)
        yield awaddr.eq(0x4)
        yield awlen.eq(4-1)
        yield awsize.eq(BURST_SIZE_4)
        yield awburst.eq(BURST_TYPE_INCR)
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.awready)
        yield awvalid.eq(1)
        yield
        yield
        yield awvalid.eq(0)
        yield
        yield
        assert (yield axi3sw.wready)
        yield wid.eq(0x125)
        yield wdata.eq(0xC0FFEE00)
        yield wstrb.eq(0xF)
        yield wvalid.eq(1)
        yield
        yield wvalid.eq(0)
        yield
        yield wvalid.eq(1)
        yield
        yield wvalid.eq(0)
        yield
        yield wvalid.eq(1)
        yield
        yield wvalid.eq(0)
        yield
        yield wvalid.eq(1)
        yield wlast.eq(1)
        yield
        yield wvalid.eq(0)
        yield wlast.eq(0)
        yield
        yield
        yield
        assert (yield axi3sw.bvalid)
        assert (yield axi3sw.bid == 0x125)
        assert (yield axi3sw.bresp == RESP_SLVERR)
        yield bready.eq(1)
        yield
        yield bready.eq(0)
        yield
        yield

    run_simulation(axi3sw, tb(), vcd_name="axi3sw.vcd")
