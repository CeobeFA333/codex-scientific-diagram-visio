"""Capability catalog rendered by the paper-figure reconstruction skill."""

from __future__ import annotations


CATEGORIES = [
    {
        "id": "ai-computer-vision",
        "title": "AI · Machine Learning · Computer Vision",
        "title_zh": "AI · 机器学习 · 计算机视觉",
        "accent": "#315C9D",
        "cards": [
            ("Neural architectures", "Transformer · CNN · MLP", "pipeline"),
            ("Encoder–decoder", "U-Net · multiscale flows", "encoder"),
            ("Feature maps", "tensors · dimensions", "cuboids"),
            ("Residual paths", "skip · feedback · return", "residual"),
            ("Attention", "Q/K/V · projection", "attention"),
            ("Multimodal fusion", "sum · concat · weighted", "fusion"),
            ("Detection", "boxes · classes · keypoints", "detection"),
            ("Dense prediction", "masks · depth · probability", "segmentation"),
        ],
    },
    {
        "id": "statistics-data-science",
        "title": "Statistics · Data Science",
        "title_zh": "统计学 · 数据科学",
        "accent": "#2B9C98",
        "cards": [
            ("Curves and points", "line · scatter · fitted", "line_plot"),
            ("Uncertainty", "error bar · confidence interval", "error_plot"),
            ("Distributions", "bar · box · violin · ROC", "distribution"),
            ("Clinical statistics", "Kaplan–Meier · forest · risk", "survival"),
            ("Matrices", "heatmap · confusion · correlation", "heatmap"),
            ("Embeddings", "PCA · t-SNE · clustered scatter", "embedding"),
            ("Trees and graphs", "dendrogram · network · phylogeny", "tree"),
            ("Circular data", "Circos · rings · radial labels", "circos"),
        ],
    },
    {
        "id": "clinical-biomedical",
        "title": "Clinical · Biomedical",
        "title_zh": "临床 · 生物医学",
        "accent": "#B64C5A",
        "cards": [
            ("Clinical flow", "cohort · randomization · outcome", "flow_chart"),
            ("Forest plots", "effect · CI · reference", "forest"),
            ("Flow cytometry", "cloud · gate · quadrant", "cytometry"),
            ("Medical imaging", "CT · MRI · PET · ultrasound", "medical_scan"),
            ("Histology", "whole slide · tissue annotation", "histology"),
            ("Segmentation", "ROI · contour · orientation", "roi"),
            ("Risk tables", "time points · at-risk counts", "risk_table"),
            ("Study timelines", "treatment · visit · follow-up", "timeline"),
        ],
    },
    {
        "id": "cell-molecular-omics",
        "title": "Cell · Molecular · Omics",
        "title_zh": "细胞 · 分子 · 组学",
        "accent": "#6B8F44",
        "cards": [
            ("Microscopy", "fluorescence · confocal · scale", "microscopy"),
            ("Multiplex imaging", "channels · composite · cells", "multiplex"),
            ("Western blot", "bands · lanes · molecular weight", "blot"),
            ("Electrophoresis", "gel · ladder · sample lanes", "gel"),
            ("Genomic matrices", "heatmap · annotation tracks", "genomic_heatmap"),
            ("Phylogenetics", "tree · clade · branch scale", "phylogeny"),
            ("Protein renders", "ribbon · residue · domain", "protein"),
            ("Ligand interactions", "ligand · residue · dashed bond", "ligand"),
        ],
    },
    {
        "id": "chemistry-materials",
        "title": "Chemistry · Materials · Electrochemistry",
        "title_zh": "化学 · 材料 · 电化学",
        "accent": "#8A66A3",
        "cards": [
            ("Chemical structure", "bonds · rings · stereochemistry", "molecule"),
            ("Reaction scheme", "arrow · conditions · yield", "reaction"),
            ("Spectroscopy", "XRD · Raman · FTIR · XPS", "spectrum"),
            ("Separation analysis", "MS · chromatography · peaks", "chromatography"),
            ("Thermal analysis", "DSC · TGA · DTA", "thermal"),
            ("Electrochemistry", "CV · EIS · Nyquist", "nyquist"),
            ("Surface microscopy", "SEM · TEM · AFM", "material_micro"),
            ("Element mapping", "EDS · regions · color bar", "eds"),
        ],
    },
    {
        "id": "engineering-physics",
        "title": "Engineering · Physics",
        "title_zh": "机械 · 电气 · 工程物理",
        "accent": "#D28A2E",
        "cards": [
            ("Circuit diagram", "symbols · wires · parameters", "circuit"),
            ("Control system", "blocks · feedback · transfer", "control"),
            ("Wiring", "junctions · terminals · IDs", "wiring"),
            ("FEA fields", "stress · strain · boundary loads", "fea"),
            ("CFD fields", "velocity · pressure · streamlines", "cfd"),
            ("Response surface", "3D surface · contour · points", "surface"),
            ("CAD drawing", "contours · dimensions · leaders", "cad"),
            ("Exploded assembly", "parts · BOM · exploded leaders", "exploded"),
        ],
    },
    {
        "id": "experimental-systems",
        "title": "Experimental Systems · Microfluidics",
        "title_zh": "实验系统 · 微流控",
        "accent": "#287E8E",
        "cards": [
            ("Experimental setup", "source · sample · detector", "apparatus"),
            ("Microfluidics", "channels · junctions · flow", "microfluidic"),
            ("Layered device", "substrate · membrane · chamber", "layers"),
            ("Sensor chain", "sensor · amplifier · acquisition", "sensor"),
            ("Device photo panel", "atomic image · labels · scale", "device_panel"),
            ("Composite figure", "photo · schematic · plot", "composite"),
            ("Process principle", "stages · material flow", "process"),
            ("Measurement layout", "dimension · angle · calibration", "measurement"),
        ],
    },
    {
        "id": "earth-geospatial",
        "title": "Earth Science · Geospatial",
        "title_zh": "地球科学 · 地理空间",
        "accent": "#4D7B5D",
        "cards": [
            ("GIS map", "boundaries · points · legend", "map"),
            ("Remote sensing", "land cover · classification", "landcover"),
            ("Terrain", "DEM · contours · hillshade", "dem"),
            ("Geology", "units · faults · contacts", "geology"),
            ("Seismic map", "epicenters · stations · magnitude", "seismic"),
            ("Cross-section", "layers · section line · depth", "section"),
            ("Map framework", "graticule · north arrow · scale", "graticule"),
            ("Cartography", "symbols · color key · annotation", "map_legend"),
        ],
    },
]


