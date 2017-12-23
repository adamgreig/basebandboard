"""
AXI3 interfaces.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue


class AXI3ReadPort(Module):
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

    def connect(self, **kwargs):
        signals = ("arid", "araddr", "arlen", "arsize", "arburst", "arlock",
                   "arcache", "arprot", "arvalid", "arready", "rid", "rdata",
                   "rresp", "rlast", "rvalid", "rready")
        for signal in signals:
            if signal in kwargs:
                self.comb += getattr(self, signal).eq(kwargs[signal])


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

    def connect(self, **kwargs):
        signals = ("awid", "awaddr", "awlen", "awsize", "awburst", "awlock",
                   "awcache", "awprot", "awvalid", "awready", "wid", "wdata",
                   "wstrb", "wlast", "wvalid", "wready", "bid", "bresp",
                   "bvalid", "bready")
        for signal in signals:
            if signal in kwargs:
                self.comb += getattr(self, signal).eq(kwargs[signal])


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


class AXI3SlaveReader(Module):
    """
    AXI3 read-only slave.

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


class AXI3SlaveWriter(Module):
    """AXI3 write-only slave.

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
               NextValue(self.response, RESP_SLVERR)),

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
