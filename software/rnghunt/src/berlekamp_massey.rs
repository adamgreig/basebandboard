use ::{BinaryVector, BinaryPolynomial, numwords};

/// Find the minimal polynomial which generates the sequence `s`,
/// using the Berlekamp-Massey algorithm.
pub fn berlekamp_massey(s: &BinaryVector) -> BinaryPolynomial {
    // c holds the candidate polynomial, initialised with highest coefficient set to 1.
    let mut c = BinaryPolynomial {
        coefficients: BinaryVector { n: 0, data: vec![0u64; numwords(s.n)] }
    };
    c.coefficients.data[0] = 0x8000_0000_0000_0000;
    let mut b = c.clone();
    let mut l = 0usize;
    let mut m = -1i32;
    for n in 0..s.n {
        let x = s.slice((s.n-n-1)..(s.n-n+l));
        c.coefficients.n = l+1;
        if c.eval(&x) == 1 {
            let t = c.clone();
            c.coefficients.n = s.n;
            b.coefficients.n = s.n;
            let offset = ((n as i32) - m) as usize;
            c.coefficients ^= (&b.coefficients >> offset).slice(0..s.n);
            if l <= n/2 {
                l = n + 1 - l;
                m = n as i32;
                b = t;
            }
        }
    }
    c
}

#[cfg(test)]
mod tests {
    use ::{BinaryVector, berlekamp_massey};

    #[test]
    fn test_berlekamp_massey() {
        // PRBS-9
        let s = BinaryVector::from_bitstring("0000100011000010011");
        let p = berlekamp_massey(&s);
        assert_eq!(format!("{}", p), "x^9 + x^5 + 1");

        // PRBS-11
        let s = BinaryVector::from_bitstring("00000000101000000100010");
        let p = berlekamp_massey(&s);
        assert_eq!(format!("{}", p), "x^11 + x^9 + 1");

        // Example LFSR with more taps from Wikipedia
        let s = BinaryVector::from_bitstring("01000100111000101110110000100011");
        let p = berlekamp_massey(&s);
        assert_eq!(format!("{}", p), "x^16 + x^14 + x^13 + x^11 + 1");
    }
}
