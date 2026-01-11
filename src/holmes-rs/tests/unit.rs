mod common;

// Unit test submodules (using #[path] to specify correct locations)
#[path = "unit/calibration/mod.rs"]
mod calibration;

#[path = "unit/hydro/mod.rs"]
mod hydro;

#[path = "unit/metrics_tests.rs"]
mod metrics_tests;

#[path = "unit/pet/mod.rs"]
mod pet;

#[path = "unit/snow/mod.rs"]
mod snow;

// Re-export helpers for use in test modules
pub use common::fixtures;
pub use common::helpers;
