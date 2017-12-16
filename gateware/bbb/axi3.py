"""
AXI3 interfaces.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue


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

    Input signals are from the AXI3 master AR and R ports.
    `regfile` is an Array which is indexed to respond to reads.

    Does not support ARLOCK, ARCACHE, or ARPROT at all.
    Only supports ARBURST=FIXED or INCR, but not WRAP.
    Only supports ARSIZE=0b010, i.e., 32bit reads.
    Does support burst reads.
    Responds SLVERR if invalid ARBURST or ARSIZE given, or if the
        read address is beyond 4*len(regfile).

    AXI3 outputs are:
        `self.arready`, `self.rid`, `self.rdata`, `self.rresp`,
        `self.rlast`, and `self.rvalid`.
    Connect them to the AXI3 master.
    """
    def __init__(self, arid, araddr, arlen, arsize, arburst, arvalid, rready,
                 regfile):

        # AXI3SlaveReader outputs
        self.arready = Signal()
        self.rid = Signal(arid.nbits)
        self.rdata = Signal(32)
        self.rresp = Signal(2)
        self.rlast = Signal()
        self.rvalid = Signal()

        # Store the control parameters for the active transaction.
        self.readid = Signal(arid.nbits)
        self.readaddr = Signal(araddr.nbits)
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
            self.arready.eq(1),
            self.rvalid.eq(0),

            # Capture all input parameters
            NextValue(self.readid, arid),
            NextValue(self.readaddr, araddr),
            NextValue(self.burstlen, arlen),
            NextValue(self.burstsize, arsize),
            NextValue(self.bursttype, arburst),

            # Initialise beatcount to 0
            NextValue(self.beatcount, 0),

            # Begin processing on ARVALID
            If(arvalid, NextState("PREPARE")),
        )

        # In PREPARE, we load the required data without yet asserting RVALID,
        # and also determine the RRESP response and incremenet the read
        # address and beat count.
        self.fsm.act(
            "PREPARE",
            self.arready.eq(0),
            self.rvalid.eq(0),

            # Output the current RID and RDATA
            self.rid.eq(self.readid),
            self.rdata.eq(regfile[self.readaddr >> 2]),

            # Return an error for burst size not 4 bytes, or WRAP burst type,
            # or an invalid read address.
            If((self.burstsize != BURST_SIZE_4)
               | (self.bursttype == BURST_TYPE_WRAP)
               | (self.readaddr > 4*len(regfile)),
               NextValue(self.response, RESP_SLVERR)).Else(
                   NextValue(self.response, RESP_OKAY)),
            self.rresp.eq(self.response),

            # Increment the read address if INCR mode is selected.
            If((self.bursttype == BURST_TYPE_INCR) & (self.beatcount != 0),
               NextValue(self.readaddr, self.readaddr + 4)),

            # Increment the beat count
            NextValue(self.beatcount, self.beatcount + 1),

            # Output whether this is the final beat of the burst
            self.rlast.eq(self.beatcount == self.burstlen + 1),
            NextState("WAIT"),
        )

        # In WAIT, we assert RVALID, and then wait for RREADY to be asserted
        # before either returning to PREPARE (if there are more beats in this
        # burst) or READY (if not).
        self.fsm.act(
            "WAIT",
            self.arready.eq(0),
            self.rvalid.eq(1),

            # Continue outputting RID, RDATA, RRESP, RLAST set in PREPARE
            self.rid.eq(self.readid),
            self.rdata.eq(regfile[self.readaddr >> 2]),
            self.rresp.eq(self.response),
            self.rlast.eq(self.beatcount == self.burstlen + 1),

            # Wait for RREADY before advancing
            If(rready,
                If(self.rlast, NextState("READY")).Else(NextState("PREPARE")))
        )


class AXI3SlaveWriter(Module):
    """AXI3 write-only slave.

    Input signals are from the AXI3 master AW, W, and B ports.
    `regfile` is an Array which is indexed to respond to writes.

    Does not support AWLOCK, AWCACHE, or AWPROT at all.
    Does not honour WSTRB.
    Only supports AWBURST=FIXED or INCR, not WRAP.
    Only supports AWSIZE=0b010, i.e., 32 bit writes.
    Responds SLVERR if invalid AWBURST or AWSIZE given, or if the
        write address is beyond 4*len(regfile).

    AXI3 outputs:
        `self.awready`, `self.wready`, `self.bid`, `self.bresp`,
        `self.bvalid`.
    Connect them to the AXI3 master.
    """
    def __init__(self, awid, awaddr, awlen, awsize, awburst, awvalid,
                 wid, wdata, wstrb, wlast, wvalid, bready, regfile):

        # AXI3SlaveWriter outputs
        self.awready = Signal()
        self.wready = Signal()
        self.bvalid = Signal()
        self.bid = Signal(awid.nbits)
        self.bresp = Signal(2)

        # Store the control parameters for the active transactions
        self.writeid = Signal(awid.nbits)
        self.writeaddr = Signal(awaddr.nbits)
        self.writedata = Signal(wdata.nbits)
        self.writestrobe = Signal(wstrb.nbits)
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
            self.awready.eq(1),
            self.wready.eq(0),
            self.bvalid.eq(0),
            self.bid.eq(0),
            self.bresp.eq(0),

            NextValue(self.writeid, awid),
            NextValue(self.writeaddr, awaddr),
            NextValue(self.burstlen, awlen),
            NextValue(self.burstsize, awsize),
            NextValue(self.bursttype, awburst),

            NextValue(self.beatcount, 0),

            If(awvalid, NextState("WAIT"))
        )

        # In WAIT we continuously register the data to write until we see
        # WVALID, then transition to STORE to process it.
        self.fsm.act(
            "WAIT",
            self.awready.eq(0),
            self.wready.eq(1),
            self.bvalid.eq(0),
            self.bid.eq(0),
            self.bresp.eq(0),

            NextValue(self.writedata, wdata),
            NextValue(self.writestrobe, wstrb),
            NextValue(self.lastwrite, wlast),

            If(wvalid, NextState("STORE"))
        ),

        # Save the recently registered incoming data to the register file,
        # then either transition back to WAIT if there's more data, or
        # on to RESPOND if not.
        self.fsm.act(
            "STORE",
            self.awready.eq(0),
            self.wready.eq(1),
            self.bvalid.eq(0),
            self.bid.eq(0),
            self.bresp.eq(0),

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
            self.awready.eq(0),
            self.wready.eq(0),
            self.bvalid.eq(1),
            self.bresp.eq(self.response),
            self.bid.eq(self.writeid),

            If(bready, NextState("READY"))
        ),
