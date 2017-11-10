// Copyright 2017 Adam Greig

use rand;
use rand::distributions::{IndependentSample, Range};
use ::{BinaryVector, numwords};

/// A binary matrix of shape (nrows, ncols).
#[derive(Clone,Debug)]
pub struct BinaryMatrix {
    pub nrows: usize,
    pub ncols: usize,
    pub words_per_col: usize,

    /// Bits are stored packed into u64 words going down the columns, MSbit first. The first word
    /// represents the first 64 bits of the first column. If `nrows` is not a multiple of 64, the
    /// final word for each column is zero-padded in the LSbits, so that each column begins on
    /// a word boundary.
    pub data: Vec<u64>,
}

impl BinaryMatrix {

    /// Construct a BinaryMatrix from the given u64 words, which store the matrix bits
    /// in column-major form (i.e., the first word is the first 64 bits of the first
    /// column of the matrix, with the bit from the first row corresponding to the MSb).
    /// If the number of rows is not a multiple of 64, the final word for each column
    /// is zero-padded in the lower bits, so that each column starts on a word boundary.
    pub fn from_words(nrows: usize, ncols: usize, words: &[u64]) -> BinaryMatrix {
        BinaryMatrix { nrows: nrows, ncols: ncols, words_per_col: numwords(nrows),
                       data: words.to_owned() }
    }

    /// Return a BinaryVector corresponding to the specified column of the BinaryMatrix.
    pub fn col(&self, col: usize) -> BinaryVector {
        let idx1 = col * self.words_per_col;
        let idx2 = (col+1) * self.words_per_col;
        BinaryVector { n: self.nrows, data: self.data[idx1..idx2].to_owned() }
    }

    /// Return a BinaryVector corresponding to the specified row of the BinaryMatrix.
    pub fn row(&self, row: usize) -> BinaryVector {
        let mut out = vec![0u64; numwords(self.ncols)];
        for col in 0..self.ncols {
            if self.col(col)[row] {
                out[col/64] |= 1<<(63-(col%64));
            }
        }
        BinaryVector { n: self.ncols, data: out }
    }

    /// Product with a BinaryVector over GF2.
    pub fn dot(&self, x: &BinaryVector) -> BinaryVector {
        assert!(x.n == self.ncols);
        let mut out = vec![0u64; self.words_per_col];
        for col in 0..self.ncols {
            if x[col] {
                for idx in 0..self.words_per_col {
                    out[idx] ^= self.data[col*self.words_per_col + idx];
                }
            }
        }
        BinaryVector { n: self.nrows, data: out }
    }

    /// Using self as a recurrence matrix, iterate n times starting from x,
    /// return a new BinaryVector of the bits in the first position at each step.
    pub fn recur(&self, x: &BinaryVector, n: usize) -> BinaryVector {
        let mut bits = Vec::with_capacity(n);
        let mut x = x.clone();
        for _ in 0..n {
            x = self.dot(&x);
            bits.push(x[0] as u8);
        }
        BinaryVector::from_bits(&bits)
    }

    /// Create a new random binary matrix with `nrows` rows and `ncols` columns,
    /// where the rows have weights chosen uniformly at random from `rowweights`.
    pub fn random(nrows: usize, ncols: usize, rowweights: &[usize]) -> BinaryMatrix {
        let words_per_col = numwords(nrows);
        let mut data = vec![0u64; words_per_col * ncols];
        let mut rng = rand::thread_rng();
        let weightrange = Range::new(0, rowweights.len());
        for rowidx in 0..nrows {
            let weight = rowweights[weightrange.ind_sample(&mut rng)];
            let cols = rand::sample(&mut rng, 0..ncols, weight);
            for colidx in &cols {
                data[colidx*words_per_col + rowidx/64] |= 1<<(63-(rowidx%64));
            }
        }
        BinaryMatrix { nrows: nrows, ncols: ncols, words_per_col: words_per_col, data: data }
    }
}

