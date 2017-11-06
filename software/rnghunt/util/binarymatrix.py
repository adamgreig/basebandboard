"""
Generate test/reference results for testing Rust implementation.

Copyright 2017 Adam Greig
"""

import numpy as np


def random_binary_matrix(nrows, ncols):
    return np.random.randint(2, size=(nrows, ncols)).astype(np.uint8)


def random_binary_vector(n):
    return np.random.randint(2, size=(n, 1)).astype(np.uint8)


def pack_matrix(a):
    words = []
    for col in range(a.shape[1]):
        u8s = np.packbits(a.T[col])
        splits = 8*np.arange(1, int(np.ceil(a.shape[0]/64)))
        chunks = np.split(u8s, splits)
        for chunk in chunks:
            word = "".join("{:02X}".format(byte) for byte in chunk)
            words.append(word.ljust(16, "0"))
    return ", ".join("0x{}".format(word) for word in words)


if __name__ == "__main__":
    import sys
    nrows = int(sys.argv[1])
    ncols = int(sys.argv[2])
    a = random_binary_matrix(nrows, ncols)
    b = random_binary_vector(ncols)
    print("a:")
    print(a)
    print("a (list format):")
    print(a.tolist())
    print("a.T (list format):")
    print(a.T.tolist())
    print("a words:", pack_matrix(a))
    print("b:", b.T.tolist())
    print("a.b:", np.mod(np.dot(a, b), 2).T.tolist())
