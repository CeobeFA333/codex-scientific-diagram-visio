# Cross-paper regression corpus

This corpus extends the local examples with real open papers from different disciplines. It is a routing and regression set, not a permission to copy artwork blindly. Before reconstruction, record the article URL, figure number, source-data or code URL, license, retrieval date, and SHA-256 of every downloaded asset. Always run a PDF object census first; a publisher web page showing PNG does not prove the PDF figure is raster-only.

Recovery levels:

- `R0`: preserve native PDF text and vector objects.
- `R1`: regenerate exactly from available source data and declared plotting parameters.
- `R2`: reconstruct or digitize approximately from pixels; report uncertainty.
- `R3`: preserve irrecoverable scientific-evidence pixels as atomic rasters.

## 1. Multi-omics workflow

- Paper: [Interpretation of network-based integration from multi-omics longitudinal data](https://academic.oup.com/nar/article/50/5/e27/6457960).
- Target: Figure 1, from longitudinal study design through normalization, multilayer networks, clustering, ORA and propagation analysis.
- Route: `R0`, with `R2` geometry fallback.
- Editable: text, time points, omics layer blocks, arrows, nodes, edges, legends and panel letters.
- Raster atoms: none by default; a bitmap biological icon must be isolated as its own atom.
- Gates: validate a semantic connection table. Pixel similarity alone cannot detect a wrongly connected workflow.

## 2. Protein-interaction network, heatmap and bar chart

- Paper: [The OncoPPi network of cancer-focused protein-protein interactions](https://www.nature.com/articles/ncomms14356).
- Target: Figure 2, including the 83-node/397-edge map, topology, localization heatmap and interaction-domain bars. Supplementary Data 3 is Cytoscape-compatible.
- Route: `R1`.
- Editable: nodes, edges, hub encoding, mutually exclusive edges, labels, heatmap cells, axes, bars and legends.
- Raster atoms: none.
- Gates: prefer saved Cytoscape coordinates. If only an edge list exists, record the layout algorithm and seed, then validate node and edge identity rather than claiming pixel-exact placement.

## 3. Violin, heatmap and volcano composite

- Paper: [High-throughput proteome integral solubility alteration assay for low cell input using One-Tip](https://pmc.ncbi.nlm.nih.gov/articles/PMC12474936/).
- Target: Figure 2. Source material includes PRIDE `PXD056894` / `PXD061105` and Supplementary Data 1.
- Route: `R1`.
- Editable: every point, violin path, quartile and median, heatmap cell, volcano threshold and label, axes and legends.
- Raster atoms: none.
- Gates: record KDE bandwidth, normalization, log transform, adjusted-p method and significance thresholds; compare source-data hashes, point counts and summary statistics.

## 4. Single-cell multi-omics heatmaps and genome tracks

- Paper: [Single-cell multiomics decodes regulatory programs for mouse secondary palate development](https://pmc.ncbi.nlm.nih.gov/articles/PMC10821874/).
- Target: Figure 2, including linked peak-gene heatmaps and Twist1 genome-browser tracks with arcs. Data are in GEO `GSE218576`, `GSE252592`, `GSE250247`, and `GSE155928`; code is in the linked repository from the paper.
- Route: `R1`.
- Editable: axes, cluster and color tracks, labels, peaks, arcs, gene models, boxes and legends.
- Raster atoms: a very large matrix body may be rendered as one lossless, data-derived raster for Illustrator performance, while text, axes, tracks and legends remain vector. This remains R1, not R3.
- Gates: pin row and column order, clustering seed, normalization range, genome build, coordinates and arc thresholds.

## 5. SEM, EDS maps and line scans

- Paper: [In situ elemental analyses of living biological specimens using NanoSuit and EDS methods in FE-SEM](https://pmc.ncbi.nlm.nih.gov/articles/PMC7471950/).
- Target: Figure 7.
- Route: `R3 + R2`.
- Editable: panel letters, element names, arrows, scan lines, scale bars, and line-scan axes, ticks and labels. Digitized line scans are R2 if numeric source data are absent.
- Raster atoms: every SEM field, elemental map and merged map is an independent evidence atom.
- Gates: do not beautify intensity pixels. Preserve map-to-SEM registration, scale-bar pixel length, and line-scan peak positions; no generative repair inside evidence.

## 6. MRI segmentation comparison

- Paper: [nnU-Net-based Segmentation of Tumor Subcompartments in Pediatric Medulloblastoma Using Multiparametric MRI](https://pmc.ncbi.nlm.nih.gov/articles/PMC11427926/).
- Target: Figure 2, with MRI, reference labels and two model predictions for good and poor cases.
- Route: `R3 + R2`.
- Editable: panel letters, row and column headings, case labels, metrics, legends and borders.
- Raster atoms: each MRI slice and each inseparable reference or prediction overlay is an independent evidence atom.
- Gates: preserve slice identity, window and level, mask alpha and colors. Never substitute a similar case or inpaint diagnostic pixels.

## 7. Raman spectra

- Paper: [In situ Raman spectroscopy reveals the structure and dissociation of interfacial water](https://www.nature.com/articles/s41586-021-04068-z).
- Target: Figure 2. The publisher provides Figure 2 source-data spreadsheets.
- Route: `R1`.
- Editable: all spectra, axes, ticks, potential labels, peak annotations, baselines, fits and legends.
- Raster atoms: none unless a photo or molecular-render inset is present.
- Gates: reproduce stacking offsets, baseline correction, normalization, smoothing, fitting and scan order from source data; do not replace noisy spectra with hand-smoothed paths.

## 8. Electrochemical Nyquist plots

- Paper: [Experimental data for electrochemical impedance characterization of Li-ion batteries under varying SOC, current amplitude and rest time](https://pmc.ncbi.nlm.nih.gov/articles/PMC12926631/).
- Target: Figures 5 and 6; the paper documents MATLAB scripts that generate the panels.
- Route: `R1`.
- Editable: every complex-impedance point and line, marker, axes, ticks, legends and panel letters.
- Raster atoms: none.
- Gates: verify the negative-imaginary-axis convention, units, frequency order, and legend mapping for SOC, current amplitude and rest time.

## 9. Remote-sensing land-cover maps

- Paper: [Urban heat island dynamics in Rawalpindi: a 30-year remote sensing analysis and future projections](https://pmc.ncbi.nlm.nih.gov/articles/PMC12460804/).
- Target: Figure 7, the 1990-2020 land-use and land-cover series.
- Route: `R3 + R2` unless the exact classified rasters, training state and post-processing are available.
- Editable: years, titles, legends, north arrows, scale bars, administrative boundaries, graticules and panel letters.
- Raster atoms: each year's classified raster is independent.
- Gates: preserve projection, extent, category values, class-color mapping and pixel alignment; do not let annotation cleanup alter boundary or category pixels.

## 10. Three-dimensional CFD fields and quantitative comparison

- Paper: [ML-ROM wall shear stress prediction in patient-specific vascular pathologies under a limited clinical training data regime](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0325644).
- Target: Figure 6 three-dimensional TAWSS surfaces and Figure 8 Bland-Altman comparisons. The article links its Zenodo data.
- Route: `R1` when field data, camera and plotting parameters are recoverable; otherwise downgrade Figure 6 to `R3 + R2`.
- Editable: Figure 8 points, mean and limit lines, axes and labels; Figure 6 text, color bars, ticks, callouts and panel structure.
- Raster atoms: each data-derived three-dimensional shaded surface should normally be one high-resolution render atom rather than hundreds of thousands of mesh paths in Illustrator.
- Gates: record camera matrix, lighting, triangulation, colormap, numeric range and sampling seed.

## Minimum regression matrix

- R0 object extraction: samples 1 and 2, subject to actual PDF census.
- Pure R1 regeneration: samples 2, 3, 7 and 8.
- Large R1 matrix with performance-aware rasterization: sample 4.
- R3 scientific-evidence hybrid: samples 5, 6 and 9.
- Data-derived 3D render plus vector annotation: sample 10.

For every sample, structural, semantic, visual, Illustrator-Type, PDF and scientific-integrity gates must all pass. A visual overlay cannot replace source-data or object-identity validation.
