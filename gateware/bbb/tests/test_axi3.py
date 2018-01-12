from ..axi3 import AXI3ReadPort, AXI3WritePort
from ..axi3 import AXI3RegReader, AXI3RegWriter
from ..axi3 import AXI3ToBRAM, BRAMToAXI3
from ..axi3 import AXI3ReadMux, AXI3WriteMux
from ..axi3 import BURST_TYPE_INCR, BURST_SIZE_4, RESP_OKAY, RESP_SLVERR
from migen import Array, Signal, Memory, Module
from migen.sim import run_simulation


def test_axi3_slave_reader():
    port = AXI3ReadPort(id_width=12, addr_width=21, data_width=32)

    # Make a very simple fake register file.
    reg0 = Signal(32, reset=0x12345678)
    reg1 = Signal(32, reset=0xDEADBEEF)
    reg2 = Signal(32, reset=0xCAFEBABE)
    reg3 = Signal(32, reset=0xABCD1234)
    regfile = Array([reg0, reg1, reg2, reg3])

    axi3sr = AXI3RegReader(port, regfile)

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

    axi3sw = AXI3RegWriter(port, regfile)

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


def test_axi3_to_bram():
    read_port = AXI3ReadPort(id_width=2, addr_width=6, data_width=32)
    regs = [Signal(32, reset=x) for x in range(16)]
    regfile = Array(regs)

    axi3sr = AXI3RegReader(read_port, regfile)

    bram = Memory(32, 16)
    bram_port = bram.get_port(write_capable=True)

    trigger = Signal()

    axi3tobram = AXI3ToBRAM(read_port, bram_port, trigger, 0, 16, 4)

    top = Module()
    top.submodules += [axi3tobram, axi3sr]
    top.specials += [bram, bram_port]

    def tb():
        for _ in range(10):
            yield
        yield trigger.eq(1)
        yield
        yield trigger.eq(0)
        for _ in range(200):
            yield

    run_simulation(top, tb(), vcd_name="axi3tobram.vcd")


def test_bram_to_axi3():
    write_port = AXI3WritePort(id_width=2, addr_width=6, data_width=32)
    regs = [Signal(32) for _ in range(16)]
    regfile = Array(regs)

    axi3rw = AXI3RegWriter(write_port, regfile)

    bram = Memory(32, 16, list(range(16)))
    bram_port = bram.get_port()

    trigger = Signal()

    bramtoaxi3 = BRAMToAXI3(write_port, bram_port, trigger, 0, 16, 4)

    top = Module()
    top.submodules += [bramtoaxi3, axi3rw]
    top.specials += [bram, bram_port]

    def tb():
        for _ in range(10):
            yield
        yield trigger.eq(1)
        yield
        yield trigger.eq(0)
        yield
        while not (yield bramtoaxi3.ready):
            yield
        for _ in range(10):
            yield

    run_simulation(top, tb(), vcd_name="bramtoaxi3.vcd")


def test_axi3_read_mux():
    slave_port = AXI3ReadPort(id_width=2, addr_width=6, data_width=32)
    reg0 = Signal(32, reset=0xCAFE)
    reg1 = Signal(32, reset=0xBEEF)
    reg2 = Signal(32, reset=0xFACE)
    reg3 = Signal(32, reset=0xDEAD)
    regfile = Array([reg0, reg1, reg2, reg3])
    axi3sr = AXI3RegReader(slave_port, regfile)

    mux = AXI3ReadMux(slave_port)

    bram0 = Memory(32, 2)
    bram1 = Memory(32, 2)
    bram2 = Memory(32, 2)
    bram3 = Memory(32, 2)
    brams = [bram0, bram1, bram2, bram3]
    bram_ports = [bram.get_port(write_capable=True) for bram in brams]
    triggers = [Signal() for _ in range(4)]
    axi3tobrams = []

    for i in range(4):
        master_port = mux.add_master()
        axi3tobrams.append(AXI3ToBRAM(master_port, bram_ports[i], triggers[i],
                                      i*4, 1, 1))

    top = Module()
    top.submodules += [axi3sr, mux]
    top.specials += brams
    top.specials += bram_ports
    top.submodules += axi3tobrams

    def tb():
        for _ in range(10):
            yield

        # Trigger 0
        yield triggers[0].eq(1)
        yield
        yield triggers[0].eq(0)
        for _ in range(50):
            yield

        # Trigger 1 and 2 together
        yield triggers[1].eq(1)
        yield triggers[2].eq(1)
        yield
        yield triggers[1].eq(0)
        yield triggers[2].eq(0)
        for _ in range(50):
            yield

        # Trigger 3
        yield triggers[3].eq(1)
        yield
        yield triggers[3].eq(0)
        for _ in range(50):
            yield

        assert (yield bram0[0]) == 0xCAFE
        assert (yield bram1[0]) == 0xBEEF
        assert (yield bram2[0]) == 0xFACE
        assert (yield bram3[0]) == 0xDEAD

    run_simulation(top, tb(), vcd_name="axi3readmux.vcd")


def test_axi3_write_mux():
    slave_port = AXI3WritePort(id_width=2, addr_width=6, data_width=32)
    reg0 = Signal(32)
    reg1 = Signal(32)
    reg2 = Signal(32)
    reg3 = Signal(32)
    regfile = Array([reg0, reg1, reg2, reg3])
    axi3sw = AXI3RegWriter(slave_port, regfile)
    mux = AXI3WriteMux(slave_port)

    bram0 = Memory(32, 2, [0xCAFE])
    bram1 = Memory(32, 2, [0xBEEF])
    bram2 = Memory(32, 2, [0xFACE])
    bram3 = Memory(32, 2, [0xDEAD])
    brams = [bram0, bram1, bram2, bram3]
    bram_ports = [bram.get_port() for bram in brams]
    triggers = [Signal() for _ in range(4)]
    bramtoaxi3s = []

    for i in range(4):
        master_port = mux.add_master()
        bramtoaxi3s.append(BRAMToAXI3(master_port, bram_ports[i], triggers[i],
                                      i*4, 1, 1))

    top = Module()
    top.submodules += [axi3sw, mux]
    top.specials += brams
    top.specials += bram_ports
    top.submodules += bramtoaxi3s

    def tb():
        for _ in range(100):
            yield

        # Trigger 0
        yield triggers[0].eq(1)
        yield
        yield triggers[0].eq(0)
        for _ in range(50):
            yield

        # Trigger 1 and 2 together
        yield triggers[1].eq(1)
        yield triggers[2].eq(1)
        yield
        yield triggers[1].eq(0)
        yield triggers[2].eq(0)
        for _ in range(50):
            yield

        # Trigger 3
        yield triggers[3].eq(1)
        yield
        yield triggers[3].eq(0)
        for _ in range(50):
            yield

        assert (yield reg0) == 0xCAFE
        assert (yield reg1) == 0xBEEF
        assert (yield reg2) == 0xFACE
        assert (yield reg3) == 0xDEAD

    run_simulation(top, tb(), vcd_name="axi3writemux.vcd")
