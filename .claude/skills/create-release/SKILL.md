---
name: create-release
description: Create a hardware release x.y.z of this KiCad project. Runs ERC/DRC, checks and fixes the page numbers of the schematic, checks the impedance table against the net classes of the layout, sets the changelog variables of the release in the KiBot configuration and the schematic, switches the KiBot variant to CHECKED, pushes "Prepare Release x.y.z" to the development branch, waits for the KiBot pipeline, merges into the main branch, creates and pushes the tag x.y.z, waits for the release pipeline, pulls the released state of the main branch and finishes with the main branch checked out. Use when the user asks to prepare, create or publish a release.
---

# create-release

This skill is maintained in one place for all AI coding agents:
[.github/skills/create-release/SKILL.md](../../../.github/skills/create-release/SKILL.md)

Read that file completely (path from the repository root: `.github/skills/create-release/SKILL.md`) and follow it
step by step. Do not start before you have read it. This file only points to it and contains no steps.

Keep the `description` above identical to the one in that file.
