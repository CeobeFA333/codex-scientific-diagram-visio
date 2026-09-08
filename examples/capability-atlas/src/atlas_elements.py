"""Editable SVG-recipe primitives for the capability atlas."""

from __future__ import annotations

import math


INK = "#233042"
MUTED = "#6B7788"
PALE = "#F4F7FA"
GRID = "#D9E0E8"


def _id(prefix, name):
    return f"{prefix}.{name}"


def text(prefix, name, value, x, y, size=11, fill=INK, anchor="start", weight="normal"):
    return {
        "type": "text", "id": _id(prefix, name), "text": value,
        "x_px": x, "y_px": y, "font_size_pt": size, "fill": fill,
        "anchor": anchor, "font_weight": weight,
    }


def line(prefix, name, x1, y1, x2, y2, stroke=INK, width=1.3, dash=None):
    item = {
        "type": "line", "id": _id(prefix, name), "x1_px": x1, "y1_px": y1,
        "x2_px": x2, "y2_px": y2, "stroke": stroke, "stroke_width_pt": width,
        "linecap": "round",
    }
    if dash:
        item["dash_mm"] = dash
    return item


def rect(prefix, name, x, y, w, h, fill="none", stroke=INK, width=1.2):
    return {
        "type": "rect", "id": _id(prefix, name), "x_px": x, "y_px": y,
        "width_px": w, "height_px": h, "fill": fill, "stroke": stroke,
        "stroke_width_pt": width,
    }


def ellipse(prefix, name, cx, cy, rx, ry, fill="none", stroke=INK, width=1.2):
    return {
        "type": "ellipse", "id": _id(prefix, name), "cx_px": cx, "cy_px": cy,
        "rx_px": rx, "ry_px": ry, "fill": fill, "stroke": stroke,
        "stroke_width_pt": width,
    }


def polyline(prefix, name, points, stroke=INK, width=1.4, fill="none", dash=None):
    item = {
        "type": "polyline", "id": _id(prefix, name), "points_px": points,
        "stroke": stroke, "stroke_width_pt": width, "fill": fill,
    }
    if dash:
        item["dash_mm"] = dash
    return item


def polygon(prefix, name, points, fill="none", stroke=INK, width=1.2):
    return {
        "type": "polygon", "id": _id(prefix, name), "points_px": points,
        "fill": fill, "stroke": stroke, "stroke_width_pt": width,
    }


def arc(prefix, name, cx, cy, radius, start, end, stroke=INK, width=1.4):
    return {
        "type": "arc", "id": _id(prefix, name), "cx_px": cx, "cy_px": cy,
        "radius_px": radius, "start_angle_deg": start, "end_angle_deg": end,
        "clockwise": True, "stroke": stroke, "stroke_width_pt": width,
    }


def arrow(prefix, name, x1, y1, x2, y2, color=INK, width=1.4):
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 9
    spread = 0.55
    p1 = [x2, y2]
    p2 = [x2 - length * math.cos(angle - spread), y2 - length * math.sin(angle - spread)]
    p3 = [x2 - length * math.cos(angle + spread), y2 - length * math.sin(angle + spread)]
    return [
        line(prefix, f"{name}.shaft", x1, y1, x2, y2, color, width),
        polygon(prefix, f"{name}.head", [p1, p2, p3], color, color, width),
    ]


def axes(prefix, x, y, w, h):
    return [
        line(prefix, "axis.x", x, y + h, x + w, y + h, MUTED, 1.0),
        line(prefix, "axis.y", x, y, x, y + h, MUTED, 1.0),
        line(prefix, "grid.1", x, y + h * .33, x + w, y + h * .33, GRID, .7),
        line(prefix, "grid.2", x, y + h * .66, x + w, y + h * .66, GRID, .7),
    ]


