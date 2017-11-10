x = 0xACE1

for _ in range(32):
    # Taps on the 16th (rightmost, LSbit), 14th, 13th, 11th bits.
    newbit = ((x >> 0) ^ (x >> 2) ^ (x >> 3) ^ (x >> 5)) & 1
    x = (x >> 1) | (newbit << 15)
    print(newbit, end='')

print()

x = 0x1111111111111111
for _ in range(128):
    # Taps at 64, 62, 61, 1 bits.
    newbit = ((x >> 0) ^ (x >> 2) ^ (x >> 3) ^ (x >> 63)) & 1
    x = (x >> 1) | (newbit << 63)
    print(newbit, end='')
print()
