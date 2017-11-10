use ::BinaryVector;
use ::factors::get_factors;

use std::ops::Index;
use std::fmt;

/// A polynomial over GF(2).
#[derive(Clone, Debug)]
pub struct BinaryPolynomial {
    pub coefficients: BinaryVector,
}

impl Index<usize> for BinaryPolynomial {
    type Output = bool;

    /// Fetch a specific coefficient in this polynomial
    fn index(&self, i: usize) -> &bool {
        &self.coefficients[i]
    }
}

impl fmt::Display for BinaryPolynomial {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let mut parts = Vec::new();
        for i in 0..self.coefficients.n {
            if self.coefficients[i] {
                let degree = self.coefficients.n - 1 - i;
                if degree == 0 {
                    parts.push("1".to_owned());
                } else if degree == 1 {
                    parts.push("x".to_owned());
                } else {
                    parts.push(format!("x^{}", degree));
                }
            }
        }

        if parts.len() == 0 {
            parts.push("0".to_owned());
        }

        write!(f, "{}", parts.join(" + "))
    }
}

impl BinaryPolynomial {
    /// Make a new BinaryPolynomial from the provided coefficients.
    ///
    /// `coefficients` is the slice `[c0, c1, c2, ..., cN]` that represent
    /// the polynomial `c0.x^N + c1.x^(N-1) + ... + cN`. Each entry must be 0 or 1.
    pub fn from_coefficients(coefficients: &[u8]) -> BinaryPolynomial {
        BinaryPolynomial { coefficients: BinaryVector::from_bits(coefficients) }
    }

    /// Return the degree of this polynomial, i.e. the highest non-zero-coefficient power.
    pub fn degree(&self) -> isize {
        for i in 0..self.coefficients.n {
            if self.coefficients[i] {
                return (self.coefficients.n - 1 - i) as isize;
            }
        }
        -1
    }

    /// Evaluate the polynomial on a specific sequence.
    ///
    /// The first bit in `x` corresponds to the highest power in the polynomial.
    /// The sequence must have the same length as the polynomial, i.e., x.n == p.degree()+1.
    pub fn eval(&self, x: &BinaryVector) -> u8 {
        assert_eq!(x.n as isize, self.degree()+1);
        assert_eq!(x.data.len(), self.coefficients.data.len());
        let mut parity = 0u8;
        // We want to find the inner product of the coefficients with x.
        // We can first compute the products by ANDing the underlying words together,
        // and then we just need the parity (even/odd number of bits set) in the result.
        for (idx, word) in self.coefficients.data.iter().enumerate() {
            let mut v = word & x.data[idx];
            v ^= v >> 32;
            v ^= v >> 16;
            v ^= v >> 8;
            v ^= v >> 4;
            parity ^= ((0x6996u64 >> (v & 0xf)) & 1) as u8;
        }
        parity
    }

    /// Evaluate the product with `g` mod `p`, returning the result as a new BinaryPolynomial.
    pub fn modmult(&self, g: &BinaryPolynomial, p: &BinaryPolynomial) -> BinaryPolynomial {
        // We have:
        // self = f(x) = a_n x^n + ... + a_1 x + a_0
        //    g = g(x) = b_n x^n + ... + b_1 x + b_0
        //
        // Write the product as
        // f(x).g(x)   = a_0.g(x) + a_1.x.g(x) + ... + a_n.x^n.g(x)
        //
        // Note that x.g(x) is just a left shift of the coefficients of g(x), so we can go
        // through each coefficient of f(x), and if it's 1, accumulate g(x), then always
        // left-shift g(x) by one to prepare it for the next coefficient check.
        //
        // To maintain the (mod p(x)) property, we check at each step if g(x) exceeds
        // the degree of p(x), and subtract p(x) if so.

        assert_eq!(self.coefficients.n, g.coefficients.n);
        assert_eq!(self.coefficients.n, p.coefficients.n);

        let degree_p = p.degree() as usize;

        // Take a copy of g as we'll be shifting it in-place.
        let mut gs = g.clone();

        // Prepare a result the same size as p but zeroed
        let mut r = p.clone();
        r.coefficients ^= &p.coefficients;

        // For each bit set in self, starting at the lowest...
        for bit in 1..((self.degree()+2) as usize) {
            // If this bit is set, we accumulate the current shifted version of g
            if self.coefficients[self.coefficients.n - bit] {
                r.coefficients ^= &gs.coefficients;
            }

            // Multiply gs by x. We have to increase the bit length as well.
            gs.coefficients <<= 1;
            gs.coefficients.n += 1;

            // Mod p(x)
            if gs.coefficients[gs.coefficients.n - degree_p - 1] {
                gs.coefficients ^= &p.coefficients;
            }
        }

        r
    }

