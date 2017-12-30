"""
SDRAM controller for DE0-Nano with AXI3 slave interface.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue, TSTriple
from .axi3 import BURST_TYPE_INCR, BURST_SIZE_4, RESP_OKAY, RESP_SLVERR
from .axi3 import BURST_TYPE_WRAP


# Contains logic levels for RAS_N, CAS_N, and WE_N for each command.
# In each case CS_N must be 0, otherwise all commands are interpreted as NOP.
SDRAM_COMMANDS = {
    "NOP": (1, 1, 1),
    "READ": (1, 0, 1),
    "WRITE": (1, 0, 0),
    "ACT": (0, 1, 1),
    "PRE": (0, 1, 0),
    "REF": (0, 0, 1),
    "MRS": (0, 0, 0),
}


def sdram_cmd(cmd, sdram):
    ras_n, cas_n, we_n = SDRAM_COMMANDS[cmd]
    sdram.ras_n.eq(ras_n)
    sdram.cas_n.eq(cas_n)
    sdram.we_n.eq(we_n)


class SDRAM(Module):
    """
    SDRAM Controller to AXI3 slave.

    `read_port` is an AXI3ReadPort and must be connected to the AXI3 master.
    `write_port` is an AXI3WritePort and must be connected to the AXI3 master.
    `sdram` is an object with `a`, `ba`, `cs_n`, `cke`, `ras_n`, `cas_n`,
        `we_n`, `dq`, and `dm` signals which are connected to the SDRAM.
    `timings` contains SDRAM timing values in units of cycles:
        "powerup": power-up delay, 200µs worth of clock cycles
        "t_cac": CAS latency, try 2
        "t_rcd": active to rw, try 3
        "t_rc": command period, REF to REF and ACT to ACT, try 10
        "t_ras": command period, ACT to PRE, try 7
        "t_rp": command period, PRE to ACT, try 3
        "t_mrd": mode register delay, >=3
        "t_ref": clocks between each auto-refresh command, eg 750
    The SDRAM clock should be established externally to an appropriate phase
    advance over the clock for this module, at the same frequency.
    """
    def __init__(self, read_port, write_port, sdram, timings):
        # Set up the DQ tristate signal
        dqn = len(sdram.dq)
        self.dqt = TSTriple(dqn)
        #self.specials += self.dqt.get_tristate(sdram.dq)

        # We'll just leave CKE asserted
        self.comb += sdram.cke.eq(1)

        # Controller state machine
        self.submodules.fsm = FSM(reset_state="POWERUP")
        counter = Signal(max=max(timings.values())+1)
        init_refresh_counter = Signal(3, reset=0)

        # AXI3 slave related registers
        self.writeid = Signal(write_port.id_width)
        self.writeaddr = Signal(write_port.addr_width)
        self.writedata = Signal(write_port.data_width)
        self.writestrobe = Signal(write_port.data_width//8)
        self.readid = Signal(read_port.id_width)
        self.readaddr = Signal(read_port.addr_width)
        self.readdata = Signal(read_port.data_width)
        self.lastwrite = Signal()
        self.wburstlen = Signal(4)
        self.wburstsize = Signal(3)
        self.wbursttype = Signal(2)
        self.rburstlen = Signal(4)
        self.rburstsize = Signal(3)
        self.rbursttype = Signal(2)
        self.beatcount = Signal(4)
        self.response = Signal(2)

        # Counters for auto refresh
        auto_refresh_counter = Signal(max=timings['t_ref']+1)
        auto_refresh_pending = Signal()
        self.sync += auto_refresh_counter.eq(auto_refresh_counter + 1)
        self.sync += If(auto_refresh_counter == 0, auto_refresh_pending.eq(1))

        self.fsm.act(
            "POWERUP",
            # NOP during initialisation.
            sdram.cs_n.eq(1),

            # Wait for 200µs initial powerup
            If(counter == timings['powerup'],
               NextValue(counter, 0),
               NextState("INIT_PRECHARGE")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "INIT_PRECHARGE",
            # Precharge all banks
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["PRE"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["PRE"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["PRE"][2]),
            sdram.a[10].eq(1),
            sdram.dm.eq(0xFF),
            NextState("INIT_PRECHARGE_WAIT"),
        )

        self.fsm.act(
            "INIT_PRECHARGE_WAIT",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If(counter == timings['t_rp'],
               NextValue(counter, 0),
               NextState("INIT_AUTOREFRESH")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "INIT_AUTOREFRESH",
            # Run auto-refresh cycles
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["REF"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["REF"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["REF"][2]),
            NextValue(init_refresh_counter, init_refresh_counter + 1),
            NextState("INIT_AUTOREFRESH_WAIT"),
        )

        self.fsm.act(
            "INIT_AUTOREFRESH_WAIT",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If(counter == timings['t_rc'],
               NextValue(counter, 0),
               If(init_refresh_counter == 0,
                   NextState("INIT_MODE")).Else(NextState("INIT_AUTOREFRESH"))
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "INIT_MODE",
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["MRS"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["MRS"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["MRS"][2]),

            # Write Burst Mode: Programmed Burst Length
            sdram.a[9].eq(0),
            # Operating Mode: Standard Operation
            sdram.a[7:9].eq(0),
            # CAS Latency: 2
            sdram.a[4:7].eq(2),
            # Burst Type: Sequential
            sdram.a[3].eq(0),
            # Burst Length: 2 (32 bits)
            sdram.a[0:3].eq(0b001),
            # Reserved, set to 0
            sdram.a[10:].eq(0),
            sdram.ba.eq(0),

            NextState("INIT_MODE_WAIT"),
        )

        self.fsm.act(
            "INIT_MODE_WAIT",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If(counter == timings['t_mrd'],
               NextValue(counter, 0),
               NextState("IDLE")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "IDLE",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            # Set AXI3 write port outputs.
            write_port.awready.eq(0),
            write_port.wready.eq(0),
            write_port.bvalid.eq(0),

            # Register AXI3 request inputs so that when
            # we notice AWVALID/ARVALID, these will contain valid data
            NextValue(self.writeid, write_port.awid),
            NextValue(self.writeaddr, write_port.awaddr),
            NextValue(self.wburstlen, write_port.awlen),
            NextValue(self.wburstsize, write_port.awsize),
            NextValue(self.wbursttype, write_port.awburst),
            NextValue(self.readid, read_port.arid),
            NextValue(self.writeaddr, read_port.araddr),
            NextValue(self.rburstlen, read_port.arlen),
            NextValue(self.rburstsize, read_port.arsize),
            NextValue(self.rbursttype, read_port.arburst),


            NextValue(counter, 0),
            NextValue(self.beatcount, 0),

            self.dqt.oe.eq(0),

            If(auto_refresh_pending,
               NextState("AUTOREFRESH")
               ).Elif(
               write_port.awvalid,
               NextState("WPREPARE")
               ).Elif(
               read_port.arvalid,
               NextState("RPREPARE")
               ).Else(NextState("IDLE")),
        )

        self.fsm.act(
            "WPREPARE",

            # Acknowledge the write request
            write_port.awready.eq(1),
            write_port.wready.eq(0),
            write_port.bvalid.eq(0),

            # Activate the relevant row for this address
            sdram.ba.eq(self.writeaddr[22:24]),
            sdram.a.eq(self.writeaddr[9:22]),
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["ACT"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["ACT"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["ACT"][2]),

            NextValue(counter, 0),
            NextState("WPREPARE_WAIT")
        )

        self.fsm.act(
            "WPREPARE_WAIT",

            write_port.awready.eq(0),
            write_port.wready.eq(0),
            write_port.bvalid.eq(0),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If((self.wburstsize != BURST_SIZE_4)
               | (self.wbursttype == BURST_TYPE_WRAP),
               NextValue(self.response, RESP_SLVERR)).Else(
                    NextValue(self.response, RESP_OKAY)),

            If(counter == timings['t_rcd'],
               NextValue(counter, 0),
               NextState("WWAIT")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "WWAIT",

            # Wait for write data and register it

            # NOP the SDRAM
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            # Set AXI3 write outputs.
            # In WWAIT we continuously register the data to write until we see
            # WVALID, then transition to WSTORE to process it.
            write_port.awready.eq(0),
            write_port.wready.eq(1),
            write_port.bvalid.eq(0),

            # Register incoming AXI3 data-to-write
            NextValue(self.writedata, write_port.wdata),
            NextValue(self.writestrobe, write_port.wstrb),
            NextValue(self.lastwrite, write_port.wlast),

            If(write_port.wvalid, NextState("WSTOREL"))
        )

        self.fsm.act(
            # Send write command and store first 16bits
            "WSTOREL",

            write_port.awready.eq(0),
            write_port.wready.eq(0),
            write_port.bvalid.eq(0),

            # Send the SDRAM WRITE command,
            # with AUTO PRECHARGE to close this row if self.lastwrite is set
            sdram.ba.eq(self.writeaddr[22:24]),
            sdram.a[0:9].eq(self.writeaddr[0:9]),
            sdram.a[9].eq(0),
            sdram.a[10].eq(self.lastwrite),
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["WRITE"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["WRITE"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["WRITE"][2]),
            self.dqt.o.eq(self.writedata[0:16]),
            self.dqt.oe.eq(1),

            NextState("WSTOREH"),
        )

        self.fsm.act(
            # Store second 16bits
            "WSTOREH",

            write_port.awready.eq(0),
            write_port.wready.eq(0),
            write_port.bvalid.eq(0),

            # NOP the SDRAM
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            # Set second data to write
            self.dqt.o.eq(self.writedata[16:32]),
            self.dqt.oe.eq(1),

            # Sort out address increment if we're bursting
            If(self.wbursttype == BURST_TYPE_INCR,
               NextValue(self.writeaddr, self.writeaddr + 4)),
            NextValue(self.beatcount, self.beatcount + 1),

            NextValue(counter, 0),
            If(self.lastwrite, NextState("WRESPOND")).Else(NextState("WWAIT"))
        )

        self.fsm.act(
            "WRESPOND",
            write_port.awready.eq(0),
            write_port.wready.eq(0),
            write_port.bvalid.eq(1),
            write_port.bresp.eq(self.response),
            write_port.bid.eq(self.writeid),

            NextValue(counter, 0),
            If(write_port.bready, NextState("WRESPOND_WAIT"))
        )

        self.fsm.act(
            # Wait for the auto precharge to finish
            "WRESPOND_WAIT",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If(counter == timings['t_rp'],
               NextValue(counter, 0),
               NextState("IDLE")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "RPREPARE",

            # Acknowledge read request
            read_port.arready.eq(1),
            read_port.rvalid.eq(0),

            # Activate relevant row for this address
            sdram.ba.eq(self.writeaddr[22:24]),
            sdram.a.eq(self.writeaddr[9:22]),
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["ACT"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["ACT"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["ACT"][2]),

            If((self.rburstsize != BURST_SIZE_4)
               | (self.rbursttype == BURST_TYPE_WRAP),
               NextValue(self.response, RESP_SLVERR)).Else(
                    NextValue(self.response, RESP_OKAY)),

            NextValue(counter, 0),
            NextState("RPREPARE_WAIT")
        )

        self.fsm.act(
            "RPREPARE_WAIT",

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            If(counter == timings['t_rcd'],
               NextValue(counter, 0),
               NextState("RREAD")
               ).Else(
               NextValue(counter, counter + 1))
        )

        self.fsm.act(
            "RREAD",
            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            # Send the SDRAM READ command,
            # with AUTO PRECHARGE to close this row if rlast is set
            sdram.ba.eq(self.writeaddr[22:24]),
            sdram.a[0:9].eq(self.writeaddr[0:9]),
            sdram.a[9].eq(0),
            If(self.beatcount == self.rburstlen,
               sdram.a[10].eq(1)).Else(sdram.a[10].eq(0)),
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["READ"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["READ"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["READ"][2]),
            self.dqt.oe.eq(0),

            NextState("RREAD_WAIT"),
        )

        self.fsm.act(
            "RREAD_WAIT",

            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),
            self.dqt.oe.eq(0),

            NextState("RLOADL"),
        )

        self.fsm.act(
            "RLOADL",

            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),
            self.dqt.oe.eq(0),

            NextValue(self.readdata[0:16], self.dqt.i),

            NextState("RLOADH"),
        )

        self.fsm.act(
            "RLOADH",

            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),
            self.dqt.oe.eq(0),

            NextValue(self.readdata[16:32], self.dqt.i),

            NextState("RRESPOND"),
        )

        self.fsm.act(
            "RRESPOND",

            read_port.arready.eq(0),
            read_port.rvalid.eq(0),

            read_port.rid.eq(self.readid),
            read_port.rdata.eq(self.readdata),
            read_port.rresp.eq(self.response),
            read_port.rlast.eq(self.beatcount == self.rburstlen + 1),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),
            self.dqt.oe.eq(0),

            If(self.rbursttype == BURST_TYPE_INCR,
               NextValue(self.writeaddr, self.writeaddr + 4)),
            NextValue(self.beatcount, self.beatcount + 1),

            NextState("RRESPOND_WAIT"),
        )

        self.fsm.act(
            "RRESPOND_WAIT",
            read_port.arready.eq(0),
            read_port.rvalid.eq(1),
            read_port.rid.eq(self.readid),
            read_port.rdata.eq(self.readdata),
            read_port.rresp.eq(self.response),
            read_port.rlast.eq(self.beatcount == self.rburstlen + 1),

            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),
            self.dqt.oe.eq(0),

            If(read_port.rready,
                If(read_port.rlast,
                   NextState("IDLE")).Else(NextState("RREAD")))
        )

        self.fsm.act(
            "AUTOREFRESH",
            # Run auto-refresh cycles
            sdram.cs_n.eq(0),
            sdram.ras_n.eq(SDRAM_COMMANDS["REF"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["REF"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["REF"][2]),
            NextValue(auto_refresh_pending, 0),
            NextState("AUTOREFRESH_WAIT"),
        )

        self.fsm.act(
            "AUTOREFRESH_WAIT",
            sdram.cs_n.eq(1),
            sdram.ras_n.eq(SDRAM_COMMANDS["NOP"][0]),
            sdram.cas_n.eq(SDRAM_COMMANDS["NOP"][1]),
            sdram.we_n.eq(SDRAM_COMMANDS["NOP"][2]),

            If(counter == timings['t_rc'],
               NextValue(counter, 0),
               NextState("IDLE"),
               ).Else(
               NextValue(counter, counter + 1))
        )
