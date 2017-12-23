"""
SDRAM controller for DE0-Nano with AXI3 slave interface.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, FSM, If, NextState, NextValue, Tristate


class SDRAM(Module):
    """
    SDRAM Controller to AXI3 slave.

    `read_port` is an AXI3ReadPort and must be connected to the AXI3 master.
    `write_port` is an AXI3WritePort and must be connected to the AXI3 master.
    `sdram` is an object with `a`, `ba`, `cs_n`, `cke`, `ras_n`, `cas_n`,
        `we_n`, `dq`, and `dm` signals which are connected to the SDRAM.
    `timings` contains SDRAM timing values in units of cycles:
        "powerup": power-up delay, 200µs.
    The SDRAM clock should be established externally to an appropriate phase
    advance over the clock for this module, at the same frequency.
    """
    def __init__(self, read_port, write_port, sdram, timings):
        # Set up the DQ tristate signal
        dqn = len(sdram.dq)
        dqo = Signal(dqn)
        dqoe = Signal()
        dqi = Signal(dqn)
        dqt = Tristate(sdram.dq, dqo, dqoe, dqi)

        # We'll just leave CKE asserted
        self.comb += sdram.cke.eq(1)

        # Controller state machine
        self.submodules.fsm = FSM(reset_state="POWERUP")
        powerup_counter = Signal(max=timings['powerup']+1)
        self.sync += powerup_counter.eq(powerup_counter + 1)

        self.fsm.act(
            "POWERUP",
            # Assert CKE but deassert CS_N for NOP during initialisation.
            sdram.cs_n.eq(1),
            sdram.dm.eq(0xFFFFFFFF),

            # Wait for initial powerup
            If(powerup_counter == timings['powerup'], NextState("INIT1"))
        )

        self.fsm.act(
            "INIT1"
            # Precharge all banks
            sdram.cs_n.eq(1),