    /// Evaluate x^k mod self. k is interpreted as a large binary integer.
    pub fn modexp(&self, k: &BinaryVector) -> BinaryPolynomial {
        // Start at f=1. Need to construct f with same length as self.
        let offset = (64 - (self.coefficients.n % 64)) % 64;
        let mut f = self.clone();
        f.coefficients ^= &self.coefficients;
        f.coefficients.data[self.coefficients.data.len()-1] = 1<<offset;

        if k.firstbit() == k.n {
            return f;
        }

        // Construct the polynomial x, also same length as self.
        let mut x = f.clone();
        x.coefficients.data[self.coefficients.data.len()-1] = 2<<offset;

        f.coefficients.data[self.coefficients.data.len()-1] = 2<<offset;

        // For each bit after the MSb in the binary expansion of k, we evaluate f <- f.f mod p,
        // and if that bit is 1, we further evaluate f <- x.f mod p, so by the end
        // we have evaluated x^k mod p, without ever exceeding the degree of p.
        for bit in (k.firstbit()+1)..k.n {
            f = f.modmult(&f, &self);
            if k[bit] {
                f = f.modmult(&x, &self);
            }
        }

        f
    }

    /// Checks if x^k mod self is integer (==1). k is interpreted as a large binary integer.
    pub fn check_integer(&self, k: &BinaryVector) -> bool {
        let f = self.modexp(k);

        // Construct the polynomial 1 with the same length as self.
        let offset = (64 - (self.coefficients.n % 64)) % 64;
        let mut one = self.clone();
        one.coefficients ^= &self.coefficients;
        one.coefficients.data[self.coefficients.data.len()-1] = 1<<offset;

        return f.coefficients.data == one.coefficients.data;
    }

    /// Evaluates if an irreducible polynomial is primitive.
    pub fn is_primitive(&self) -> bool {
        // No point checking 0-degree polynomials
        if self.degree() == -1 {
            return true;
        }

        // All primitive polynomials must have nonzero constant term
        if !self.coefficients[self.coefficients.n - 1] {
            return false;
        }

        // Must have an odd number of nonzero terms
        if self.coefficients.count_ones() % 2 != 1 {
            return false;
        }

        println!("Checking primitivity of {}, degree is {}", self, self.degree());
        let factors = get_factors(self.degree() as usize);
        println!("Got factors: {:?}", factors);

        // 2^k - 1 mod p must be 1 for k=degree(p)
        if !self.check_integer(&factors[0]) {
            return false;
        }

        for factor in &factors[1..] {
            println!("    Testing factor {}", factor);
            if self.check_integer(&factor) {
                println!("      Test failed, not primitive!");
                return false;
            }
        }
        println!("    All factors passed, primitive.");
        true
    }
}

#[cfg(test)]
mod tests {
    use ::{BinaryVector, BinaryPolynomial};

