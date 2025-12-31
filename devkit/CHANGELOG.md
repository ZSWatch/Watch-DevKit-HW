# Changelog

## [Unreleased]

### Changed

-   Change part number for SWD connector to BD125-10-A-0305-0580-L-B (#164)

### Fixed

-   Fix wrong resistor for VREF2 pin for the level shifter (#172)
-	Fix wrong silkscreen for Display current (#179)

## [1.2.1] - 2025-09-26

### Added

-   Add missing pull-ups for I2C lines (#158)
-	Add additional GPIO to I2S header (#180)

### Fixed

-   Fix wrong ship mode button (#155)

### Changed

-   Change part number for SWD connector to 62201021121 (#157)
-   Set pull-up for Flash CS to NA (#158)
-   Center the mounting holes for the display (#159)

## [1.2.0] - 2025-09-07

### Fixed

-   Fix wrong orientation for SWD header (#117)

### Added

-   Add pull-up resistor for display enable signal. Can be disabled via GPIO. (#123)
-   Add new KiBot template (#116)
-   Add orientation marker for IMU (#124)
-   Add power LEDs (#128)
-   Add reset button (#131)
-   Add testpoints for microphone I2S (#145)

### Changed

-   Shrink down the PCB to save costs (#115)
-   Replace pin headers with THT to make them more robust (#121)
-   Rename "Power" jumpers to "Current" (#129)
-   Replace level shifter for RTC with PCA9306GF (#133)
-   Switch back to old LED driver (#134)
-   Power microphone from PMIC (#145)

### Removed

-   Remove APDS-9306 interrupt (#122)

[Unreleased]: https://github.com/ZSWatch/Watch-DevKit-HW/compare/1.2.1...HEAD

[1.2.1]: https://github.com/ZSWatch/Watch-DevKit-HW/compare/1.2.0...1.2.1

[1.2.0]: https://github.com/ZSWatch/Watch-DevKit-HW/compare/fc3844fb6a647a23e214f3085a47ce2212e0d98a...1.2.0
