import numpy as np
import matplotlib.pyplot as plt

n = 256
logn = int(np.log2(n))
nsamp = 100000
samples = np.empty(nsamp, dtype=np.int16)
for sampidx in range(nsamp):
    x = np.random.randint(2, size=n).astype(np.int16)
    for level in range(logn):
        level_n = 2**(logn - level)
        y = np.zeros(level_n//2, dtype=np.int16)
        for pair in range(0, level_n, 2):
            y[pair//2] = x[pair] - x[pair+1]
        x = y
    samples[sampidx] = x

μt = 0
μs = np.mean(samples)
σt = np.sqrt(2**(logn - 2))
σs = np.sqrt(np.var(samples))
x = np.linspace(-n/2, n/2, 1000)
pdf_t = 1/np.sqrt(2*np.pi*σt**2) * np.exp(-(x-μt)**2 / (2*σt**2))
pdf_s = 1/np.sqrt(2*np.pi*σs**2) * np.exp(-(x-μs)**2 / (2*σs**2))
cdf_t = np.cumsum(pdf_t)
cdf_t /= cdf_t[-1]
cdf_s = np.cumsum(pdf_s)
cdf_s /= cdf_s[-1]

print("Theoretical mean μ={:.4e}, variance σ²={:.4e}.".format(μt, σt**2))
print("Sample mean μ={:.4e}, variance σ²={:.4e}.".format(μs, σs**2))

plt.subplot(2, 1, 1)
plt.hist(samples, bins=n, range=(-n//2, n//2), color='g', alpha=0.5,
         align='left', normed=True, label="Empirical PDF")
plt.plot(x, pdf_t, lw=3, color='k', alpha=0.6, label="Theoretical PDF")
plt.plot(x, pdf_s, lw=3, color='g', alpha=0.6, label="Matched Gaussian PDF")
plt.xlim((μt-4*σt, μt+4*σt))
plt.legend()
plt.grid()

plt.subplot(2, 1, 2)
plt.hist(samples, bins=n, range=(-n//2, n//2), color='g', alpha=0.5,
         normed=True, cumulative=True, align='left', label="Empirical CDF")
plt.plot(x, cdf_t, lw=3, color='k', alpha=0.6, label="Theoretical CDF")
plt.plot(x, cdf_s, lw=3, color='k', alpha=0.6, label="Matched Gaussian CDF")
plt.xlim((μt-4*σt, μt+4*σt))
plt.grid()

plt.show()
