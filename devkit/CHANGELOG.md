# Changelog

## [Unreleased]

### Fixed

- Fix wrong orientation for SWD header (#117)

### Added

- Add pull-up resistor for display enable signal. Can be disabled via GPIO. (#123)
- Add new KiBot template (#116)
- Add orientation marker for IMU (#124)
- Add power LEDs (#128)
- Add reset button (#131)
- Add testpoints for microphone I2S (#145)

### Changed

- Shrink down the PCB to save costs (#115)
- Replace pin headers with THT to make them more robust (#121)
- Rename "Power" jumpers to "Current" (#129)
- Replace level shifter for RTC with PCA9306GF (#133)
- Switch back to old LED driver (#134)
- Power microphone from PMIC (#145)

### Removed

- Remove APDS-9306 interrupt (#122)
