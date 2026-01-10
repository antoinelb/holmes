use ndarray::Array1;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

/// Generate precipitation with specified probability of wet days and exponential distribution
pub fn generate_precipitation(
    n: usize,
    mean: f64,
    wet_day_prob: f64,
    seed: u64,
) -> Array1<f64> {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let precip: Vec<f64> = (0..n)
        .map(|_| {
            if rng.random::<f64>() < wet_day_prob {
                // Exponential distribution for wet day precipitation
                -mean * rng.random::<f64>().ln()
            } else {
                0.0
            }
        })
        .collect();
    Array1::from_vec(precip)
}

/// Generate temperature with seasonal cycle + noise
pub fn generate_temperature(
    n: usize,
    mean: f64,
    amplitude: f64,
    noise_std: f64,
    seed: u64,
) -> Array1<f64> {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let temps: Vec<f64> = (0..n)
        .map(|i| {
            let seasonal = amplitude
                * (2.0 * std::f64::consts::PI * i as f64 / 365.0).cos();
            let noise = noise_std * (rng.random::<f64>() - 0.5) * 2.0;
            mean - seasonal + noise
        })
        .collect();
    Array1::from_vec(temps)
}

/// Generate day of year sequence (1-365, wrapping)
pub fn generate_doy(start_doy: usize, n: usize) -> Array1<usize> {
    let doy: Vec<usize> =
        (0..n).map(|i| ((start_doy + i - 1) % 365) + 1).collect();
    Array1::from_vec(doy)
}

/// Generate PET using simple formula for testing (not Oudin, just synthetic)
pub fn generate_pet(
    n: usize,
    mean: f64,
    amplitude: f64,
    seed: u64,
) -> Array1<f64> {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let pet: Vec<f64> = (0..n)
        .map(|i| {
            let seasonal = amplitude
                * (2.0 * std::f64::consts::PI * i as f64 / 365.0).cos();
            let noise = 0.1 * mean * (rng.random::<f64>() - 0.5);
            (mean - seasonal + noise).max(0.0)
        })
        .collect();
    Array1::from_vec(pet)
}

/// Generate elevation layers for CemaNeige testing
pub fn generate_elevation_layers(
    n_layers: usize,
    min_elev: f64,
    max_elev: f64,
) -> Array1<f64> {
    let step = (max_elev - min_elev) / (n_layers as f64 - 1.0).max(1.0);
    let layers: Vec<f64> =
        (0..n_layers).map(|i| min_elev + step * i as f64).collect();
    Array1::from_vec(layers)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_precipitation() {
        let precip = generate_precipitation(365, 5.0, 0.3, 42);
        assert_eq!(precip.len(), 365);
        assert!(precip.iter().all(|&x| x >= 0.0));
    }

    #[test]
    fn test_generate_temperature() {
        let temp = generate_temperature(365, 10.0, 15.0, 2.0, 42);
        assert_eq!(temp.len(), 365);
    }

    #[test]
    fn test_generate_doy() {
        let doy = generate_doy(1, 365);
        assert_eq!(doy.len(), 365);
        assert_eq!(doy[0], 1);
        assert_eq!(doy[364], 365);

        // Test wrapping
        let doy_wrap = generate_doy(360, 10);
        assert_eq!(doy_wrap[0], 360);
        assert_eq!(doy_wrap[5], 365);
        assert_eq!(doy_wrap[6], 1);
    }

    #[test]
    fn test_generate_elevation_layers() {
        let layers = generate_elevation_layers(5, 500.0, 2000.0);
        assert_eq!(layers.len(), 5);
        assert!((layers[0] - 500.0).abs() < 0.001);
        assert!((layers[4] - 2000.0).abs() < 0.001);
    }
}