def motif_pipeline(prefix, x, y, w, h, accent, variant):
    items = []
    labels = {
        "encoder": ["Input", "Encode", "Bottleneck", "Decode"],
        "attention": ["Q", "K", "V", "Attention"],
        "fusion": ["Image", "Text", "Fusion", "Output"],
        "control": ["Setpoint", "Controller", "Plant", "Output"],
        "sensor": ["Sensor", "Amplify", "Acquire", "Analyze"],
        "process": ["Feed", "Treat", "Separate", "Product"],
    }.get(variant, ["Input", "Feature", "Transform", "Output"])
    bw, gap = 58, (w - 4 * 58) / 3
    centers = []
    for idx, label in enumerate(labels):
        bx = x + idx * (bw + gap)
        by = y + (12 if variant in {"encoder", "residual"} and idx in {0, 3} else 34)
        items.append(rect(prefix, f"block.{idx}", bx, by, bw, 58, "#FFFFFF" if idx != 2 else accent, accent))
        items.append(text(prefix, f"label.{idx}", label, bx + bw/2, by + 34, 7.2, "#FFFFFF" if idx == 2 else INK, "middle", "bold"))
        centers.append((bx + bw/2, by + 29))
        if idx:
            items += arrow(prefix, f"flow.{idx}", centers[idx-1][0] + bw/2, centers[idx-1][1], bx - 5, centers[idx][1], accent)
    if variant in {"residual", "control"}:
        items += [
            polyline(prefix, "return", [[centers[-1][0], centers[-1][1]+35], [centers[-1][0], y+h-12], [centers[0][0], y+h-12], [centers[0][0], centers[0][1]+35]], accent, 1.4),
            ellipse(prefix, "sum", centers[0][0], centers[0][1]+35, 8, 8, "#FFFFFF", accent),
        ]
    return items


def motif_cuboids(prefix, x, y, w, h, accent):
    items = []
    for idx, scale in enumerate((1.0, .82, .64, .46)):
        cx = x + 25 + idx * 74
        cy = y + 28 + idx * 7
        cw, ch = 48 * scale, 92 * scale
        items += [
            rect(prefix, f"tensor.{idx}.front", cx, cy, cw, ch, "#FFFFFF", accent),
            polygon(prefix, f"tensor.{idx}.top", [[cx,cy],[cx+10,cy-10],[cx+cw+10,cy-10],[cx+cw,cy]], "#E5EEF9", accent),
            polygon(prefix, f"tensor.{idx}.side", [[cx+cw,cy],[cx+cw+10,cy-10],[cx+cw+10,cy+ch-10],[cx+cw,cy+ch]], "#BCD0EA", accent),
            text(prefix, f"dim.{idx}", f"C{idx+1} × H{idx+1} × W{idx+1}", cx+cw/2, cy+ch+18, 6.4, MUTED, "middle"),
        ]
        if idx:
            items += arrow(prefix, f"flow.{idx}", cx-28, cy+ch/2, cx-6, cy+ch/2, accent)
    return items


def motif_detection(prefix, x, y, w, h, accent, segmentation=False):
    items = [rect(prefix, "image", x+22, y+8, w-44, h-20, "#E9EEF2", GRID)]
    if segmentation:
        items += [
            polygon(prefix, "mask.a", [[x+52,y+40],[x+112,y+22],[x+168,y+65],[x+137,y+121],[x+73,y+112]], accent, accent),
            polygon(prefix, "mask.b", [[x+176,y+78],[x+238,y+47],[x+270,y+103],[x+221,y+139]], "#F2B84B", "#F2B84B"),
            text(prefix, "legend.a", "class A", x+58, y+h-3, 7, accent),
            text(prefix, "legend.b", "class B", x+190, y+h-3, 7, "#B87300"),
        ]
    else:
        items += [
            rect(prefix, "bbox.a", x+48, y+28, 92, 94, "none", accent, 2),
            rect(prefix, "bbox.b", x+168, y+50, 86, 70, "none", "#D95F59", 2),
            text(prefix, "class.a", "cell 0.97", x+48, y+23, 7, accent),
            text(prefix, "class.b", "object 0.91", x+168, y+45, 7, "#D95F59"),
        ]
        for idx, (kx, ky) in enumerate(((72,62),(108,48),(92,92),(202,78),(230,94))):
            items.append(ellipse(prefix, f"keypoint.{idx}", x+kx, y+ky, 4, 4, "#FFFFFF", accent, 1.5))
    return items


