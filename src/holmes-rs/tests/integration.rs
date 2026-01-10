mod common;

// Integration test submodules (using #[path] to specify correct locations)
#[path = "integration/calibration_workflow.rs"]
mod calibration_workflow;

#[path = "integration/full_simulation.rs"]
mod full_simulation;

// Re-export helpers for use in test modules
pub use common::fixtures;
pub use common::helpers;