    #[test]
    fn test_degree() {
        // x^6 + x^5 + x^4 + x^3 + x^2 + x + 1
        let p = BinaryPolynomial::from_coefficients(&[1, 1, 1, 1, 1, 1, 1]);
        assert_eq!(p.degree(), 6);
        // x^3
        let p = BinaryPolynomial::from_coefficients(&[0, 1, 0, 0, 0]);
        assert_eq!(p.degree(), 3);
        // x^0
        let p = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 0, 0, 1]);
        assert_eq!(p.degree(), 0);
        // 0
        let p = BinaryPolynomial::from_coefficients(&[0]);
        assert_eq!(p.degree(), -1);
    }

    #[test]
    fn test_display() {
        let p = BinaryPolynomial::from_coefficients(&[1, 0, 0, 1, 1, 1, 1]);
        let s = format!("{}", p);
        assert_eq!(s, "x^6 + x^3 + x^2 + x + 1");

        let p = BinaryPolynomial::from_coefficients(&[0]);
        let s = format!("{}", p);
        assert_eq!(s, "0");
    }

    #[test]
    fn test_eval() {
        let p = BinaryPolynomial::from_coefficients(&[1, 0, 1, 0, 1, 1]);
        let x = BinaryVector::from_bits(&[1, 1, 1, 1, 1, 0]);
        let y = BinaryVector::from_bits(&[1, 1, 1, 1, 1, 1]);
        assert_eq!(p.eval(&x), 1);
        assert_eq!(p.eval(&y), 0);

        let v = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let p = BinaryPolynomial { coefficients: v };
        let x = BinaryVector::from_words(256, &[
            0x72A750F0B61C8083, 0xD6B446B28D7709F5, 0x4A2A35BB6B4A9D57, 0x36B60EF547DD7363]);
        assert_eq!(p.eval(&x), 1);
        let y = BinaryVector::from_words(256, &[
            0x6375252384DE2649, 0x15C4FC9E04004D91, 0x2FE1EF103A5A9D6D, 0xBA9BA69D6FE360E0]);
        assert_eq!(p.eval(&y), 0);
    }

    #[test]
    fn test_modmult() {
        // x^6 is suitably big to not have any effect
        let p = BinaryPolynomial::from_coefficients(&[1, 0, 0, 0, 0, 0, 0]);

        // f(x) = x^2
        let f = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 1, 0, 0]);

        // g(x) = x + 1
        let g = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 0, 1, 1]);

        // f(x) * g(x) = x^2 * (x+1) = x^3 + x^2
        let fg = f.modmult(&g, &p);
        assert_eq!(fg.coefficients.to_bits(), vec![0, 0, 0, 1, 1, 0, 0]);

        // Try a new test with squaring and multiplying by x and where p(x) becomes effective
        let p = BinaryPolynomial::from_coefficients(&[0, 1, 1, 0, 0, 1]);
        let mut f = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 1, 0]);
        let x = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 1, 0]);

        // x * x = x^2
        f = f.modmult(&f, &p);
        assert_eq!(f.coefficients.to_bits(), vec![0, 0, 0, 1, 0, 0]);

        // x^2 * x^2 = x^4, mod p(x) = x^3+1
        f = f.modmult(&f, &p);
        assert_eq!(f.coefficients.to_bits(), vec![0, 0, 1, 0, 0, 1]);

        // x^4 * x = x^5, mod p(x) = x^3 + x + 1
        f = f.modmult(&x, &p);
        assert_eq!(f.coefficients.to_bits(), vec![0, 0, 1, 0, 1, 1]);

        // Large polynomials
        let p = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x01000000_00000000, 0x00000000_00000000, 0x00000000_00000000, 0x00000000_00000000])};
        let f = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000000, 0x10000000_10000000, 0x10000000_10000000, 0x00000000_00000000])};
        let g = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000000, 0x00000000_00000000, 0x00000000_00000000, 0x00000000_00003010])};
        let fg = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000301, 0x00000301_00000301, 0x00000301_00000000, 0x00000000_00000000])};
        let result = f.modmult(&g, &p);
        assert_eq!(result.coefficients.data, fg.coefficients.data);
    }

    #[test]
    fn test_modexp() {
        // First test a few values with degree(p)>k so mod doesn't come into it.
        let p = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000001, 0x00000000_00000000, 0x00000000_00000000, 0x00000000_00000000])};
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[0]))), "1");
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[1]))), "x");
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[2]))), "x^2");
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[20]))), "x^20");
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[100]))), "x^100");

        // Test a few with an effective polynomial
        let p = BinaryPolynomial::from_coefficients(&[1, 1, 0, 0, 1]);
        assert_eq!(format!("{}", p.modexp(&BinaryVector::from_words(64, &[15]))), "1");
    }

    #[test]
    fn test_check_integer() {
        // x^4 + x^3 + 1, a primitive polynomial
        let p = BinaryPolynomial::from_coefficients(&[1, 1, 0, 0, 1]);
        // Since p is primitive, all x^k mod p for k<(2^4 - 1) should be non-integer,
        // while x^k for k=2^4 - 1 should be 1.
        for k in 1..15 {
            assert!(!p.check_integer(&BinaryVector::from_words(64, &[k])));
        }
        assert!(p.check_integer(&BinaryVector::from_words(64, &[15])));

        // x^200 + x^5 + x^3 + x^2 + 1, another primitive polynomial
        let p = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000100, 0x00000000_00000000, 0x00000000_00000000, 0x00000000_0000002d])};
        assert_eq!(format!("{}", p), "x^200 + x^5 + x^3 + x^2 + 1");
        // Try the first few. We don't have time to try 2^200 possibilities...
        for k in 1..100 {
            assert!(!p.check_integer(&BinaryVector::from_words(64, &[k])));
        }
        // 2^200 - 1 should be integer
        let r = BinaryVector::from_words(256, &[
            0xff, 0xffff_ffff_ffff_ffff, 0xffff_ffff_ffff_ffff, 0xffff_ffff_ffff_ffff]);
        assert!(p.check_integer(&r));
    }

    #[test]
    fn test_is_primitive() {
        // x^4 + x^3 + 1 is primitive
        let p = BinaryPolynomial::from_coefficients(&[1, 1, 0, 0, 1]);
        assert!(p.is_primitive());

        // x^4 + x^2 + x + 1 is not primitive (you can reduce it by x+1).
        let p = BinaryPolynomial::from_coefficients(&[1, 0, 1, 1, 1]);
        assert!(!p.is_primitive());

        // x^200 + x^5 + x^3 + x^2 + 1 is primitive
        let p = BinaryPolynomial { coefficients: BinaryVector::from_words(256, &[
            0x00000000_00000100, 0x00000000_00000000, 0x00000000_00000000, 0x00000000_0000002d])};
        assert!(p.is_primitive());
    }
}
