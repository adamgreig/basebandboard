"""
A UART transmitter.

Copyright 2017 Adam Greig
"""

from migen import Module, Signal, If, FSM, NextValue, NextState, Array, Cat


class UARTTx(Module):
    """
    UART Transmitter.
    """
    def __init__(self, divider, data, start):
        """
        `divider`: amount to divide clock by for baud rate, constant.
        `data`: 8bit Signal containing data to transmit.
        `start`: pulse high to begin transmission, for at least one bit period.
                 Ideally assert `start` until `self.ready` is deasserted.

        `self.ready`: asserted high when idle, deasserted during transmission.
        `self.tx_out`: the output serial data
        """
        self.ready = Signal(reset=1)
        self.tx_out = Signal(reset=1)

        # Baud rate clock generator
        self.div = Signal(max=divider - 1)
        self.baud = Signal()
        self.sync += If(
            self.div == divider - 1,
            self.div.eq(0),
            self.baud.eq(1),
        ).Else(
            self.div.eq(self.div + 1),
            self.baud.eq(0)
        )

        # Transmitter state machine
        self.bitno = Signal(3)
        self.data = Array(data)
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.comb += self.ready.eq(self.fsm.ongoing("IDLE"))
        self.fsm.act(
            "IDLE",
            self.tx_out.eq(1),
            If(self.baud & start, NextState("START"))
        )
        self.fsm.act(
            "START",
            self.tx_out.eq(0),
            NextValue(self.bitno, 0),
            If(self.baud, NextState("DATA"))
        )
        self.fsm.act(
            "DATA",
            self.tx_out.eq(self.data[self.bitno]),
            If(
                self.baud,
                NextValue(self.bitno, self.bitno + 1),
                If(self.bitno == 7, NextState("STOP"))
            )
        )
        self.fsm.act(
            "STOP",
            self.tx_out.eq(1),
            If(self.baud, NextState("IDLE"))
        )


class UARTTxFromMemory(Module):
    """
    Given a port into a memory, provide for dumping the memory over a UART.
    """
    def __init__(self, divider, port, width, startadr, stopadr, trigger):
        """
        `divider`: the UART baud rate divider (=clk/baud)
        `port`: a port to a Memory instance
        `width`: the width of the memory words, in bits
        `startadr`: the first address to transmit
        `stopadr`: the last address to transmit, must be stopadr > startadr.
        `trigger`: transmission begins when pulsed high

        `self.ready`: low while transmitting
        `self.tx_out`: the TX output
        """
        self.ready = Signal()
        self.tx_out = Signal()

        self.uart_data = Signal(8)
        self.uart_start = Signal()
        self.submodules.uart = UARTTx(divider, self.uart_data, self.uart_start)
        self.comb += self.tx_out.eq(self.uart.tx_out)

        self.adr = Signal(max=stopadr+2)
        self.word = Signal(width)
        self.worda = Array(self.word)
        self.bitidx = Signal(max=width+8)
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.comb += self.ready.eq(self.fsm.ongoing("IDLE"))
        self.fsm.act(
            "IDLE",
            NextValue(self.adr, startadr),
            If(trigger, NextState("SETUP_READ"))
        )
        self.fsm.act(
            "SETUP_READ",
            NextValue(port.adr, self.adr),
            NextState("WAIT_READ")
        )
        self.fsm.act(
            "WAIT_READ",
            NextState("STORE_READ")
        )
        self.fsm.act(
            "STORE_READ",
            #NextValue(self.word, (port.dat_r & 0xFFFFFF) | (self.adr << 24)),
            NextValue(self.word, port.dat_r),
            NextValue(self.adr, self.adr + 1),
            NextValue(self.bitidx, 0),
            NextState("SETUP_WRITE"),
        )
        self.fsm.act(
            "SETUP_WRITE",
            NextValue(self.uart_data,
                      Cat(
                          self.worda[self.bitidx+0],
                          self.worda[self.bitidx+1],
                          self.worda[self.bitidx+2],
                          self.worda[self.bitidx+3],
                          self.worda[self.bitidx+4],
                          self.worda[self.bitidx+5],
                          self.worda[self.bitidx+6],
                          self.worda[self.bitidx+7])),
            NextValue(self.uart_start, 1),
            If(self.uart.ready == 0, NextState("WAIT_WRITE"))
        )
        self.fsm.act(
            "WAIT_WRITE",
            NextValue(self.uart_start, 0),
            If(self.uart.ready, NextState("FINISH_WRITE"))
        )
        self.fsm.act(
            "FINISH_WRITE",
            If(
                self.bitidx + 8 >= width,
                If(
                    self.adr == stopadr + 1,
                    NextState("IDLE")
                ).Else(
                    NextState("SETUP_READ")
                )
            ).Else(
                NextValue(self.bitidx, self.bitidx + 8),
                NextState("SETUP_WRITE")
            )
        )


