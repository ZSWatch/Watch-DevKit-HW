<p align="center" width="100%">
  <img alt="Logo" width="33%" src="logos/ZSWatch_logo_with_text.png">
</p>

<h1 align="center">ZSWatch-Watch-DevKit</h1>

<p align="center" width="100%">
  <a href="${GIT_URL}/actions/workflows/hw-pcb.yaml">
    <img alt="CI Badge" src="${GIT_URL}/actions/workflows/hw-pcb.yaml/badge.svg">
  </a>
</p>

***

<p align="center">
  <img alt="3D Top Angled" src="Images/ZSWatch-Watch-DevKit-angled_top.png" width="45%">
&nbsp; &nbsp; &nbsp; &nbsp;
  <img alt="3D Bottom Angled" src="Images/ZSWatch-Watch-DevKit-angled_bottom.png" width="45%">
</p>

***

## SPECIFICATIONS

| Parameter | Value |
| --- | --- |
| Dimensions | 32.0 × 24.0 mm |

***

## PROJECT DIRECTORY STRUCTURE

    .
    ├─ kibot_resources       # External resources for KiBot
    │  ├─ colors             # Color theme for KiCad
    │  ├─ fonts              # Fonts used in the project
    │  ├─ scripts            # External scripts used with KiBot
    │  └─ templates          # Templates for KiBot generated reports
    ├─ kibot_yaml            # KiBot YAML config files
    ├─ logos                 # Logos
    ├─ meta                  # Project metadata
    ├─ templates             # Title block templates
    ├─ *.kicad_sch           # KiCad schematic files
    ├─ *.kicad_pcb           # KiCad PCB layout
    ├─ *.kicad_pro           # KiCad project file
    ├─ *.xml                 # Netlist of the schematic (updated by the pipeline)
    ├─ CHANGELOG.md          # Changelog of the hardware
    ├─ LICENSE               # Project license
    ├─ README.md             # Project README
    └─ kibot_launch.sh       # KiBot automation script

## OUTPUT DIRECTORY STRUCTURE

    .
    ├─ 3D                   # 3D export of the PCB (STEP)
    ├─ HTML                 # HTML files for generated webpage
    ├─ Images               # Pictures and renders
    │  └─ Logos             # Logos
    ├─ KiRI                 # KiRI (PCB diff viewer) files
    ├─ Manufacturing        # Assembly and fabrication documents
    │  ├─ Assembly          # Assembly documents (BoM, BoM check, Mouser cart, pos, notes)
    │  └─ Fabrication       # Fabrication documents (Gerber / ODB++ ZIP, notes, impedance table)
    │     ├─ Drill Tables   # CSV drill tables
    │     └─ Gerbers        # Gerbers
    ├─ Netlist              # PCB netlist
    ├─ Reports              # Reports for ERC/DRC
    ├─ Schematic            # PDF of schematic
    ├─ Testing              # Test documents
    │  └─ Testpoints        # Testpoints tables
    ├─ Variants             # Outputs for assembly variants, if available
    ├─ index.html           # Start page of the generated webpage
    └─ README.md            # This README
