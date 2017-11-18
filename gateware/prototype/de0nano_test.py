import numpy as np
from migen import Module, Signal, ClockDomain
from migen.build.platforms import de0nano
from rng import LUTOPT, CLTGRNG
from prbs import PRBS
from bitshaper import PRBSShaper

plat = de0nano.Platform()
gpio0 = plat.request("gpio_0")
gpio1 = plat.request("gpio_1")
clk50 = plat.request("clk50")

packed = [
    [6, 24, 41, 99], [5, 42, 89, 112], [36, 54, 110, 122], [16, 63, 86, 94],
    [23, 31, 71, 111], [19, 81, 123, 125], [4, 15, 45, 72], [22, 44, 66, 109],
    [90, 92, 105, 119], [9, 18, 100, 101], [48, 52, 61, 83], [21, 56, 82, 93],
    [7, 40, 47, 87], [12, 88, 113, 121], [67, 103, 114, 118],
    [55, 95, 108, 115], [1, 17, 26, 91], [25, 34, 50, 51], [10, 65, 74, 96],
    [58, 78, 124], [27, 29, 39, 104], [13, 79, 107], [35, 37, 70, 106],
    [43, 64, 69, 77], [32, 53, 73, 117], [2, 3, 98, 102], [0, 62, 80, 127],
    [46, 84, 85, 120], [14, 33, 49, 68], [11, 59, 116], [28, 30, 76],
    [8, 20, 97], [38, 57, 60, 75], [29, 60, 92, 126], [11, 21, 52, 121],
    [70, 76, 102, 109], [10, 35, 67, 111], [30, 55, 56, 96], [20, 23, 83, 122],
    [0, 72, 77, 126], [6, 17, 46, 98], [2, 4, 8, 31], [42, 87, 99, 101],
    [44, 73, 91, 124], [47, 103, 110, 120], [14, 48, 65, 69],
    [71, 90, 104, 112], [19, 27, 64], [25, 28, 66, 80], [45, 54, 75, 119],
    [57, 89, 114, 117], [12, 49, 74, 84], [24, 68, 81, 107], [18, 63, 85, 93],
    [3, 26, 36, 118], [7, 43, 50, 127], [1, 16, 32, 106], [34, 62, 88, 100],
    [13, 15, 22, 78], [38, 58, 59, 108], [37, 39, 79, 95], [9, 40, 53, 61],
    [41, 51, 86, 115], [5, 82, 97, 123], [105, 113, 116, 125],
    [33, 67, 94, 101], [5, 11, 49, 115], [6, 75, 90, 127], [39, 92, 94, 123],
    [25, 40, 86, 103], [0, 29, 51], [41, 55, 124], [16, 23, 70, 73],
    [24, 36, 66, 105], [62, 79, 119, 121], [31, 104, 109, 125],
    [20, 58, 107, 113], [65, 74, 117, 120], [27, 32, 57, 116],
    [7, 22, 84, 112], [15, 28, 68, 102], [3, 17, 82, 83], [2, 4, 14, 53],
    [18, 38, 95, 108], [12, 56, 59, 64], [1, 34, 44, 85], [10, 54, 87, 89],
    [33, 37, 46, 110], [26, 71, 93, 100], [8, 60, 69, 122], [9, 35, 63, 96],
    [48, 52, 78], [47, 80, 99, 111], [72, 97, 98, 114], [81, 91, 106],
    [21, 30, 126], [13, 19, 50, 61], [45, 77, 88, 118], [8, 42, 43, 76],
    [40, 59, 92, 109], [55, 56, 107, 113], [48, 90, 116, 120], [6, 7, 19, 108],
    [28, 50, 82, 126], [72, 84, 99], [47, 62, 63, 102], [31, 33, 43, 110],
    [35, 52, 97, 111], [1, 93, 94, 121], [0, 41, 54, 81], [15, 30, 85, 100],
    [16, 29, 51, 106], [23, 44, 91, 119], [3, 10, 37, 74], [11, 38, 42, 70],
    [27, 69, 88, 115], [83, 118, 125], [20, 22, 26, 80], [32, 34, 61, 112],
    [53, 67, 68, 117], [21, 73, 77, 105], [36, 46, 64, 75], [9, 18, 25, 127],
    [58, 76, 78, 101], [13, 14, 39, 79], [17, 65, 87, 96], [57, 60, 71, 98],
    [24, 104, 123, 124]]

n = len(packed)
logn = int(np.log2(n))
urng = LUTOPT.from_packed(packed)
grng = CLTGRNG(urng)

prbs = PRBS(9)
t = np.arange(-32, 32)
β = 0.5
c = 1/8 * np.sinc(t/8) * np.cos(np.pi * β * t/8)/(1-((2*β*t/8)**2))
c[t == 8/(2*β)] = c[t == -8/(2*β)] = np.pi/(4*8) * np.sinc(1/(2*β))
c = (c*1700).astype(np.int)
c = c.tolist()
setsel = Signal(5, reset=0)
shaper = PRBSShaper(prbs, setsel, [c]*32)


m = Module()
m.clock_domains.sys = ClockDomain("sys")
m.comb += m.sys.clk.eq(clk50)
m.sync += setsel.eq(gpio1[:5])
m.submodules.grng = grng
m.comb += gpio0[12:logn].eq(m.grng.x)
m.submodules.shaper = shaper
m.comb += gpio0[:12].eq(m.shaper.x)

if __name__ == "__main__":
    plat.build(m)
    prog = plat.create_programmer()
    prog.load_bitstream("build/top.sof")