class DataToMem(Module):
    def __init__(self, data, port, count, trigger):
        """
        `data`: signal to save each clock
        `port`: Memory port to write to
        `count`: how many samples to save each trigger
        `trigger`: saving to memory starts on trigger
        """
        self.ready = Signal()
        self.ctr = Signal(max=count)
        self.comb += port.adr.eq(self.ctr)
        self.comb += port.dat_w.eq(data)
        self.submodules.fsm = FSM(reset_state="IDLE")
        self.comb += port.we.eq(self.fsm.ongoing("RUN"))
        self.fsm.act(
            "IDLE",
            NextValue(self.ctr, 0),
            If(trigger, NextState("RUN"))
        )
        self.fsm.act(
            "RUN",
            NextValue(self.ctr, self.ctr + 1),
            If(self.ctr + 1 == count, NextState("IDLE")),
        )
        self.comb += self.ready.eq(self.fsm.ongoing("IDLE"))


def test_uart_tx():
    from migen.sim import run_simulation
    divider = 10
    data = Signal(8)
    start = Signal()
    tx = UARTTx(divider, data, start)
    txout = []

    def tb():
        teststring = "Hello World"
        for val in [ord(x) for x in teststring]:
            yield (data.eq(val))
            yield (start.eq(1))
            while (yield tx.ready):
                yield
            yield (start.eq(0))
            while not (yield tx.ready):
                txout.append((yield tx.tx_out))
                yield

        expected_bits = []
        for c in [ord(x) for x in teststring]:
            # Start bit
            expected_bits.append(0)
            # Data, LSbit first
            for bit in "{:08b}".format(c)[::-1]:
                expected_bits.append(int(bit))
            # Stop bit
            expected_bits.append(1)

        assert txout[::divider] == expected_bits

    run_simulation(tx, tb())


def test_uart_tx_from_memory():
    from migen.sim import run_simulation
    from migen import Memory

    # Store some string in the memory, shifted left by 4 so each
    # character takes up 12 bits.
    teststring = "XXTEST1234XX"
    mem = Memory(12, 12, [ord(x) << 4 for x in teststring])
    port = mem.get_port()

    divider = 10
    trigger = Signal()
    uartfrommem = UARTTxFromMemory(divider, port, 12, 2, 10, trigger)

    uartfrommem.specials += [mem, port]
    txout = []

    def tb():
        yield
        yield (trigger.eq(1))
        yield
        while (yield uartfrommem.ready):
            yield
        while not (yield uartfrommem.ready):
            if (yield uartfrommem.uart.baud):
                txout.append((yield uartfrommem.tx_out))
            yield

        # Generate the bits we expect to see, considering both the left
        # shift of the string and the start and end addresses given to
        # the UARTTxFromMemory.
        expected_bits = [1]
        for c in [ord(x) << 4 for x in teststring[2:11]]:
            # Start bit
            expected_bits.append(0)
            # Data, LSbit first, bottom byte
            for bit in "{:08b}".format(c & 0xFF)[::-1]:
                expected_bits.append(int(bit))
            # Stop bit, inter-byte idle bit as we prepare the next byte
            expected_bits.append(1)
            expected_bits.append(1)

            # Start bit
            expected_bits.append(0)
            # Data, LSbit first, top byte
            for bit in "{:08b}".format((c & 0xFF00) >> 8)[::-1]:
                expected_bits.append(int(bit))
            # Stop bit, inter-byte idle bit as we prepare the next byte
            expected_bits.append(1)
            expected_bits.append(1)

        assert txout == expected_bits[:-1]

    run_simulation(uartfrommem, tb())


def test_uart_tx_from_memory_width8():
    from migen.sim import run_simulation
    from migen import Memory

    # Store some string in the memory, shifted left by 4 so each
    # character takes up 12 bits.
    teststring = "0123456789ABCDEF"
    mem = Memory(12, 16, [ord(x) for x in teststring])
    port = mem.get_port()

    divider = 10
    trigger = Signal()
    uartfrommem = UARTTxFromMemory(divider, port, 8, 0, 15, trigger)

    uartfrommem.specials += [mem, port]
    txout = []

    def tb():
        yield
        yield (trigger.eq(1))
        yield
        while (yield uartfrommem.ready):
            yield
        while not (yield uartfrommem.ready):
            if (yield uartfrommem.uart.baud):
                txout.append((yield uartfrommem.tx_out))
            yield

        # Generate the bits we expect to see
        expected_bits = [1]
        for c in [ord(x) for x in teststring]:
            # Start bit
            expected_bits.append(0)
            # Data, LSbit first, bottom byte
            for bit in "{:08b}".format(c)[::-1]:
                expected_bits.append(int(bit))
            # Stop bit, inter-byte idle bit as we prepare the next byte
            expected_bits.append(1)
            expected_bits.append(1)

        assert txout == expected_bits[:-1]

    run_simulation(uartfrommem, tb(), vcd_name="dump.vcd")


def test_data_to_mem():
    from migen.sim import run_simulation
    from migen import Memory
    data = Signal(8)
    mem = Memory(8, 128)
    port = mem.get_port(write_capable=True)
    trigger = Signal()
    tomem = DataToMem(data, port, 100, trigger)
    tomem.specials += [mem, port]

    mem_contents = []

    def tb():
        for _ in range(10):
            yield
        yield (trigger.eq(1))
        for x in range(200):
            yield(data.eq(x))
            yield
            yield (trigger.eq(0))

        for x in range(128):
            mem_contents.append((yield mem[x]))

        assert mem_contents == list(range(1, 101)) + [0]*28

    run_simulation(tomem, tb())
