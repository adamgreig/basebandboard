use ::factors_data::FACTORS;
use ::BinaryVector;

/// Fetches a Vec of numbers r/k_i where k_i are the prime factors of r, starting from 1,
/// and r is 2^n - 1. Each number is represented as a BinaryVector with the MSbit first.
/// Requires 1<=n<=512.
pub fn get_factors(n: usize) -> Vec<BinaryVector> {
    assert!(n>=1);
    assert!(n<=512);
    let n_factors = FACTORS[n-1].len();
    let mut out = Vec::with_capacity(n_factors);
    for factor in FACTORS[n-1] {
        out.push(BinaryVector::from_words(factor.len() * 64, factor));
    }
    out
}