WORKLOAD_PROFILES = {
    "S": {
        "token_range": "15–35k tok",
        "image_refs": "0–1 img",
        "description": "single-panel vector reconstruction with limited evidence reconciliation",
    },
    "M": {
        "token_range": "35–75k tok",
        "image_refs": "0–2 img",
        "description": "multi-layer panel with source inspection and one editor QA pass",
    },
    "L": {
        "token_range": "75–150k tok",
        "image_refs": "1–4 img",
        "description": "dense or image-bearing panel with scientific review and roundtrip QA",
    },
    "S/M": {
        "token_range": "15–75k tok",
        "image_refs": "0–2 img",
        "description": "small schematic at S; real data, statistics, or linked panels upgrade to M",
    },
    "M/L": {
        "token_range": "35–150k tok",
        "image_refs": "0–4 img",
        "description": "generic vector example at M; real imagery, dense layers, or roundtrip QA upgrade to L",
    },
}


LARGE_KINDS = {
    "circos", "medical_scan", "histology", "multiplex", "eds", "fea", "cfd",
    "cad", "exploded", "landcover", "dem", "geology", "seismic",
}

SMALL_KINDS = {
    "pipeline", "timeline", "molecule", "reaction", "circuit", "control",
    "wiring", "sensor", "process", "measurement",
}

SMALL_MEDIUM_KINDS = {
    "line_plot", "distribution", "risk_table", "blot", "gel", "graticule",
    "map_legend",
}

MEDIUM_LARGE_KINDS = {
    "map", "section", "surface", "material_micro", "protein", "ligand",
    "device_panel", "composite", "detection", "segmentation", "cytometry",
    "genomic_heatmap", "phylogeny", "chromatography", "apparatus", "microfluidic",
}


def consumption_for(kind):
    """Return a conservative real-task planning range, not a billing quote."""

    if kind in SMALL_MEDIUM_KINDS:
        tier = "S/M"
    elif kind in MEDIUM_LARGE_KINDS:
        tier = "M/L"
    elif kind in LARGE_KINDS:
        tier = "L"
    elif kind in SMALL_KINDS:
        tier = "S"
    else:
        tier = "M"
    profile = WORKLOAD_PROFILES[tier]
    return {
        "tier": tier,
        "token_range": profile["token_range"],
        "image_refs": profile["image_refs"],
        "description": profile["description"],
    }


def all_cards():
    """Yield ``(category, title, subtitle, kind)`` for every catalog card."""

    for category in CATEGORIES:
        for title, subtitle, kind in category["cards"]:
            yield category, title, subtitle, kind
