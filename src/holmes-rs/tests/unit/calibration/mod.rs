//! Auto-discovers every `*_tests.rs` sibling as a child module.
//! `automod::dir!` expands at compile time to `mod <stem>;` for each `.rs`
//! file in the directory (excluding `mod.rs`), so dropping a new
//! `*_tests.rs` file into this directory is sufficient — no edit here.
//! The path literal is resolved relative to `CARGO_MANIFEST_DIR`
//! (the `src/holmes-rs/` crate root), not to this file.
automod::dir!("tests/unit/calibration");
