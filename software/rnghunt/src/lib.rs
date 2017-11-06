// Copyright 2017 Adam Greig

mod binary_vector;
mod binary_matrix;
mod binary_polynomial;
mod berlekamp_massey;

pub use binary_vector::BinaryVector;
pub use binary_matrix::BinaryMatrix;
pub use binary_polynomial::BinaryPolynomial;
pub use berlekamp_massey::berlekamp_massey;

/// Compute the number of u64 words required to store n bits.
#[inline(always)]
pub fn numwords(n: usize) -> usize {
    (n + 63) / 64
}
