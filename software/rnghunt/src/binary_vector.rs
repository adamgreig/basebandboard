// Copyright 2017 Adam Greig

use std::cmp::{PartialEq, Eq};
use std::ops::{Index, Range};
use std::ops::{BitXor, BitXorAssign, BitAnd, BitAndAssign, BitOr, BitOrAssign};
use std::ops::{Shl, ShlAssign, Shr, ShrAssign};
use std::fmt;

use ::numwords;

/// A binary matrix of length (n).
#[derive(Clone,Debug)]
pub struct BinaryVector {
    pub n: usize,

    /// Bits stored packed into u64 words, MSbit first. If `n` is not a multiple of 64,
    /// the final (least significant) bits of the final word are ignored.
    pub data: Vec<u64>,
}

impl Index<usize> for BinaryVector {
    type Output = bool;

    /// Fetch a specific bit in this vector
    fn index(&self, i: usize) -> &bool {
        assert!(i < self.n);
        if self.data[i/64] >> (63-(i%64)) & 1 == 1 {
            &true
        } else {
            &false
        }
    }
}

impl fmt::Display for BinaryVector {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.to_bitstring())
    }
}

impl<'a> BitAnd for &'a BinaryVector {
    type Output = BinaryVector;
    fn bitand(self, rhs: &BinaryVector) -> BinaryVector {
        assert_eq!(self.n, rhs.n);
        let mut data = self.data.clone();
        for wordidx in 0..numwords(self.n) {
            data[wordidx] &= rhs.data[wordidx];
        }
        BinaryVector { n: self.n, data: data }
    }
}

impl BitAndAssign for BinaryVector {
    fn bitand_assign(&mut self, rhs: Self) {
        assert_eq!(self.n, rhs.n);
        for wordidx in 0..numwords(self.n) {
            self.data[wordidx] &= rhs.data[wordidx];
        }
    }
}

impl<'a> BitOr for &'a BinaryVector {
    type Output = BinaryVector;
    fn bitor(self, rhs: &BinaryVector) -> BinaryVector {
        assert_eq!(self.n, rhs.n);
        let mut data = self.data.clone();
        for wordidx in 0..numwords(self.n) {
            data[wordidx] |= rhs.data[wordidx];
        }
        BinaryVector { n: self.n, data: data }
    }
}

impl BitOrAssign for BinaryVector {
    fn bitor_assign(&mut self, rhs: Self) {
        assert_eq!(self.n, rhs.n);
        for wordidx in 0..numwords(self.n) {
            self.data[wordidx] |= rhs.data[wordidx];
        }
    }
}

impl<'a> BitXor for &'a BinaryVector {
    type Output = BinaryVector;
    fn bitxor(self, rhs: &BinaryVector) -> BinaryVector {
        assert_eq!(self.n, rhs.n);
        let mut data = self.data.clone();
        for wordidx in 0..numwords(self.n) {
            data[wordidx] ^= rhs.data[wordidx];
        }
        BinaryVector { n: self.n, data: data }
    }
}

impl BitXorAssign for BinaryVector {
    fn bitxor_assign(&mut self, rhs: Self) {
        assert_eq!(self.n, rhs.n);
        for wordidx in 0..numwords(self.n) {
            self.data[wordidx] ^= rhs.data[wordidx];
        }
    }
}

impl<'a> Shl<usize> for &'a BinaryVector {
    type Output = BinaryVector;
    fn shl(self, i: usize) -> BinaryVector {
        assert!(i <= self.n);
        let n = self.n - i;
        let nwords = numwords(n);
        let offset = i % 64;
        if offset == 0 {
            BinaryVector { n: n, data: self.data[i/64..].to_owned() }
        } else {
            let mut data = vec![0u64; nwords];
            for idx in 0..nwords {
                let wordidx = (i+idx*64)/64;
                data[idx] = self.data[wordidx] << offset;
                if idx != (nwords - 1) || wordidx != (self.n-1)/64 {
                    data[idx] |= self.data[wordidx+1] >> (64-offset);
                }
            }
            BinaryVector { n: n, data: data }
        }
    }
}

