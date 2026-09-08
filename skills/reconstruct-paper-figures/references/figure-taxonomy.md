# Cross-disciplinary paper figure taxonomy

Use this catalog to classify each panel, not only the whole composite figure. Data recovery status uses:

- `R0`: native PDF objects can be extracted.
- `R1`: public source data exists and the plot can be regenerated.
- `R2`: pixel-to-data digitization is possible but approximate.
- `R3`: scientific evidence pixels cannot be recovered from the publication image.

| Priority | Figure class | Raster evidence to preserve | Editable reconstruction | Recovery | Representative source |
|---|---|---|---|---|---|
| P0 | Line/scatter/error-bar/fitted curves | None unless scanning noise is evidence | Axes, ticks, points, error bars, curves, legends, text | R0-R2 | [Electrode plots and Nyquist examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC8425916/) |
| P0 | Bar/box/violin/ROC plots | Usually none | Full geometric redraw with significance marks and text | R1-R2 | [Mixed biomedical statistical plots](https://pmc.ncbi.nlm.nih.gov/articles/PMC8484502/) |
| P0 | Kaplan-Meier/forest/clinical flow | Usually none | Curves, censor marks, CI symbols, risk table, flow nodes | R1-R2 | [Clinical trial graphics](https://pmc.ncbi.nlm.nih.gov/articles/PMC2394578/) |
| P0 | Heatmap/confusion/correlation matrix | Continuous or unreadable heatmap only | Cells, dendrogram, color bar, values, labels | R1-R2 | [Two-dimensional genomic heatmap](https://pmc.ncbi.nlm.nih.gov/articles/PMC6144591/) |
| P0 | Phylogenetic tree/network/Circos | Embedded photos or textures | Topology, nodes, edges, rings, labels, scale | R1-R2 | [Tree and Circos examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC3691752/) |
| P0 | Flow/mechanism/neural architecture | Only photos and feature maps | Nodes, tensors, connectors, formulas, text | R0-R2 | [U-Net architecture examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC7829473/) |
| P0 | Circuit/control/wiring diagram | Instrument screenshots and photos | Symbols, wires, junctions, IDs, parameters | R0-R2 | [Telemetry circuit figure](https://pmc.ncbi.nlm.nih.gov/articles/PMC4279561/) |
| P0 | Microfluidic/process principle | Microscopy and device photos | Channels, layers, flow arrows, dimensions, labels | R0-R2 | [Two-layer microfluidic device](https://pmc.ncbi.nlm.nih.gov/articles/PMC3918417/) |
| P0 | Chemical structure/reaction scheme | Spectra and photos only | Bonds, stereochemistry, arrows, conditions, yields | R0-R2 | [Reaction scheme example](https://pmc.ncbi.nlm.nih.gov/articles/PMC10952796/) |
| P1 | Fluorescence/confocal microscopy | All channel intensity pixels | Scale bars, ROIs, arrows, channel and panel labels | R3 | [Fluorescence presentation guidance](https://pmc.ncbi.nlm.nih.gov/articles/PMC6080651/) |
| P1 | Histology/whole-slide/segmentation | Tissue pixels | ROI boundaries, polygons, markers, scale, text | R3 | [Digital pathology ROI examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC6437786/) |
| P1 | Western blot/electrophoresis | Bands and gel background | Lane labels, molecular weights, brackets, panel labels | R3 | [Single-cell Western blot composite](https://pmc.ncbi.nlm.nih.gov/articles/PMC5764185/) |
| P1 | Flow cytometry | Scatter/density cloud | Gates, quadrant lines, percentages, axes, sample labels | R1 or R3 | [Flow cytometry analysis review](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867282/) |
| P1 | CT/MRI/PET/ultrasound | Medical image pixels | Segmentation boundaries, orientation, arrows, scale, text | R1 or R3 | [Medical segmentation overlays](https://pmc.ncbi.nlm.nih.gov/articles/PMC6871678/) |
| P1 | SEM/TEM/AFM/EDS | Instrument and element-intensity pixels | Scale bars, region boxes, arrows, element labels, color bars | R3 | [SEM and EDXS mapping](https://pmc.ncbi.nlm.nih.gov/articles/PMC6054630/) |
| P1 | XRD/Raman/FTIR/XPS/MS/chromatography | Noise-bearing curve only when needed | Axes, peak marks, reference lines; digitized curves | R1-R2 | [Open Raman-XRD data resource](https://pmc.ncbi.nlm.nih.gov/articles/PMC6557180/) |
| P1 | DSC/TGA/DTA/CV/EIS | Usually none | Curves, peaks, axes, circuit symbols and text | R1-R2 | [Thermal plots](https://pmc.ncbi.nlm.nih.gov/articles/PMC2976901/), [electrochemical plots](https://pmc.ncbi.nlm.nih.gov/articles/PMC10763723/) |
| P1 | FEA stress/strain field | Continuous field and deformed mesh | Color bar, boundary arrows, dimensions, labels | R1 or R3 | [Stress field examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC6056196/) |
| P1 | CFD velocity/pressure/streamlines | Continuous numerical field | Color bar, sections, boundaries, arrows, labels | R1 or R3 | [CFD contour examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC2699293/) |
| P1 | 3D response-surface/contour plot | Continuous fitted field when source data/model is absent | Three-dimensional axes, projected contours, grids, ticks, black operating points, labels | R1-R3 | Current `surface_plots` complex reference; apply the same continuous-field safeguards as FEA/CFD |
| P1 | GIS/remote sensing/land cover | Satellite, DEM, continuous raster | Boundaries, points, graticule, north arrow, scale, legend | R1-R3 | [Land-cover classification maps](https://pmc.ncbi.nlm.nih.gov/articles/PMC4916107/) |
| P1 | Geology/seismic/map-section | Terrain and complex focal mechanisms | Faults, epicenters, section lines, axes, symbols, legend | R1-R3 | [Etna earthquake map and section](https://pmc.ncbi.nlm.nih.gov/articles/PMC10415380/) |
| P1 | Computer-vision qualitative results | Photos, continuous depth/probability maps | Boxes, classes, confidence, keypoints, masks, panel text | R2-R3 | [Feature Pyramid Networks](https://arxiv.org/abs/1612.03144) |
| P2 | Protein/molecular 3D render | Ribbon/surface render without PDB | Residue labels, ligands, dashed bonds, arrows, text | R1 or R3 | [Kinase structure example](https://pmc.ncbi.nlm.nih.gov/articles/PMC3320885/) |
| P2 | CAD/exploded/device assembly | Complex surface render and photos | Visible contours, dimensions, leaders, BOM IDs, text | R1-R3 | [Device CAD and exploded views](https://pmc.ncbi.nlm.nih.gov/articles/PMC10035053/) |
| P2 | Multi-panel photo + schematic + plot | Classify each atomic panel separately | Panel frames, labels, leaders, schematic and plot layers | Mixed | [Composite experimental figure](https://pmc.ncbi.nlm.nih.gov/articles/PMC7582002/) |

## Implementation order

1. P0: geometry-first types with deterministic structural tests.
2. P1: a shared atomic-raster hybrid engine with text cleanup and vector overlays.
3. P2: domain adapters such as ChemDraw/RDKit, PyMOL/ChimeraX, CAD, and Visio.

Never infer R1/R2 data as original measurements. Store the recovery level in the reconstruction manifest and surface it in QA.
