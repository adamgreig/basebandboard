"""
AXI3 interfaces.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue, Case, Mux
from migen import Array


class AXI3ReadPort:
    def __init__(self, id_width, addr_width, data_width):
        self.id_width = id_width
        self.addr_width = addr_width
        self.data_width = data_width

        # Read Address
        self.arid = Signal(id_width)
        self.araddr = Signal(addr_width)
        self.arlen = Signal(4)
        self.arsize = Signal(3)
        self.arburst = Signal(2)
        self.arlock = Signal(2)
        self.arcache = Signal(4)
        self.arprot = Signal(3)
        self.arvalid = Signal()
        self.arready = Signal()

        # Read Response
        self.rid = Signal(id_width)
        self.rdata = Signal(data_width)
        self.rresp = Signal(2)
        self.rlast = Signal()
        self.rvalid = Signal()
        self.rready = Signal()


class AXI3WritePort:
    def __init__(self, id_width, addr_width, data_width):
        self.id_width = id_width
        self.addr_width = addr_width
        self.data_width = data_width

        # Write Address
        self.awid = Signal(id_width)
        self.awaddr = Signal(addr_width)
        self.awlen = Signal(4)
        self.awsize = Signal(3)
        self.awburst = Signal(2)
        self.awlock = Signal(2)
        self.awcache = Signal(4)
        self.awprot = Signal(3)
        self.awvalid = Signal()
        self.awready = Signal()

        # Write Data
        self.wid = Signal(id_width)
        self.wdata = Signal(data_width)
        self.wstrb = Signal(data_width//8)
        self.wlast = Signal()
        self.wvalid = Signal()
        self.wready = Signal()

        # Write Response
        self.bid = Signal(id_width)
        self.bresp = Signal(2)
        self.bvalid = Signal()
        self.bready = Signal()


BURST_TYPE_FIXED = 0b00
BURST_TYPE_INCR = 0b01
BURST_TYPE_WRAP = 0b10

BURST_SIZE_1 = 0b000
BURST_SIZE_2 = 0b001
BURST_SIZE_4 = 0b010
BURST_SIZE_8 = 0b011
BURST_SIZE_16 = 0b100
BURST_SIZE_32 = 0b101
BURST_SIZE_64 = 0b110
BURST_SIZE_128 = 0b111

RESP_OKAY = 0b00
RESP_EXOKAY = 0b01
RESP_SLVERR = 0b10
RESP_DECERR = 0b11


class AXI3RegReader(Module):
    """
    AXI3 read-only register file interface.

    `read_port` is an AXI3ReadPort. It should be connected to an AXI3 master.
    `regfile` is an Array which is indexed to respond to reads.

    Does not support ARLOCK, ARCACHE, or ARPROT at all.
    Only supports ARBURST=FIXED or INCR, but not WRAP.
    Only supports ARSIZE=0b010, i.e., 32bit reads.
    Does support burst reads.
    Responds SLVERR if invalid ARBURST or ARSIZE given, or if the
        read address is beyond 4*len(regfile).
    """
    def __init__(self, read_port, regfile):
        port = read_port

        # Store the control parameters for the active transaction.
        self.readid = Signal(port.id_width)
        self.readaddr = Signal(port.addr_width)
        self.burstlen = Signal(4)
        self.burstsize = Signal(3)
        self.bursttype = Signal(2)
        self.beatcount = Signal(4)
        self.response = Signal(2)

        self.submodules.fsm = FSM(reset_state="READY")

        # In READY, we assert ARREADY to indicate we can immediately receive
        # a new address to read from, and continuously register the input
        # AR parameters. When ARVALID becomes asserted, we transition to
        # the PREPARE state.
        self.fsm.act(
            "READY",
            port.arready.eq(1),
            port.rvalid.eq(0),

            # Capture all input parameters
            NextValue(self.readid, port.arid),
            NextValue(self.readaddr, port.araddr),
            NextValue(self.burstlen, port.arlen),
            NextValue(self.burstsize, port.arsize),
            NextValue(self.bursttype, port.arburst),

            # Initialise beatcount to 0
            NextValue(self.beatcount, 0),

            # Begin processing on ARVALID
            If(port.arvalid, NextState("PREPARE")),
        )

        # In PREPARE, we load the required data without yet asserting RVALID,
        # and also determine the RRESP response and incremenet the read
        # address and beat count.
        self.fsm.act(
            "PREPARE",
            port.arready.eq(0),
            port.rvalid.eq(0),

            # Output the current RID and RDATA
            port.rid.eq(self.readid),
            port.rdata.eq(regfile[self.readaddr >> 2]),

            # Return an error for burst size not 4 bytes, or WRAP burst type,
            # or an invalid read address.
            If((self.burstsize != BURST_SIZE_4)
               | (self.bursttype == BURST_TYPE_WRAP)
               | (self.readaddr > 4*len(regfile)),
               NextValue(self.response, RESP_SLVERR)).Else(
                   NextValue(self.response, RESP_OKAY)),
            port.rresp.eq(self.response),

            # Increment the read address if INCR mode is selected.
            If((self.bursttype == BURST_TYPE_INCR) & (self.beatcount != 0),
               NextValue(self.readaddr, self.readaddr + 4)),

            # Increment the beat count
            NextValue(self.beatcount, self.beatcount + 1),

            # Output whether this is the final beat of the burst
            port.rlast.eq(self.beatcount == self.burstlen + 1),
            NextState("WAIT"),
        )

        # In WAIT, we assert RVALID, and then wait for RREADY to be asserted
        # before either returning to PREPARE (if there are more beats in this
        # burst) or READY (if not).
        self.fsm.act(
            "WAIT",
            port.arready.eq(0),
            port.rvalid.eq(1),

            # Continue outputting RID, RDATA, RRESP, RLAST set in PREPARE
            port.rid.eq(self.readid),
            port.rdata.eq(regfile[self.readaddr >> 2]),
            port.rresp.eq(self.response),
            port.rlast.eq(self.beatcount == self.burstlen + 1),

            # Wait for RREADY before advancing
            If(port.rready,
                If(port.rlast, NextState("READY")).Else(NextState("PREPARE")))
        )


class AXI3RegWriter(Module):
    """AXI3 write-only register file interface.

    `write_port` is an AXI3WritePort. Connect it to an AXI3 master.
    `regfile` is an Array which is indexed to respond to writes.

    Does not support AWLOCK, AWCACHE, or AWPROT at all.
    Does not honour WSTRB.
    Only supports AWBURST=FIXED or INCR, not WRAP.
    Only supports AWSIZE=0b010, i.e., 32 bit writes.
    Responds SLVERR if invalid AWBURST or AWSIZE given, or if the
        write address is beyond 4*len(regfile).
    """
    def __init__(self, write_port, regfile):
        port = write_port

        # Store the control parameters for the active transactions
        self.writeid = Signal(port.id_width)
        self.writeaddr = Signal(port.addr_width)
        self.writedata = Signal(port.data_width)
        self.writestrobe = Signal(port.data_width//8)
        self.lastwrite = Signal()
        self.burstlen = Signal(4)
        self.burstsize = Signal(3)
        self.bursttype = Signal(2)
        self.beatcount = Signal(4)
        self.response = Signal(2)

        self.submodules.fsm = FSM(reset_state="READY")

        # In READY, we assert AWREADY to indicate we can immediately receive
        # a new address to write to, and continuously register the input AW
        # parameters. When AWVALID becomes asserted, we transition to the
        # WAIT state.
        self.fsm.act(
            "READY",
            port.awready.eq(1),
            port.wready.eq(0),
            port.bvalid.eq(0),
            port.bid.eq(0),
            port.bresp.eq(0),

            NextValue(self.writeid, port.awid),
            NextValue(self.writeaddr, port.awaddr),
            NextValue(self.burstlen, port.awlen),
            NextValue(self.burstsize, port.awsize),
            NextValue(self.bursttype, port.awburst),

            NextValue(self.beatcount, 0),

            If(port.awvalid, NextState("WAIT"))
        )

        # In WAIT we continuously register the data to write until we see
        # WVALID, then transition to STORE to process it.
        self.fsm.act(
            "WAIT",
            port.awready.eq(0),
            port.wready.eq(1),
            port.bvalid.eq(0),
            port.bid.eq(0),
            port.bresp.eq(0),

            NextValue(self.writedata, port.wdata),
            NextValue(self.writestrobe, port.wstrb),
            NextValue(self.lastwrite, port.wlast),

            If(port.wvalid, NextState("STORE"))
        ),

        # Save the recently registered incoming data to the register file,
        # then either transition back to WAIT if there's more data, or
        # on to RESPOND if not.
        self.fsm.act(
            "STORE",
            port.awready.eq(0),
            port.wready.eq(1),
            port.bvalid.eq(0),
            port.bid.eq(0),
            port.bresp.eq(0),

            # Save data
            NextValue(regfile[self.writeaddr >> 2], self.writedata),

            # Response is by default OKAY, but we'll change to SLVERR if
            # any error conditions occur on any write.
            If((self.burstsize != BURST_SIZE_4)
               | (self.bursttype == BURST_TYPE_WRAP)
               | (self.writeaddr >= 4*len(regfile)),
               NextValue(self.response, RESP_SLVERR)).Else(
                   NextValue(self.response, RESP_OKAY)),

            # Increment write address if required
            If(self.bursttype == BURST_TYPE_INCR,
               NextValue(self.writeaddr, self.writeaddr + 4)),

            # Increment the beat count
            NextValue(self.beatcount, self.beatcount + 1),

            If(self.lastwrite, NextState("RESPOND")).Else(NextState("WAIT"))
        ),

        # Return the response for this write
        self.fsm.act(
            "RESPOND",
            port.awready.eq(0),
            port.wready.eq(0),
            port.bvalid.eq(1),
            port.bresp.eq(self.response),
            port.bid.eq(self.writeid),

            If(port.bready, NextState("READY"))
        ),


class AXI3ToFromBRAM(Module):
    """
    Read and write data between an AXI3 slave and a BRAM.
    """
    def __init__(self, axi3_read, axi3_write, bram_port,
                 trigger_read, trigger_write, start_addr, length,
                 axi3_burst_length=1):
        """
        `axi3_read`: an AXI3ReadPort or None
        `axi3_write`: an AXI3WritePort or None
        `bram_port`: a MemoryPort, write capable if axi3_read is not None
        `trigger_read`: when asserted, copies `length` 32bit words from the
                        `axi3_read` into `bram_port` starting at address
                        `start_addr`.
        `trigger_write`: when asserted, copies `length` 32bit words from the
                         `bram_port` into the `axi3_write` port, starting at
                         address `start_addr`.
        `self.ready`: asserted when idle
        """
        self.ready = Signal()

        self.rlast = Signal()
        burstcount = Signal(max=axi3_burst_length+1)

        # These parameters of the read request are fixed
        if axi3_read is not None:
            self.comb += axi3_read.arid.eq(0)
            self.comb += axi3_read.arlen.eq(axi3_burst_length - 1)
            self.comb += axi3_read.arsize.eq(BURST_SIZE_4)
            self.comb += axi3_read.arburst.eq(BURST_TYPE_INCR)
            self.comb += axi3_read.arlock.eq(0b00)
            self.comb += axi3_read.arcache.eq(0b0000)
            self.comb += axi3_read.arprot.eq(0b000)

        # These parameters of the write requests are fixed
        if axi3_write is not None:
            self.comb += axi3_write.awid.eq(0)
            self.comb += axi3_write.awlen.eq(axi3_burst_length - 1)
            self.comb += axi3_write.awsize.eq(BURST_SIZE_4)
            self.comb += axi3_write.awburst.eq(BURST_TYPE_INCR)
            self.comb += axi3_write.awlock.eq(0b00)
            self.comb += axi3_write.awcache.eq(0b0000)
            self.comb += axi3_write.awprot.eq(0b000)
            self.comb += axi3_write.wid.eq(0)
            self.comb += axi3_write.wdata.eq(bram_port.dat_r)
            self.comb += axi3_write.wstrb.eq(0b1111)
            self.comb += axi3_write.wlast.eq(burstcount == axi3_burst_length-1)
            self.comb += axi3_write.bready.eq(1)

        # Make the state machine that manages reads and writes.
        # Our `self.ready` output is just whether we're in the READY state.
        self.submodules.fsm = FSM(reset_state="READY")
        self.comb += self.ready.eq(self.fsm.ongoing("READY"))

        # Form the READY state commands differently depending on whether
        # `axi3_read` and/or `axi3_write` are None
        ready_commands = [
            NextValue(bram_port.adr, 0),
        ]

        if axi3_read is not None:
            ready_commands += [
                axi3_read.arvalid.eq(0),
                axi3_read.rready.eq(0),
                NextValue(axi3_read.araddr, start_addr),
                If(trigger_read, NextState("READ_REQUEST")),
            ]
            self.comb += bram_port.we.eq(self.fsm.ongoing("READ_STORE"))

        if axi3_write is not None:
            ready_commands += [
                axi3_write.awvalid.eq(0),
                axi3_write.wvalid.eq(0),
                NextValue(axi3_write.awaddr, start_addr),
                If(trigger_write, NextState("WRITE_REQUEST"))
            ]

        self.fsm.act("READY", ready_commands)

        # Add relevant states for when axi3_read is not None
        if axi3_read is not None:
            self.fsm.act(
                "READ_REQUEST",
                axi3_read.arvalid.eq(1),
                axi3_read.rready.eq(0),

                If(axi3_read.arready, NextState("READ_WAIT"))
            )

            self.fsm.act(
                "READ_WAIT",
                axi3_read.arvalid.eq(0),
                axi3_read.rready.eq(1),

                NextValue(bram_port.dat_w, axi3_read.rdata),
                NextValue(self.rlast, axi3_read.rlast),
                If(axi3_read.rvalid, NextState("READ_STORE"))
            )

            self.fsm.act(
                "READ_STORE",
                axi3_read.arvalid.eq(0),
                axi3_read.rready.eq(0),

                # Increment BRAM and AXI3 addresses
                NextValue(bram_port.adr, bram_port.adr + 1),
                NextValue(axi3_read.araddr, axi3_read.araddr + 4),

                (If(self.rlast == 0, NextState("READ_WAIT"))
                 .Elif(bram_port.adr == length - 1, NextState("READY"))
                 .Else(NextState("READ_REQUEST")))
            )

        # Add relevant states for when axi3_write is not None
        if axi3_write is not None:
            self.fsm.act(
                "WRITE_REQUEST",
                axi3_write.awvalid.eq(1),
                axi3_write.wvalid.eq(0),

                NextValue(burstcount, 0),

                If(axi3_write.awready, NextState("WRITE_LOAD"))
            )

            self.fsm.act(
                "WRITE_LOAD",
                axi3_write.awvalid.eq(0),
                axi3_write.wvalid.eq(0),

                NextState("WRITE_WAIT")
            )

            self.fsm.act(
                "WRITE_WAIT",
                axi3_write.awvalid.eq(0),
                axi3_write.wvalid.eq(1),

                If(axi3_write.wready, NextState("WRITE_NEXT"))
            )

            self.fsm.act(
                "WRITE_NEXT",
                axi3_write.awvalid.eq(0),
                axi3_write.wvalid.eq(0),

                NextValue(bram_port.adr, bram_port.adr + 1),
                NextValue(burstcount, burstcount + 1),
                NextValue(axi3_write.awaddr, axi3_write.awaddr + 4),

                (If(axi3_write.wlast == 0, NextState("WRITE_LOAD"))
                 .Elif(bram_port.adr == length - 1, NextState("READY"))
                 .Else(NextState("WRITE_REQUEST")))
            )


class AXI3ToBRAM(AXI3ToFromBRAM):
    """
    Read data from an AXI3 slave into a BRAM.
    """
    def __init__(self, read_port, bram_port, trigger, start_addr, length,
                 axi3_burst_length=1):
        """
        When `trigger` is asserted, begins copying `length` 32bit words from
        the AXI3 port `read_port`, starting with address `start_addr`,
        writing into the BRAM port `bram_port` (a migen MemoryPort with width
        32 and which is write-capable). The signal `self.ready` is asserted
        while idle and deasserted during processing. The trigger input is
        ignored while not ready.
        """
        super().__init__(axi3_read=read_port, axi3_write=None,
                         bram_port=bram_port, trigger_read=trigger,
                         trigger_write=None, start_addr=start_addr,
                         length=length, axi3_burst_length=axi3_burst_length)


class BRAMToAXI3(AXI3ToFromBRAM):
    """
    Write data from a BRAM into an AXI3 slave.
    """
    def __init__(self, write_port, bram_port, trigger, start_addr, length,
                 axi3_burst_length=1):
        """
        When `trigger` is asserted, begins copying `length` 32bit words from
        the BRAM port `bram_port` (a migen MemoryPort with width 32) into the
        AXI3 port `write_port`, starting at AXI3 address `start_addr`.  The
        signal `self.ready` is asserted while idle and deasserted during
        processing. The trigger input is ignored while not ready.
        """
        super().__init__(axi3_read=None, axi3_write=write_port,
                         bram_port=bram_port, trigger_read=None,
                         trigger_write=trigger, start_addr=start_addr,
                         length=length, axi3_burst_length=axi3_burst_length)


class AXI3ReadMux(Module):
    """
    AXI3 multi-master single-slave read multiplexer.
    """
    def __init__(self, slave_port):
        """
        `slave_port` is an AXI3ReadPort connected to a slave device.
        This module will drive its master-driven signals from one
        of the attached masters.
        """
        self.slave_port = slave_port
        self.master_ports = []

    def add_master(self):
        """
        Creates a new AXI3ReadPort and returns it. The slave lines on the
        new port will be driven by the underlying device. The master lines
        should be driven by an external master.
        """
        port = AXI3ReadPort(self.slave_port.id_width,
                            self.slave_port.addr_width,
                            self.slave_port.data_width)
        self.comb += [
            port.rid.eq(self.slave_port.rid),
            port.rdata.eq(self.slave_port.rdata),
            port.rresp.eq(self.slave_port.rresp),
            port.rlast.eq(self.slave_port.rlast),
        ]

        self.master_ports.append(port)
        return port

    def do_finalize(self):
        n = len(self.master_ports)
        sel = Signal(n)

        # Connect the slave port bus lines to the selected master
        cases = {
            1 << i: [
                self.slave_port.arid.eq(self.master_ports[i].arid),
                self.slave_port.araddr.eq(self.master_ports[i].araddr),
                self.slave_port.arlen.eq(self.master_ports[i].arlen),
                self.slave_port.arsize.eq(self.master_ports[i].arsize),
                self.slave_port.arburst.eq(self.master_ports[i].arburst),
                self.slave_port.arlock.eq(self.master_ports[i].arlock),
                self.slave_port.arcache.eq(self.master_ports[i].arcache),
                self.slave_port.arprot.eq(self.master_ports[i].arprot),
                self.slave_port.arvalid.eq(self.master_ports[i].arvalid),
                self.slave_port.rready.eq(self.master_ports[i].rready),
            ]
            for i in range(n)
        }
        cases["default"] = [
                self.slave_port.arid.eq(0),
                self.slave_port.araddr.eq(0),
                self.slave_port.arlen.eq(0),
                self.slave_port.arsize.eq(0),
                self.slave_port.arburst.eq(0),
                self.slave_port.arlock.eq(0),
                self.slave_port.arcache.eq(0),
                self.slave_port.arprot.eq(0),
                self.slave_port.arvalid.eq(0),
                self.slave_port.rready.eq(0),
        ]
        self.comb += Case(sel, cases)

        # Connect slave-driven handshake to appropriate master
        self.comb += [
            self.master_ports[i].arready.eq(
                Mux(sel[i], self.slave_port.arready, 0))
            for i in range(n)]
        self.comb += [
            self.master_ports[i].rvalid.eq(
                Mux(sel[i], self.slave_port.rvalid, 0))
            for i in range(n)]

        # Make an array of input ARVALID which we will monitor to transition
        arvalid_arr = Array(port.arvalid for port in self.master_ports)

        # Manage interconnect state
        self.submodules.fsm = FSM(reset_state="IDLE")

        # If the currently selected master asserts ARVALID, we'll leave it
        # selected and go to BUSY state. Otherwise, we check all other
        # masters in insertion order, select the first one which has asserted
        # ARVALID, and go to BUSY.  If no masters have asserted ARVALID we
        # remain in IDLE.
        idle_check = If(self.slave_port.arvalid, NextState("BUSY"))
        for i in range(n):
            idle_check = idle_check.Elif(
                arvalid_arr[i],
                NextValue(sel, 1 << i),
                NextState("BUSY"))

        self.fsm.act("IDLE", idle_check)

        # The current read transaction will finish when the slave is
        # asserting RLAST and RVALID, and the master asserts RREADY.
        self.fsm.act(
            "BUSY",
            If(self.slave_port.rlast &
               self.slave_port.rvalid &
               self.slave_port.rready,
               NextState("IDLE"))
        )


class AXI3WriteMux(Module):
    """
    AXI3 multi-master single-slave write multiplexer.
    """
    def __init__(self, slave_port):
        """
        `slave_port` is an AXI3WritePort connected to a slave device.
        This module will drive its master-driven signals from one
        of the attached masters.
        """
        self.slave_port = slave_port
        self.master_ports = []

    def add_master(self):
        """
        Creates a new AXI3WritePort and returns it. The slave lines on the
        new port will be driven by the underlying device. The master lines
        should be driven by an external master.
        """
        port = AXI3WritePort(self.slave_port.id_width,
                             self.slave_port.addr_width,
                             self.slave_port.data_width)
        self.comb += [
            port.bid.eq(self.slave_port.bid),
            port.bresp.eq(self.slave_port.bresp),
        ]

        self.master_ports.append(port)
        return port

    def do_finalize(self):
        n = len(self.master_ports)
        sel = Signal(n)

        # Connect the slave port bus lines to the selected master
        cases = {
            1 << i: [
                self.slave_port.awid.eq(self.master_ports[i].awid),
                self.slave_port.awaddr.eq(self.master_ports[i].awaddr),
                self.slave_port.awlen.eq(self.master_ports[i].awlen),
                self.slave_port.awsize.eq(self.master_ports[i].awsize),
                self.slave_port.awburst.eq(self.master_ports[i].awburst),
                self.slave_port.awlock.eq(self.master_ports[i].awlock),
                self.slave_port.awcache.eq(self.master_ports[i].awcache),
                self.slave_port.awprot.eq(self.master_ports[i].awprot),
                self.slave_port.awvalid.eq(self.master_ports[i].awvalid),
                self.slave_port.wid.eq(self.master_ports[i].wid),
                self.slave_port.wdata.eq(self.master_ports[i].wdata),
                self.slave_port.wstrb.eq(self.master_ports[i].wstrb),
                self.slave_port.wlast.eq(self.master_ports[i].wlast),
                self.slave_port.wvalid.eq(self.master_ports[i].wvalid),
                self.slave_port.bready.eq(self.master_ports[i].bready),
            ]
            for i in range(n)
        }
        cases["default"] = [
                self.slave_port.awid.eq(0),
                self.slave_port.awaddr.eq(0),
                self.slave_port.awlen.eq(0),
                self.slave_port.awsize.eq(0),
                self.slave_port.awburst.eq(0),
                self.slave_port.awlock.eq(0),
                self.slave_port.awcache.eq(0),
                self.slave_port.awprot.eq(0),
                self.slave_port.awvalid.eq(0),
                self.slave_port.wid.eq(0),
                self.slave_port.wdata.eq(0),
                self.slave_port.wstrb.eq(0),
                self.slave_port.wlast.eq(0),
                self.slave_port.wvalid.eq(0),
                self.slave_port.bready.eq(0),
        ]
        self.comb += Case(sel, cases)

        # Connect slave-driven handshake to appropriate master
        self.comb += [
            self.master_ports[i].awready.eq(
                Mux(sel[i], self.slave_port.awready, 0))
            for i in range(n)]
        self.comb += [
            self.master_ports[i].wready.eq(
                Mux(sel[i], self.slave_port.wready, 0))
            for i in range(n)]
        self.comb += [
            self.master_ports[i].bvalid.eq(
                Mux(sel[i], self.slave_port.bvalid, 0))
            for i in range(n)]

        # Make an array of input AWVALID which we will monitor to transition
        awvalid_arr = Array(port.awvalid for port in self.master_ports)

        # Manage interconnect state
        self.submodules.fsm = FSM(reset_state="IDLE")

        # If the currently selected master asserts AWVALID, we'll leave it
        # selected and go to BUSY state. Otherwise, we check all other
        # masters in insertion order, select the first one which has asserted
        # AWVALID, and go to BUSY.  If no masters have asserted AWVALID we
        # remain in IDLE.
        idle_check = If(self.slave_port.awvalid, NextState("BUSY"))
        for i in range(n):
            idle_check = idle_check.Elif(
                awvalid_arr[i],
                NextValue(sel, 1 << i),
                NextState("BUSY"))

        self.fsm.act("IDLE", idle_check)

        # The current read transaction will finish when the slave is
        # asserting BVALID, and the master asserts BREADY.
        self.fsm.act(
            "BUSY",
            If(self.slave_port.bvalid &
               self.slave_port.bready,
               NextState("IDLE"))
        )
