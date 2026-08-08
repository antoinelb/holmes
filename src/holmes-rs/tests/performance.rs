mod common;

// Performance test submodules (using #[path] to specify correct locations)
#[path = "performance/calibration_convergence.rs"]
mod calibration_convergence;

// Re-export helpers for use in test modules
pub use common::fixtures;
pub use common::helpers;
