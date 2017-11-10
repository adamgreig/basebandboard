extern crate rnghunt;
extern crate threadpool;
extern crate num_cpus;

use std::sync::mpsc::channel;
use threadpool::ThreadPool;
use std::time::Duration;

fn main() {
    let n = 31;
    let (tx, rx) = channel();
    let pool = ThreadPool::new(num_cpus::get());
    loop {
        if pool.active_count() < pool.max_count() {
            let tx = tx.clone();
            pool.execute(move|| {
                loop {
                    // Make a random binary matrix of shape (n, n) where rows have 3 or 4 1s.
                    let a = rnghunt::BinaryMatrix::random(n, n, &[3, 4]);

                    // Obtain a length 2n sequence output from this recurrence matrix
                    let b = rnghunt::BinaryVector::from_bits(&vec![1u8; n]);
                    let x = a.recur(&b, 2*n);

                    // Find the corresponding characteristic polynomial
                    let p = rnghunt::berlekamp_massey(&x);

                    // Check the polynomial has degree equal to n
                    if p.degree() != n as isize {
                        break;
                    }

                    // Check if the polynomial is primitive
                    if p.is_primitive() {
                        println!("Found primitive polynomial for n={}:", n);
                        println!("a: [");
                        for word in &a.data {
                            print!(" 0x{:x}, ", word);
                        }
                        println!("]");
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
