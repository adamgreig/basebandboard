import sys
import numpy as np
import subprocess

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

subprocess.run(["./ppsearch", "bma={}".format("".join(str(x) for x in seq)),
                "testprimitivity"])

from PIL import Image
im = Image.fromarray(255 - a * 255)
im.save("out.png")

b = np.random.randint(2, size=(n, 1)).astype(np.uint8)
b0 = b.copy()
#out = []
nsamples = 200000
with open("outnums", "w") as f:
    f.write("""#==================================================================
# generator rnghunt  seed = 0
#==================================================================
type: d
count: {}
numbit: 32
""".format(nsamples*(n//32)))
    for _ in range(nsamples):
        b = np.mod(np.dot(a, b), 2)
        #out.append(int("".join(str(x) for x in b[:, 0]), 2))
        bitstring = "".join(str(x) for x in b[:, 0])
        for i in range(0, n, 32):
            word = int(bitstring[i:i+32], 2)
            f.write(str(word)+"\n")