#[cfg(test)]
mod tests {
    use ::{BinaryVector, BinaryMatrix};

    #[test]
    fn test_from_words() {
        // Small matrix
        let words = [
            0x4D00000000000000, 0x6600000000000000, 0x2800000000000000, 0xC800000000000000,
            0x3E00000000000000, 0x9600000000000000, 0x2600000000000000, 0xB400000000000000,
            0xD700000000000000, 0x0A00000000000000, 0xD600000000000000, 0xA300000000000000];
        let x = BinaryMatrix::from_words(8, 12, &words);
        assert_eq!(x.col(0).to_bits(), vec![0, 1, 0, 0, 1, 1, 0, 1]);
        assert_eq!(x.col(11).to_bits(), vec![1, 0, 1, 0, 0, 0, 1, 1]);
        assert_eq!(x.row(0).to_bits(), vec![0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1]);
        assert_eq!(x.row(7).to_bits(), vec![1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1]);

        // Big matrix
        let words = [0xD1571BCA685A723F, 0x8FACE88700000000,
                     0x03CA88D60FA542A5, 0x982C521100000000];
        let x = BinaryMatrix::from_words(96, 2, &words);
        assert_eq!(x.row(0).to_bits(), vec![1, 0]);
        assert_eq!(x.col(0).to_bits(), vec![
            1, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1,
            0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0,
            1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0,
            0, 1, 0, 0, 0, 0, 1, 1, 1]);
    }