def motif_plot(prefix, x, y, w, h, accent, variant):
    items = axes(prefix, x+24, y+10, w-42, h-35)
    px, py, pw, ph = x+24, y+10, w-42, h-35
    if variant in {"line_plot", "error_plot", "survival", "spectrum", "chromatography", "thermal", "nyquist"}:
        if variant == "survival":
            pts = [[px,py+12],[px+45,py+12],[px+45,py+35],[px+98,py+35],[px+98,py+63],[px+155,py+63],[px+155,py+91],[px+pw,py+91]]
        elif variant == "nyquist":
            pts = [[px+8,py+ph-4],[px+30,py+ph-38],[px+65,py+ph-66],[px+108,py+ph-73],[px+151,py+ph-59],[px+194,py+ph-30],[px+pw,py+ph-8]]
        elif variant in {"spectrum", "chromatography"}:
            pts = [[px,py+ph-7],[px+28,py+ph-9],[px+42,py+ph-70],[px+50,py+ph-8],[px+92,py+ph-12],[px+112,py+ph-105],[px+121,py+ph-10],[px+170,py+ph-14],[px+193,py+ph-56],[px+202,py+ph-8],[px+pw,py+ph-12]]
        else:
            pts = [[px,py+ph-14],[px+45,py+ph-45],[px+86,py+ph-32],[px+128,py+ph-82],[px+174,py+ph-67],[px+pw,py+18]]
        items.append(polyline(prefix, "series.a", pts, accent, 2))
        if variant in {"line_plot", "error_plot", "thermal"}:
            items.append(polyline(prefix, "series.b", [[a,b+18] for a,b in pts], "#D95F59", 1.6))
        if variant == "error_plot":
            for idx, (cx, cy) in enumerate(pts[1:-1]):
                items += [line(prefix, f"error.{idx}", cx, cy-13, cx, cy+13, MUTED, 1), line(prefix, f"cap.{idx}.a", cx-5, cy-13, cx+5, cy-13, MUTED, 1), line(prefix, f"cap.{idx}.b", cx-5, cy+13, cx+5, cy+13, MUTED, 1)]
        return items
    if variant == "distribution":
        vals = [45, 76, 104, 70, 34]
        for idx, bh in enumerate(vals):
            items.append(rect(prefix, f"bar.{idx}", px+18+idx*43, py+ph-bh, 26, bh, accent if idx != 3 else "#D95F59", "none", 0))
        items += [line(prefix,"box.whisker",px+pw-34,py+25,px+pw-34,py+ph-15,MUTED,1), rect(prefix,"box",px+pw-48,py+53,28,48,"#FFFFFF",accent,1.5)]
        return items
    return items


def motif_matrix(prefix, x, y, w, h, accent, variant):
    items = []
    rows, cols = (5, 9) if variant == "genomic_heatmap" else (6, 8)
    cw, ch = 25, 20
    sx, sy = x + 48, y + 18
    palette = ["#EFF3F8", "#C8D7E8", accent, "#F2B84B", "#D95F59"]
    for row in range(rows):
        for col in range(cols):
            items.append(rect(prefix, f"cell.{row}.{col}", sx+col*cw, sy+row*ch, cw-1, ch-1, palette[(row*3+col*2)%len(palette)], "none", 0))
    if variant == "genomic_heatmap":
        for row in range(rows):
            items.append(rect(prefix, f"track.{row}", sx-20, sy+row*ch, 12, ch-1, palette[row%len(palette)], "none", 0))
    items += [text(prefix,"low","low",sx,sy+rows*ch+18,6.5,MUTED), text(prefix,"high","high",sx+cols*cw,sy+rows*ch+18,6.5,MUTED,"end")]
    return items


def motif_network(prefix, x, y, w, h, accent, variant):
    items = []
    if variant == "circos":
        cx, cy = x+w/2, y+h/2
        colors = [accent,"#D95F59","#F2B84B","#6B8F44","#6688AA"]
        for idx in range(10):
            items.append({"type":"annular_sector","id":_id(prefix,f"sector.{idx}"),"cx_px":cx,"cy_px":cy,"inner_radius_px":58,"outer_radius_px":76,"start_angle_deg":idx*36+2,"end_angle_deg":idx*36+32,"clockwise":True,"fill":colors[idx%5],"stroke":"#FFFFFF","stroke_width_pt":1})
        for idx in range(5):
            items.append(arc(prefix,f"link.{idx}",cx,cy,40+idx*3,210+idx*12,25+idx*18,colors[idx],1.4))
        return items
    nodes = [(x+30,y+75),(x+88,y+28),(x+95,y+122),(x+160,y+68),(x+225,y+28),(x+252,y+106)]
    edges = [(0,1),(0,2),(1,3),(2,3),(3,4),(3,5),(4,5)]
    for idx,(a,b) in enumerate(edges):
        items.append(line(prefix,f"edge.{idx}",*nodes[a],*nodes[b],GRID,1.3))
    for idx,(cx,cy) in enumerate(nodes):
        items.append(ellipse(prefix,f"node.{idx}",cx,cy,10 if idx not in {0,3} else 14,10 if idx not in {0,3} else 14,accent if idx in {0,3} else "#FFFFFF",accent,1.5))
    return items


