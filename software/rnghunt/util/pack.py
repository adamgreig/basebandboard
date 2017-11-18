import sys
import numpy as np

lines = []

for line in open(sys.argv[1]):
    lines.append(line.strip())

n = len(lines[0])
print("Detected n={}".format(n))
a = np.empty((n, n), dtype=np.uint8)
for rowidx in range(n):
    a[rowidx] = [int(x) for x in lines[rowidx]]
print("Loaded matrix")
print("Row weights:", a.sum(axis=1))
print("Col weights:", a.sum(axis=0))

packed = [np.where(a[i])[0].tolist() for i in range(n)]

print("Packed:\n[")
for subs in (packed[i:i+3] for i in range(0, n, 3)):
    print(*subs, sep=", ", end=",\n")
print("]")