impl ShlAssign<usize> for BinaryVector {
    fn shl_assign(&mut self, i: usize) {
        assert!(i <= self.n);
        self.n -= i;
        let offset = i % 64;
        if offset == 0 {
            self.data = self.data[i/64..].to_owned();
        } else {
            let nwords = numwords(self.n + i);
            for idx in 0..nwords {
                self.data[idx] <<= offset;
                if idx != nwords-1 {
                    self.data[idx] |= self.data[idx+1] >> (64-offset);
                }
            }
            self.data.truncate(nwords);
        }
    }
}

impl ShrAssign<usize> for BinaryVector {
    fn shr_assign(&mut self, i: usize) {
        self.n += i;
        let nwords = numwords(self.n);
        let offset = i % 64;
        let mut data = vec![0u64; i/64];
        data.extend_from_slice(&self.data);
        if nwords > data.len() {
            data.push(0u64);
        }
        self.data = data;
        if offset != 0 {
            for idx in (i/64..nwords).rev() {
                self.data[idx] >>= offset;
                if idx != 0 {
                    self.data[idx] |= self.data[idx-1] << (64-offset);
                }
            }
        }
    }
}

impl<'a> Shr<usize> for &'a BinaryVector {
    type Output = BinaryVector;
    fn shr(self, i: usize) -> BinaryVector {
        let n = self.n + i;
        let nwords = numwords(n);
        let offset = i % 64;
        if offset == 0 {
            let mut data = vec![0u64; i/64];
            data.extend_from_slice(&self.data);
            BinaryVector { n: n, data: data }
        } else {
            let mut data = vec![0u64; nwords];
            for (srcidx, dstidx) in ((i/64)..nwords).enumerate() {
                if srcidx > 0 {
                    data[dstidx] = self.data[srcidx-1] << (64-offset);
                }
                if dstidx != nwords-1 || srcidx < numwords(self.n) {
                    data[dstidx] |= self.data[srcidx] >> offset;
                }
            }
            BinaryVector { n: n, data: data }
        }
    }
}

impl PartialEq for BinaryVector {
    fn eq(&self, other: &BinaryVector) -> bool {
        if self.n == other.n {
            let mut eq: bool = true;
            let nwords = numwords(self.n);
            for wordidx in 0..(nwords-1) {
                eq &= self.data[wordidx] == other.data[wordidx];
            }
            if self.n % 64 != 0 {
                let mask = 0xFFFF_FFFF_FFFF_FFFF >> (64 - (self.n % 64));
                eq &= (self.data[nwords-1] & mask) == (other.data[nwords-1] & mask);
            } else {
                eq &= self.data[nwords-1] == other.data[nwords-1];
            }
            eq
        } else {
            false
        }
    }
}

impl Eq for BinaryVector {}

impl BinaryVector {
    /// Make a new BinaryVector from the given words (packed)
    ///
    /// `words` contains the packed bits, MSbit first, with the excess bits ignored.
    pub fn from_words(n: usize, words: &[u64]) -> BinaryVector {
        BinaryVector { n: n, data: words.to_owned() }
    }

    /// Make a new BinaryVector from the given bits (unpacked)
    ///
    /// `bits` contains just 0 and 1 entries, and the length of the vector is set to the
    /// length of this slice.
    pub fn from_bits(bits: &[u8]) -> BinaryVector {
        let n = bits.len();
        let mut data = vec![0u64; numwords(n)];
        for (idx, bit) in bits.iter().enumerate() {
            assert!(*bit == 0 || *bit == 1);
            if *bit == 1 {
                data[idx/64] |= 1<<(63-(idx%64));
            }
        }
        BinaryVector { n: n, data: data }
    }