def motif_medical(prefix, x, y, w, h, accent, variant):
    items = [rect(prefix,"frame",x+25,y+8,w-50,h-18,"#17212B",GRID,1)]
    if variant in {"blot","gel"}:
        for lane in range(6):
            for band in range(3):
                shade = "#B9C5D0" if (lane+band)%3 else "#F3F5F7"
                items.append(rect(prefix,f"band.{lane}.{band}",x+50+lane*36,y+35+band*35+(lane%2)*5,24,5,shade,"none",0))
        items.append(text(prefix,"ladder","kDa",x+31,y+28,6.5,"#FFFFFF"))
    elif variant in {"cytometry","embedding"}:
        for idx in range(42):
            cx=x+50+(idx*47%205); cy=y+25+(idx*31%105)
            items.append(ellipse(prefix,f"point.{idx}",cx,cy,2.5,2.5,accent,"none",0))
        items.append(polygon(prefix,"gate",[[x+68,y+110],[x+92,y+43],[x+180,y+32],[x+226,y+92],[x+160,y+130]],"none","#F2B84B",1.6))
    else:
        items += [ellipse(prefix,"scan.outer",x+w/2,y+h/2,72,62,"#606E7B","#FFFFFF",1),ellipse(prefix,"scan.inner",x+w/2,y+h/2,38,45,"#253240","#AAB7C4",1),ellipse(prefix,"roi",x+w/2+18,y+h/2-8,18,13,"none",accent,2)]
        items += arrow(prefix,"callout",x+w/2+36,y+h/2-18,x+w-35,y+22,accent)
    return items


def motif_molecule(prefix, x, y, w, h, accent, reaction=False):
    items=[]
    centers=[(x+70,y+72),(x+180,y+72)] if reaction else [(x+w/2,y+h/2)]
    for ci,(cx,cy) in enumerate(centers):
        pts=[]
        for k in range(6):
            angle=math.radians(k*60-30); pts.append([cx+40*math.cos(angle),cy+40*math.sin(angle)])
        items.append(polygon(prefix,f"ring.{ci}",pts,"none",accent,2))
        for k in range(0,6,2):
            a,b=pts[k],pts[(k+1)%6]
            items.append(line(prefix,f"double.{ci}.{k}",a[0]*.88+b[0]*.12,a[1]*.88+b[1]*.12,a[0]*.12+b[0]*.88,a[1]*.12+b[1]*.88,accent,1))
        items.append(text(prefix,f"atom.{ci}","N",cx+30,cy-30,8,"#D95F59","middle","bold"))
    if reaction:
        items += arrow(prefix,"reaction",x+115,y+72,x+137,y+72,INK,1.5)
        items.append(text(prefix,"conditions","cat. · 80 °C",x+126,y+51,6.5,MUTED,"middle"))
    else:
        items += [line(prefix,"bond.a",x+w/2+35,y+h/2+20,x+w/2+75,y+h/2+48,accent,2),text(prefix,"group","OH",x+w/2+86,y+h/2+57,8,"#D95F59","middle","bold")]
    return items


