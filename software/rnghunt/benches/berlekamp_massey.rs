// Copyright 2017 Adam Greig

#![feature(test)]
extern crate test;
use test::Bencher;

extern crate rnghunt;
use rnghunt::{BinaryVector, berlekamp_massey, old_berlekamp_massey};

#[bench]
fn bench_bm_old(b: &mut Bencher) {
    let s = BinaryVector::from_bitstring("01000100111000101110110000100011");
    b.iter(|| { old_berlekamp_massey(&s); });
}

#[bench]
fn bench_bm_new(b: &mut Bencher) {
    let s = BinaryVector::from_bitstring("01000100111000101110110000100011");
    b.iter(|| { berlekamp_massey(&s); });
}
