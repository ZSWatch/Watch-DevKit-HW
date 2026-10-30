# ZSWatch-Watch-DevKit

[![License](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://opensource.org/license/gpl-3-0/)

## 📑 Table of Contents

- [ZSWatch-Watch-DevKit](#zswatch-watch-devkit)
  - [📑 Table of Contents](#-table-of-contents)
  - [📖 About](#-about)
  - [📂 Directory Breakdown](#-directory-breakdown)
  - [Purchasing](#purchasing)
  - [Ressources](#ressources)
  - [👨‍💻 Maintainer](#-maintainer)

## 📖 About

The **ZSWatch-Watch-DevKit** project provides the hardware design and production files for a smartwatch development board tailored to the ZSWatch ecosystem.
It is built with **KiCad** and integrates a full **CI/CD pipeline** using **KiBot**, ensuring reproducible outputs for documentation, manufacturing, and releases.

Key features:

- 🛠️ Open-source hardware design
- 📦 Automated generation of Gerber, BoM, and documentation via KiBot
- 🔄 Workflow stages (DRAFT → PRELIMINARY → CHECKED → RELEASED) for structured releases
- 📝 Clear documentation and changelog to track progress
- 🌍 Designed with collaboration and transparency in mind

Please check the [wiki](https://github.com/ZSWatch/ZSWatch/wiki) for more information about the project.

You can also view this project on [CADLAB.io](https://cadlab.io/project/29658).

## 📂 Directory Breakdown

- **`.github`**: GitHub related files
- **`.gitignore`**: Ignored files list
- **`cad`**: Mechanical design files
- **`devkit`**: KiCad project for the devkit
- **`docs`**: Drawings and documentation
- **`scripts`**: Additional scripts for CI/CD
- **`CHANGELOG.md`**: Version history
- **`LICENSE`**: Project license (GPL-3.0)
- **`README.md`**: Project overview

The manufacturing outputs (Gerbers, BoM, documentation, etc.) are not part of the repository. They are
attached to each [release](https://github.com/ZSWatch/Watch-DevKit-HW/releases) and published on GitHub Pages.

## Purchasing

TBD

## Ressources

- [KiBot Template](https://github.com/nguyen-v/KDT_Hierarchical_KiBot)

## 👨‍💻 Maintainer

- [Daniel Kampert](mailto:danielkameprt@kampis-elektroecke.de)
