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

b = np.random.randint(2, size=(n, 1)).astype(np.uint8)
seq = []
for _ in range(2*n):
    b = np.mod(np.dot(a, b), 2)
    seq.append(b[0][0])

print("Generated sequence:", "".join(str(x) for x in seq))