def motif_engineering(prefix, x, y, w, h, accent, variant):
    if variant in {"fea","cfd","surface"}:
        items=[]
        colors=["#355CBB","#39A7D0","#73C879","#F2D15D","#E75B45"]
        for row in range(6):
            for col in range(10):
                pts=[[x+35+col*23,y+20+row*20],[x+58+col*23,y+18+row*20],[x+56+col*23,y+38+row*20],[x+33+col*23,y+40+row*20]]
                items.append(polygon(prefix,f"field.{row}.{col}",pts,colors[min(4,(row+col)//3)],"none",0))
        if variant == "cfd":
            for idx in range(4): items.append(polyline(prefix,f"stream.{idx}",[[x+25,y+35+idx*28],[x+110,y+22+idx*26],[x+190,y+42+idx*19],[x+270,y+28+idx*22]],"#FFFFFF",1.1))
        items.append(rect(prefix,"colorbar",x+w-30,y+20,10,120,accent,"#FFFFFF",.8))
        return items
    if variant in {"circuit","wiring"}:
        items=[line(prefix,"wire.top",x+30,y+38,x+w-35,y+38,accent,1.8),line(prefix,"wire.bottom",x+30,y+118,x+w-35,y+118,accent,1.8)]
        items += [rect(prefix,"resistor",x+78,y+28,48,20,"#FFFFFF",accent,1.5),ellipse(prefix,"source",x+48,y+78,17,17,"#FFFFFF",accent,1.5),line(prefix,"source.link.a",x+48,y+38,x+48,y+61,accent,1.5),line(prefix,"source.link.b",x+48,y+95,x+48,y+118,accent,1.5)]
        items += [line(prefix,"capacitor.a",x+184,y+66,x+218,y+66,accent,2),line(prefix,"capacitor.b",x+184,y+77,x+218,y+77,accent,2),line(prefix,"capacitor.link.a",x+201,y+38,x+201,y+66,accent,1.5),line(prefix,"capacitor.link.b",x+201,y+77,x+201,y+118,accent,1.5),text(prefix,"label","R1        C1",x+91,y+22,7,MUTED)]
        return items
    if variant in {"cad","exploded","measurement"}:
        items=[rect(prefix,"part.a",x+38,y+48,74,62,"#FFFFFF",accent,1.6),polygon(prefix,"part.b",[[x+138,y+40],[x+205,y+25],[x+237,y+65],[x+170,y+80]],"#E6EEF7",accent,1.6),ellipse(prefix,"hole",x+75,y+79,17,17,"#FFFFFF",accent,1.3)]
        items += arrow(prefix,"dimension",x+35,y+130,x+238,y+130,MUTED,1)
        items.append(text(prefix,"dimension.label","120.0 mm",x+137,y+146,7,MUTED,"middle"))
        if variant=="exploded": items += arrow(prefix,"explode",x+112,y+79,x+135,y+66,accent)
        return items
    return motif_pipeline(prefix,x,y,w,h,accent,"pipeline")


def motif_apparatus(prefix, x, y, w, h, accent, variant):
    if variant in {"microfluidic","layers"}:
        items=[]
        if variant=="microfluidic":
            items += [rect(prefix,"chip",x+35,y+24,w-70,h-46,"#F2F8FA",accent,1.6),line(prefix,"channel.a",x+50,y+70,x+w/2,y+70,accent,6),line(prefix,"channel.b",x+w/2,y+35,x+w/2,y+112,accent,6),line(prefix,"channel.c",x+w/2,y+70,x+w-50,y+70,accent,6)]
            for idx,(cx,cy) in enumerate(((x+50,y+70),(x+w/2,y+35),(x+w-50,y+70))): items.append(ellipse(prefix,f"port.{idx}",cx,cy,9,9,"#FFFFFF",accent,1.5))
        else:
            colors=["#DDE8F5",accent,"#F3D7A4","#DCE7D0"]
            for idx,color in enumerate(colors): items.append(polygon(prefix,f"layer.{idx}",[[x+55+idx*7,y+35+idx*25],[x+210+idx*7,y+35+idx*25],[x+250+idx*7,y+52+idx*25],[x+95+idx*7,y+52+idx*25]],color,accent,1.1))
        return items
    items=[rect(prefix,"source",x+25,y+52,48,48,"#FFFFFF",accent,1.5),ellipse(prefix,"sample",x+146,y+76,24,24,"#F3D7A4",accent,1.5),rect(prefix,"detector",x+222,y+48,56,56,"#FFFFFF",accent,1.5)]
    items += arrow(prefix,"beam.a",x+73,y+76,x+117,y+76,accent,2)
    items += arrow(prefix,"beam.b",x+170,y+76,x+219,y+76,accent,2)
    items += [text(prefix,"source.label","SOURCE",x+49,y+116,6.5,MUTED,"middle"),text(prefix,"sample.label","SAMPLE",x+146,y+116,6.5,MUTED,"middle"),text(prefix,"detector.label","DETECT",x+250,y+116,6.5,MUTED,"middle")]
    return items


def motif_map(prefix, x, y, w, h, accent, variant):
    items=[rect(prefix,"map.frame",x+22,y+8,w-44,h-18,"#E7EFE7",GRID,1)]
    regions=[[[x+35,y+27],[x+93,y+18],[x+116,y+61],[x+78,y+86],[x+39,y+70]],[[x+116,y+61],[x+181,y+24],[x+220,y+58],[x+188,y+98],[x+145,y+108]],[[x+78,y+86],[x+145,y+108],[x+130,y+142],[x+61,y+137]]]
    colors=["#BFD8B8","#E8D39A","#B7CDD9"]
    for idx,pts in enumerate(regions): items.append(polygon(prefix,f"region.{idx}",pts,colors[idx],"#FFFFFF",1.2))
    if variant in {"dem","geology","section"}:
        for idx in range(4): items.append(arc(prefix,f"contour.{idx}",x+160,y+82,28+idx*16,195,355,accent,.9))
    elif variant=="graticule":
        for idx in range(3):
            items += [line(prefix,f"lon.{idx}",x+72+idx*62,y+12,x+72+idx*62,y+h-15,"#FFFFFF",.8),line(prefix,f"lat.{idx}",x+25,y+42+idx*36,x+w-25,y+42+idx*36,"#FFFFFF",.8)]
    else:
        for idx,(cx,cy) in enumerate(((x+75,y+54),(x+152,y+82),(x+211,y+51),(x+112,y+121))): items.append(ellipse(prefix,f"site.{idx}",cx,cy,5+idx,5+idx,accent,"#FFFFFF",1))
    items += [text(prefix,"north","N",x+w-43,y+31,9,INK,"middle","bold"),polygon(prefix,"north.arrow",[[x+w-43,y+37],[x+w-51,y+57],[x+w-43,y+52],[x+w-35,y+57]],INK,INK,1),line(prefix,"scale",x+w-98,y+h-28,x+w-40,y+h-28,INK,3)]
    return items


def motif_for(kind, prefix, x, y, w, h, accent):
    if kind in {"pipeline","encoder","residual","attention","fusion","flow_chart","control","sensor","process","timeline","risk_table"}:
        return motif_pipeline(prefix,x,y,w,h,accent,kind)
    if kind=="cuboids": return motif_cuboids(prefix,x,y,w,h,accent)
    if kind in {"detection","segmentation","roi","histology","multiplex","device_panel","composite"}: return motif_detection(prefix,x,y,w,h,accent,kind in {"segmentation","roi","multiplex"})
    if kind in {"line_plot","error_plot","distribution","survival","forest","spectrum","chromatography","thermal","nyquist"}: return motif_plot(prefix,x,y,w,h,accent,"error_plot" if kind=="forest" else kind)
    if kind in {"heatmap","genomic_heatmap","eds","landcover"}: return motif_matrix(prefix,x,y,w,h,accent,"genomic_heatmap" if kind=="genomic_heatmap" else "heatmap")
    if kind in {"tree","phylogeny","protein","ligand","circos"}: return motif_network(prefix,x,y,w,h,accent,"circos" if kind=="circos" else "tree")
    if kind in {"medical_scan","microscopy","cytometry","embedding","blot","gel","material_micro"}: return motif_medical(prefix,x,y,w,h,accent,kind)
    if kind in {"molecule","reaction"}: return motif_molecule(prefix,x,y,w,h,accent,kind=="reaction")
    if kind in {"circuit","wiring","fea","cfd","surface","cad","exploded","measurement"}: return motif_engineering(prefix,x,y,w,h,accent,kind)
    if kind in {"apparatus","microfluidic","layers"}: return motif_apparatus(prefix,x,y,w,h,accent,kind)
    if kind in {"map","dem","geology","seismic","section","graticule","map_legend"}: return motif_map(prefix,x,y,w,h,accent,kind)
    return motif_pipeline(prefix,x,y,w,h,accent,"pipeline")


def build_card(prefix, title_value, subtitle, kind, x, y, w, h, accent):
    children = [
        rect(prefix,"card",x,y,w,h,"#FFFFFF","#D9E0E8",1.0),
        rect(prefix,"accent",x,y,7,h,accent,"none",0),
        text(prefix,"title",title_value,x+22,y+31,10.5,INK,"start","bold"),
        text(prefix,"subtitle",subtitle,x+22,y+54,7.2,MUTED),
    ]
    children.extend(motif_for(kind,prefix,x+18,y+69,w-36,h-84,accent))
    return {"type":"group","id":prefix,"aria_label":f"{title_value}: {subtitle}","children":children}