    /// Make a new BinaryVector from a bitstring
    pub fn from_bitstring(bitstring: &str) -> BinaryVector {
        let mut bits = Vec::with_capacity(bitstring.len());
        for c in bitstring.chars() {
            assert!(c == '0' || c == '1');
            if c == '0' {
                bits.push(0);
            } else if c == '1' {
                bits.push(1);
            }
        }
        BinaryVector::from_bits(&bits)
    }

    /// Convert to unpacked bits
    pub fn to_bits(&self) -> Vec<u8> {
        let mut out = vec![0u8; self.n];
        for i in 0..self.n {
            if self[i] {
                out[i] = 1;
            }
        }
        out
    }

    /// Convert to a String of 0/1
    pub fn to_bitstring(&self) -> String {
        let mut s = String::with_capacity(self.n);
        for bit in self.to_bits() {
            if bit == 0 {
                s.push('0');
            } else {
                s.push('1');
            }
        }
        s
    }

    /// Make a new BinaryVector from a range into the current one
    pub fn slice(&self, range: Range<usize>) -> BinaryVector {
        let start = range.start;
        let end = range.end;
        assert!(end >= start);
        assert!(end <= self.n);
        let n = end - start;
        let nwords = numwords(n);
        let offset = start % 64;

        if offset == 0 {
            // Short circuit the case where start is aligned to whole words
            let data = self.data[start/64..(end+63)/64].to_owned();
            BinaryVector { n: n, data: data }
        } else {
            let mut data = vec![0u64; nwords];
            for idx in 0..nwords {
                let wordidx = (start+idx*64)/64;
                data[idx] = self.data[wordidx] << offset;
                if idx != (nwords - 1) || wordidx != (end-1)/64 {
                    data[idx] |= self.data[wordidx+1] >> (64 - offset);
                }
            }
            BinaryVector { n: n, data: data }
        }
    }
}

#[cfg(test)]
mod tests {
    use ::BinaryVector;

    #[test]
    fn test_index() {
        let x = BinaryVector { n: 8, data: vec![0x8300_0000_0000_0000] };
        assert_eq!(x[0], true);
        assert_eq!(x[1], false);
        assert_eq!(x[2], false);
        assert_eq!(x[3], false);
        assert_eq!(x[4], false);
        assert_eq!(x[5], false);
        assert_eq!(x[6], true);
        assert_eq!(x[7], true);
    }

    #[test]
    fn test_to_bits() {
        // Test short vector
        let x = BinaryVector { n: 8, data: vec![0x8300_0000_0000_0000] };
        assert_eq!(x.to_bits(), vec![1, 0, 0, 0, 0, 0, 1, 1]);

        // Test word-length vector
        let x = BinaryVector { n: 64, data: vec![0x9F8344A4F44D6D10] };
        assert_eq!(x.to_bits(), vec![
            1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0,
            1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0,
            0, 1, 0, 0, 0, 0]);

        // Test greater than word-length vector
        let x = BinaryVector { n: 96, data: vec![0x883C385E66BD8704, 0xE43A5DF300000000] };
        assert_eq!(x.to_bits(), vec![
            1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1,
            1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0,
            0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0,
            1, 1, 1, 1, 1, 0, 0, 1, 1]);
    }

    #[test]
    fn test_from_words() {
        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        assert_eq!(x.to_bits(), vec![
            1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1,
            1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0,
            0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0,
            1, 1, 1, 1, 1, 0, 0, 1, 1]);
    }

    #[test]
    fn test_from_bits() {
        let x = BinaryVector::from_bits(&[
            1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0,
            1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0,
            0, 1, 0, 0, 0, 0]);
        assert_eq!(x.data, vec![0x9F8344A4F44D6D10]);
    }

    #[test]
    fn test_from_bitstring() {
        let x = BinaryVector::from_bitstring("0000000100100011010001010110011110001001");
        assert_eq!(x.data, vec![0x0123456789000000]);
    }

    #[test]
    fn test_to_bitstring() {
        let s = "0000000100100011010001010110011110001001";
        let x = BinaryVector::from_bitstring(&s);
        assert_eq!(x.to_bitstring(), s.to_owned());
    }

