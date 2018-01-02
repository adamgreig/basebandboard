from ..rgb_lcd import AR1021TouchController
from migen import Signal, Module
from migen.sim import run_simulation


def test_touchscreen():

    class FakeTouchscreen(Module):
        def __init__(self):
            self.mosi = Signal()
            self.miso = Signal()
            self.cs = Signal()
            self.sclk = Signal()
            self.int = Signal()
    touchscreen = FakeTouchscreen()
    ar1021 = AR1021TouchController(touchscreen)

    def tb():
        for _ in range(100):
            yield
        yield touchscreen.int.eq(1)
        for _ in range(100):
            yield
        yield touchscreen.int.eq(0)
        for _ in range(3000):
            yield

    run_simulation(ar1021, tb(), vcd_name="touchscreen.vcd")
