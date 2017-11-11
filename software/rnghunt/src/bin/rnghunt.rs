extern crate rnghunt;
extern crate threadpool;
extern crate num_cpus;

use std::error::Error;
use std::sync::mpsc::channel;
use threadpool::ThreadPool;
use std::time::Duration;
use std::io::prelude::*;
use std::fs::File;
use std::path::Path;

fn main() {
    let n = 192;
    println!("Starting search for n={}", n);
    let (tx, rx) = channel();
    let n_threads = num_cpus::get();
    let pool = ThreadPool::new(n_threads);
    loop {
        if pool.active_count() < pool.max_count() {
            let tx = tx.clone();
            pool.execute(move|| {
                'outer: loop {
                    // Make a random binary matrix of shape (n, n) where rows have 3 or 4 1s.
                    let a = rnghunt::BinaryMatrix::random(n, n, &[3, 4]);

                    // Obtain a length 2n sequence output from this recurrence matrix
                    let b = rnghunt::BinaryVector::from_bits(&vec![1u8; n]);
                    let x = a.recur(&b, 2*n);

                    let mut xbits = x.to_bits();
                    xbits.reverse();
                    let x = rnghunt::BinaryVector::from_bits(&xbits);

                    // Find the corresponding characteristic polynomial
                    let p = rnghunt::berlekamp_massey(&x);

                    // Check the polynomial has degree equal to n
                    if p.degree() != n as isize {
                        continue;
                    }

                    // Check if the polynomial is primitive
                    if p.is_primitive() {
                        println!("Found suitable recurrence matrix for n={}, writing out", n);
                        let path = Path::new("out");
                        let mut file = match File::create(&path) {
                            Err(why) => panic!("Couldn't create {}: {}", path.display(), why.description()),
                            Ok(file) => file,
                        };
                        for row in 0..n {
                            file.write(format!("{}\n", a.row(row)).as_bytes()).unwrap();
                        }
                        tx.send(()).unwrap();
                        break;
                    }
                }
            });
        } else {
            match rx.recv_timeout(Duration::from_secs(1)) {
                Ok(()) => break,
                Err(_) => (),
            }
        }
    }
}