    #[test]
    fn test_slice() {
        let x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let bits = x.to_bits();
        assert_eq!(x.slice(0..1).to_bits(), bits[0..1].to_owned());
        assert_eq!(x.slice(1..2).to_bits(), bits[1..2].to_owned());
        assert_eq!(x.slice(0..2).to_bits(), bits[0..2].to_owned());
        assert_eq!(x.slice(4..8).to_bits(), bits[4..8].to_owned());
        assert_eq!(x.slice(60..70).to_bits(), bits[60..70].to_owned());
        assert_eq!(x.slice(60..130).to_bits(), bits[60..130].to_owned());
        assert_eq!(x.slice(1..255).to_bits(), bits[1..255].to_owned());
        assert_eq!(x.slice(64..256).to_bits(), bits[64..256].to_owned());
        assert_eq!(x.slice(64..128).to_bits(), bits[64..128].to_owned());
        assert_eq!(x.slice(64..129).to_bits(), bits[64..129].to_owned());
        assert_eq!(x.slice(255..256).to_bits(), bits[255..256].to_owned());
        assert_eq!(x.slice(0..256).to_bits(), bits[0..256].to_owned());
    }

    #[test]
    fn test_bitand() {
        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 & 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 & 0x38A599C200000000]);
        assert_eq!(&x & &y, z);
    }

    #[test]
    fn test_bitandassign() {
        let mut x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        x &= y;
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 & 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 & 0x38A599C200000000]);
        assert_eq!(x, z);
    }

    #[test]
    fn test_bitor() {
        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 | 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 | 0x38A599C200000000]);
        assert_eq!(&x | &y, z);
    }

    #[test]
    fn test_bitorassign() {
        let mut x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        x |= y;
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 | 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 | 0x38A599C200000000]);
        assert_eq!(x, z);
    }

    #[test]
    fn test_bitxor() {
        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 ^ 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 ^ 0x38A599C200000000]);
        assert_eq!(&x ^ &y, z);
    }

    #[test]
    fn test_bitxorassign() {
        let mut x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        x ^= y;
        let z = BinaryVector::from_words(96, &[0x883C385E66BD8704 ^ 0xA8F3B1900CC10FFF,
                                               0xE43A5DF300000000 ^ 0x38A599C200000000]);
        assert_eq!(x, z);
    }

    #[test]
    fn test_shl() {
        let x = BinaryVector::from_bits(&[0, 1, 0, 1, 1, 0, 1, 1]);
        assert_eq!((&x << 1).to_bits(), vec![1, 0, 1, 1, 0, 1, 1]);
        assert_eq!((&x << 2).to_bits(), vec![0, 1, 1, 0, 1, 1]);
        assert_eq!((&x << 3).to_bits(), vec![1, 1, 0, 1, 1]);
        assert_eq!((&x << 4).to_bits(), vec![1, 0, 1, 1]);
        assert_eq!((&x << 5).to_bits(), vec![0, 1, 1]);
        assert_eq!((&x << 6).to_bits(), vec![1, 1]);
        assert_eq!((&x << 7).to_bits(), vec![1]);
        assert_eq!((&x << 8).to_bits(), vec![]);

        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(92, &[0x83C385E66BD8704E, 0x43A5DF3000000000]);
        let z = BinaryVector::from_words(32, &[0xE43A5DF300000000]);
        assert_eq!(&x << 4, y);
        assert_eq!(&x << 64, z);

        let x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let y = BinaryVector::from_words(248, &[
            0xF3B1900CC10FFF38, 0xA599C25A5F60A25B, 0xC898AB15066BA444, 0xF3A512D7C744EC00]);
        let z = BinaryVector::from_words(128, &[
            0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        assert_eq!(&x << 8, y);
        assert_eq!(&x << 128, z);
    }

    #[test]
    fn test_shl_assign() {
        let mut x = BinaryVector::from_bits(&[0, 1, 0, 1, 1, 0, 1, 1]);
        x <<= 4;
        assert_eq!(x.to_bits(), vec![1, 0, 1, 1]);

        let mut x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(92, &[0x83C385E66BD8704E, 0x43A5DF3000000000]);
        x <<= 4;
        assert_eq!(x, y);

        let mut x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let z = BinaryVector::from_words(32, &[0xE43A5DF300000000]);
        x <<= 64;
        assert_eq!(x, z);

        let mut x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let y = BinaryVector::from_words(248, &[
            0xF3B1900CC10FFF38, 0xA599C25A5F60A25B, 0xC898AB15066BA444, 0xF3A512D7C744EC00]);
        x <<= 8;
        assert_eq!(x, y);

        let mut x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let z = BinaryVector::from_words(128, &[
            0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        x <<= 128;
        assert_eq!(x, z);
    }

    #[test]
    fn test_shr() {
        let x = BinaryVector::from_bits(&[0, 1, 0, 1, 1, 0, 1, 1]);
        assert_eq!((&x >> 1).to_bits(), vec![0, 0, 1, 0, 1, 1, 0, 1, 1]);
        assert_eq!((&x >> 2).to_bits(), vec![0, 0, 0, 1, 0, 1, 1, 0, 1, 1]);
        assert_eq!((&x >> 3).to_bits(), vec![0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 1]);

        let x = BinaryVector::from_words(96,  &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(100, &[0x0883C385E66BD870, 0x4E43A5DF30000000]);
        let z = BinaryVector::from_words(160, &[0x0000000000000000, 0x883C385E66BD8704,
                                                0xE43A5DF300000000]);
        assert_eq!(&x >> 4, y);
        assert_eq!(&x >> 64, z);

        let x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let y = BinaryVector::from_words(264, &[
            0x00A8F3B1900CC10F, 0xFF38A599C25A5F60, 0xA25BC898AB15066B, 0xA444F3A512D7C744,
            0xEC00000000000000]);
        let z = BinaryVector::from_words(384, &[
            0x0000000000000000, 0x0000000000000000,
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        assert_eq!(&x >> 8, y);
        assert_eq!(&x >> 128, z);
    }

    #[test]
    fn test_shr_assign() {
        let mut x = BinaryVector::from_bits(&[0, 1, 0, 1, 1, 0, 1, 1]);
        x >>= 3;
        assert_eq!(x.to_bits(), vec![0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 1]);

        let mut x = BinaryVector::from_words(96,  &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(100, &[0x0883C385E66BD870, 0x4E43A5DF30000000]);
        x >>= 4;
        assert_eq!(x, y);

        let mut x = BinaryVector::from_words(96,  &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let z = BinaryVector::from_words(160, &[0x0000000000000000, 0x883C385E66BD8704,
                                                0xE43A5DF300000000]);
        x >>= 64;
        assert_eq!(x, z);

        let mut x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let y = BinaryVector::from_words(264, &[
            0x00A8F3B1900CC10F, 0xFF38A599C25A5F60, 0xA25BC898AB15066B, 0xA444F3A512D7C744,
            0xEC00000000000000]);
        x >>= 8;
        assert_eq!(x, y);

        let mut x = BinaryVector::from_words(256, &[
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        let z = BinaryVector::from_words(384, &[
            0x0000000000000000, 0x0000000000000000,
            0xA8F3B1900CC10FFF, 0x38A599C25A5F60A2, 0x5BC898AB15066BA4, 0x44F3A512D7C744EC]);
        x >>= 128;
        assert_eq!(x, z);
    }

    #[test]
    fn test_eq() {
        let x = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let y = BinaryVector::from_words(96, &[0x883C385E66BD8704, 0xE43A5DF300000000]);
        let z = BinaryVector::from_words(96, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        let w = BinaryVector::from_words(97, &[0xA8F3B1900CC10FFF, 0x38A599C200000000]);
        assert_eq!(x, y);
        assert_ne!(y, z);
        assert_ne!(z, w);
    }
}