    #[test]
    fn test_dot() {
        let words = [
            0x77C560511586E4DA, 0xB11A0E7E1E9CF914, 0x1A157938C089896A, 0x17D052B7EEF8E6D0,
            0x5DFD087B667BA4DF, 0x95328B51CD0E784A, 0x59911C3B44ECA753, 0x1730A89BCE0AB547,
            0xE29DDCB392C0E5B8, 0x80370BE533EEDCD8, 0x95F689E62570FE53, 0x4A1CFF8243D047CB,
            0x1E861C5EBF131D83, 0x813EC3A71242DA8F, 0xD7D26080432B589C, 0x7AFA0A8C881BB4F8,
            0x71C554B7F6E533E5, 0x3BFBE4E054B8E22F, 0x22C0B1C0E94BE294, 0x28C363CBD00494A3,
            0x573843D2DF76065E, 0x89910B59119E0632, 0x1F73D8036DE4EE5E, 0x22F710A3C3DB93E9,
            0xDF1653515BC13BF4, 0x63F7DD10128C77D3, 0xD41CCE1357E42511, 0x9E4EB4BC58DC4FEE,
            0x54A95557FFDE73B2, 0xBA2681F23B0CEDBD, 0xD02049299E685EB2, 0x9B2C183751C2B869,
            0x73CC438449CC6271, 0xFA43C8326C5C43E7, 0xB6AE643BE51D627A, 0x6759DDEC081A11E4,
            0x69FFA1DA9AFB9A16, 0x5C4AA766A50FF05E, 0x51669CC64A5E8803, 0xB2D66A2CFECA1000,
            0x26AD814E2AFA53B8, 0x0CDDA1532B0A52DA, 0xD8197312D918C4BF, 0x24B62C18F1C19346,
            0xE44320950703CFAE, 0xB034B92097062BAB, 0x196C0A40C6FC7CEE, 0x629BB5997E84BD48,
            0x75137E75630C2801, 0xBCCFC86141718941, 0xF6744675B715DE94, 0x0C519E42973468CA,
            0x5D892F760BE9501A, 0x5DB84E56D9DB94CB, 0x4D6F4B49588618C8, 0x14745934B5F54369,
            0x00BFF2C0CCA7DA5E, 0x698EC12ECC5F55A3, 0xE7607AFD0411A1EF, 0xC14B279EB4581717,
            0x2BEB989C25DE87F9, 0x65789946989E55D2, 0xA78CCAAD75F2AC67, 0x8F0FF89D1069A684,
            0x767EC8FC4A0DD689, 0x8011EFE294143EDA, 0x5579A9382B1D2F76, 0x171A317F6B45520B,
            0xD173916223164143, 0xBC3696451031D3A7, 0xA729E856902C22B7, 0xC85D913AAD78816D,
            0x75DE3C3712A5FC1E, 0x2C7334B3A58835D6, 0x5BBEB8A62019E907, 0xD93376BA76A65A07,
            0xD3ABFE3035C92107, 0x606E4AA6D487EC9A, 0xD8D3C0FDA50A2846, 0xDD12369F645ED991,
            0xF941D4447A2790F6, 0x07E6D238258D54B1, 0x60D649AE2F11152A, 0xF69989EF3C27C602,
            0xC7E838E302AD16C3, 0xF674DF92A8B704BB, 0x251BA8369ED7177E, 0xB8D3796A15844B22,
            0x75834CAF996681D9, 0x994211A62E69066D, 0xDE22B0148825CEEF, 0x5E18659537EC67EC,
            0x62EF086B0EBF786C, 0xDE5BF1513E53B856, 0x5556C74AC8BFD027, 0x1DF49C94CA385BA7,
            0xF9C1DFC77923294E, 0x8891C3FB31495C6F, 0x9784EAF4B7C670B3, 0x95DBACEF3679D924,
            0x9CF92F4F3A98606A, 0x52BC806C1806AC3C, 0xAE287240FB221ECC, 0xCCB5B93ED7BA3275,
            0xE5373152391CE2CF, 0x1974FB540F1AA6A4, 0x060F78470211F3B3, 0xD150DDD61DFF23A6,
            0x3CBCA58CB9685E3F, 0x6E98872422D2C506, 0x0B14E36DAF9CD11D, 0xC62E02E3482C1EBA,
            0xB3855792B2922279, 0x96155FD5DCB4F8D5, 0xE22C4340366D1826, 0x3A715D1DD0FAB8B8,
            0x6026404DD0852CD4, 0xCD5651D4A18F956C, 0xFCC6537EC81DDEE4, 0xC8C43B4084E7A22C,
            0x43F75AD11CEFA37B, 0x84FCDB8697552878, 0xD7ED4A855DAC4016, 0x81AB173B3634A266,
            0x3353019B01009DD4, 0xD3DEF8BC93D6DEBD, 0x43E1C4E8BCA565CB, 0x3B978613171F4F20];
        let a = BinaryMatrix::from_words(64, 128, &words);
        let b = BinaryVector::from_bits(&[
            1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0,
            0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 0,
            0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0,
            0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 1,
            0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0]);
        let ab = a.dot(&b);
        assert_eq!(ab.to_bits(), vec![
            1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0,
            1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0,
            0, 1, 0, 0, 1, 0]);
    }

    #[test]
    fn test_recur() {
        let words = [
            0x7400000000000000, 0x5800000000000000, 0xC500000000000000, 0xD000000000000000,
            0xD500000000000000, 0xE600000000000000, 0xF100000000000000, 0x4700000000000000];
        let a = BinaryMatrix::from_words(8, 8, &words);
        let b = BinaryVector::from_bits(&[1, 0, 1, 0, 1, 0, 1, 0]);
        let x = a.recur(&b, 24);
        assert_eq!(x.to_bits(), vec![
            1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0]);
    }

    #[test]
    fn test_random() {
        let a = BinaryMatrix::random(8, 8, &[5]);
        for rowidx in 0..8 {
            let row = a.row(rowidx);
            let rowweight = row.to_bits().iter().fold(0, |acc, &x| acc + x);
            assert_eq!(rowweight, 5);
        }

        let a = BinaryMatrix::random(8, 8, &[2, 4]);
        for rowidx in 0..8 {
            let row = a.row(rowidx);
            let rowweight = row.to_bits().iter().fold(0, |acc, &x| acc + x);
            assert!(rowweight==2 || rowweight==4);
        }
    }
}
