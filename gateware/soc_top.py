from migen import Module, Signal, Instance, Cat, Array, ClockDomain, If
from migen.build.platforms import de0nanosoc

from bbb.axi3 import AXI3SlaveReader, AXI3SlaveWriter


class Registers(Module):
    """
    Simple register file.
    reg0 maps to the user LEDs.
    reg1 maps to the user keys.
    reg2 is a counter.
    reg3 is always 0xDEADBEEF.
    """
    def __init__(self, platform):
        leds = Cat([plat.request("user_led", x) for x in range(8)])
        keys = Cat([plat.request("key", x) for x in range(2)])
        switches = Cat([plat.request("sw", x) for x in range(4)])

        counter = Signal(32)
        self.sync += counter.eq(counter + 1)

        sw = [Signal(4) for _ in range(6)]
        self.sync += [sw[i].eq(1-keys[i]) for i in range(2)]
        self.sync += [sw[i].eq(switches[i-2]) for i in range(2, 6)]

        reg0 = Signal(32)
        reg1 = Signal(32)
        reg2 = Signal(32)
        reg3 = Signal(32)

        self.sync += leds.eq(reg0[:8])
        self.sync += reg1.eq(Cat(sw))
        self.sync += reg2.eq(counter)
        self.sync += reg3.eq(0xDEADBEEF)

        self.regfile = Array([reg0, reg1, reg2, reg3])


class Top(Module):
    def __init__(self, platform):
        # Wire up the outputs from the HPS2FPGA lightweight bridge
        arid = Signal(12)
        araddr = Signal(21)
        arlen = Signal(4)
        arsize = Signal(3)
        arburst = Signal(2)
        arlock = Signal(2)
        arcache = Signal(4)
        arprot = Signal(3)
        arvalid = Signal()
        rready = Signal()
        awid = Signal(12)
        awaddr = Signal(21)
        awlen = Signal(4)
        awsize = Signal(3)
        awburst = Signal(2)
        awlock = Signal(2)
        awcache = Signal(4)
        awprot = Signal(3)
        awvalid = Signal()
        wid = Signal(12)
        wdata = Signal(32)
        wstrb = Signal(4)
        wlast = Signal()
        wvalid = Signal()
        bready = Signal()

        # Set up the clock
        clk50 = plat.request("clk1_50")
        self.clock_domains.sys = ClockDomain("sys")
        self.comb += self.sys.clk.eq(clk50)

        # Create a simple registers file
        self.submodules.registers = Registers(platform)

        # Create the AXI3 read-only slave
        axi3sr = AXI3SlaveReader(arid, araddr, arlen, arsize, arburst, arvalid,
                                 rready, self.registers.regfile)
        self.submodules += axi3sr

        # Create the AXI3 write-only slave
        axi3sw = AXI3SlaveWriter(awid, awaddr, awlen, awsize, awburst, awvalid,
                                 wid, wdata, wstrb, wlast, wvalid, bready,
                                 self.registers.regfile)
        self.submodules += axi3sw

        # Instantiate the HPS2FPGA lightweight bridge.
        # We connect its outputs to the Signals above, and its inputs to
        # the outputs of the AXI3SlaveReader.
        self.specials += Instance(
            "cyclonev_hps_interface_hps2fpga_light_weight",
            # Read outputs
            o_arid=arid, o_araddr=araddr, o_arlen=arlen, o_arsize=arsize,
            o_arburst=arburst, o_arlock=arlock, o_arcache=arcache,
            o_arprot=arprot, o_arvalid=arvalid, o_rready=rready,

            # Read inputs
            i_arready=axi3sr.arready, i_rid=axi3sr.rid, i_rdata=axi3sr.rdata,
            i_rresp=axi3sr.rresp, i_rlast=axi3sr.rlast, i_rvalid=axi3sr.rvalid,
            i_clk=self.sys.clk,

            # Write outputs
            o_awid=awid, o_awaddr=awaddr, o_awlen=awlen, o_awsize=awsize,
            o_awburst=awburst, o_awlock=awlock, o_awcache=awcache,
            o_awprot=awprot, o_awvalid=awvalid, o_wid=wid, o_wdata=wdata,
            o_wstrb=wstrb, o_wlast=wlast, o_wvalid=wvalid, o_bready=bready,

            # Write inputs
            i_awready = axi3sw.awready, i_wready=axi3sw.wready,
            i_bvalid = axi3sw.bvalid, i_bid=axi3sw.bid, i_bresp=axi3sw.bresp,
        )

        # We'll stick some debug information on GPI for easy checking
        gpi = Signal(32)
        self.sync += If(awvalid, gpi.eq(Cat(
            awid, awaddr[:4], awlen, awsize, awburst, awlock, awcache)))
        self.specials += Instance(
            "cyclonev_hps_interface_mpu_general_purpose", i_gp_in=gpi)


if __name__ == "__main__":
    import sys
    plat = de0nanosoc.Platform()
    top = Top(plat)
    plat.add_platform_command(
        "set_global_assignment -name NUM_PARALLEL_PROCESSORS ALL")
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        plat.build(top)
    if len(sys.argv) >= 3 and sys.argv[2] == "load":
        prog = plat.create_programmer()
        prog.load_bitstream("build/top.sof")
