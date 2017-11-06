use ::BinaryVector;

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
        let mut start = 0;
        for (idx, c) in coefficients.iter().enumerate() {
            if *c == 1 {
                start = idx;
                break;
            }
        }
        BinaryPolynomial { coefficients: BinaryVector::from_bits(&coefficients[start..]) }
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
        assert_eq!(p.coefficients.to_bits(), &[1, 0, 0, 0]);
        // x^0
        let p = BinaryPolynomial::from_coefficients(&[0, 0, 0, 0, 0, 0, 1]);
        assert_eq!(p.degree(), 0);
        assert_eq!(p.coefficients.to_bits(), &[1]);
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
}
