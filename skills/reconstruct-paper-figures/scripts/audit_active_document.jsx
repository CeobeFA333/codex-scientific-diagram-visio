#target illustrator

(function () {
    if (app.documents.length === 0) {
        alert("No active Illustrator document.");
        return;
    }

    var documentRef = app.activeDocument;
    var sourceFile;
    try {
        sourceFile = documentRef.fullName;
    } catch (error) {
        alert("This document has never been saved. Save a copy first, then run the audit.");
        return;
    }

    function jsonEscape(value) {
        return String(value)
            .replace(/\\/g, "\\\\")
            .replace(/\"/g, "\\\"")
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function jsonString(value) {
        return "\"" + jsonEscape(value) + "\"";
    }

    function numberOrNull(value) {
        var numeric = Number(value);
        return isFinite(numeric) ? String(Math.round(numeric * 10000) / 10000) : "null";
    }

    function colorObject(color) {
        if (!color || !color.typename) {
            return "{\"type\":\"Unknown\"}";
        }
        if (color.typename === "RGBColor") {
            return "{\"type\":\"RGB\",\"red\":" + numberOrNull(color.red) +
                ",\"green\":" + numberOrNull(color.green) +
                ",\"blue\":" + numberOrNull(color.blue) + "}";
        }
        if (color.typename === "CMYKColor") {
            return "{\"type\":\"CMYK\",\"cyan\":" + numberOrNull(color.cyan) +
                ",\"magenta\":" + numberOrNull(color.magenta) +
                ",\"yellow\":" + numberOrNull(color.yellow) +
                ",\"black\":" + numberOrNull(color.black) + "}";
        }
        if (color.typename === "GrayColor") {
            return "{\"type\":\"Gray\",\"gray\":" + numberOrNull(color.gray) + "}";
        }
        if (color.typename === "SpotColor") {
            return "{\"type\":\"Spot\",\"name\":" + jsonString(color.spot.name) + "}";
        }
        return "{\"type\":" + jsonString(color.typename) + "}";
    }

    function textKindName(kind) {
        if (kind === TextType.POINTTEXT) { return "point"; }
        if (kind === TextType.AREATEXT) { return "area"; }
        if (kind === TextType.PATHTEXT) { return "path"; }
        return "unknown";
    }

    function parentObject(item) {
        var parent = item.parent;
        var ancestorTypename = "";
        var ancestorName = "";
        try {
            ancestorTypename = parent.parent.typename || "";
            ancestorName = parent.parent.name || "";
        } catch (error) {
            // Document-level parents do not expose another page-item ancestor.
        }
        return "{\"typename\":" + jsonString(parent.typename || "") +
            ",\"name\":" + jsonString(parent.name || "") +
            ",\"parent_typename\":" + jsonString(ancestorTypename) +
            ",\"parent_name\":" + jsonString(ancestorName) + "}";
    }

    function pointArray(point) {
        return "[" + numberOrNull(point[0]) + "," + numberOrNull(point[1]) + "]";
    }

    function textPathObject(frame) {
        if (frame.kind !== TextType.PATHTEXT) {
            return "null";
        }
        var path = frame.textPath;
        var pointCount = path.pathPoints.length;
        var startAnchor = pointCount ? pointArray(path.pathPoints[0].anchor) : "null";
        var endAnchor = pointCount ? pointArray(path.pathPoints[pointCount - 1].anchor) : "null";
        var bounds = "[" + numberOrNull(path.left) + "," + numberOrNull(path.top) + "," +
            numberOrNull(path.left + path.width) + "," + numberOrNull(path.top - path.height) + "]";
        return "{" +
            "\"closed\":" + (path.closed ? "true" : "false") +
            ",\"point_count\":" + pointCount +
            ",\"bounds_pt\":" + bounds +
            ",\"start_anchor_pt\":" + startAnchor +
            ",\"end_anchor_pt\":" + endAnchor +
            "}";
    }

    var warnings = [];
    var textRows = [];
    var unnamedSingleCharacterCount = 0;
    var i;
    for (i = 0; i < documentRef.textFrames.length; i += 1) {
        var frame = documentRef.textFrames[i];
        if ((!frame.name || frame.name === "") && String(frame.contents).length <= 1) {
            unnamedSingleCharacterCount += 1;
        }
        var attributes = frame.textRange.characterAttributes;
        var fontName = "";
        try {
            fontName = attributes.textFont.name;
        } catch (fontError) {
            fontName = "<mixed-or-missing>";
            warnings.push("Text frame " + i + " has a mixed or missing font.");
        }
        var sizePt = Number(attributes.size);
        if (isFinite(sizePt) && Math.abs(sizePt - 8.5) > 0.05) {
            warnings.push("Text frame " + i + " is " + sizePt + " pt, expected 8.5 pt unless documented.");
        }
        var bounds = frame.geometricBounds;
        textRows.push(
            "{" +
            "\"index\":" + i +
            ",\"name\":" + jsonString(frame.name || "") +
            ",\"contents\":" + jsonString(frame.contents) +
            ",\"kind\":" + jsonString(textKindName(frame.kind)) +
            ",\"font_postscript_name\":" + jsonString(fontName) +
            ",\"size_pt\":" + numberOrNull(sizePt) +
            ",\"fill\":" + colorObject(attributes.fillColor) +
            ",\"locked\":" + (frame.locked ? "true" : "false") +
            ",\"hidden\":" + (frame.hidden ? "true" : "false") +
            ",\"parent\":" + parentObject(frame) +
            ",\"bounds_pt\":[" + numberOrNull(bounds[0]) + "," + numberOrNull(bounds[1]) + "," +
                numberOrNull(bounds[2]) + "," + numberOrNull(bounds[3]) + "]" +
            ",\"text_path\":" + textPathObject(frame) +
            "}"
        );
    }
    if (unnamedSingleCharacterCount >= 3) {
        warnings.push(
            "Possible fragmented text: " + unnamedSingleCharacterCount +
            " unnamed single-character Type frames. Check imported SVG path text."
        );
    }

    var pathRows = [];
    for (i = 0; i < documentRef.pathItems.length; i += 1) {
        var pathItem = documentRef.pathItems[i];
        var pathBounds = pathItem.geometricBounds;
        var pathPointCount = pathItem.pathPoints.length;
        var pathStartAnchor = pathPointCount ? pointArray(pathItem.pathPoints[0].anchor) : "null";
        var pathEndAnchor = pathPointCount ? pointArray(pathItem.pathPoints[pathPointCount - 1].anchor) : "null";
        pathRows.push(
            "{" +
            "\"index\":" + i +
            ",\"name\":" + jsonString(pathItem.name || "") +
            ",\"closed\":" + (pathItem.closed ? "true" : "false") +
            ",\"filled\":" + (pathItem.filled ? "true" : "false") +
            ",\"stroked\":" + (pathItem.stroked ? "true" : "false") +
            ",\"locked\":" + (pathItem.locked ? "true" : "false") +
            ",\"hidden\":" + (pathItem.hidden ? "true" : "false") +
            ",\"stroke_width_pt\":" + numberOrNull(pathItem.strokeWidth) +
            ",\"point_count\":" + pathPointCount +
            ",\"parent\":" + parentObject(pathItem) +
            ",\"bounds_pt\":[" + numberOrNull(pathBounds[0]) + "," +
                numberOrNull(pathBounds[1]) + "," + numberOrNull(pathBounds[2]) + "," +
                numberOrNull(pathBounds[3]) + "]" +
            ",\"start_anchor_pt\":" + pathStartAnchor +
            ",\"end_anchor_pt\":" + pathEndAnchor +
            "}"
        );
    }

    var artboard = documentRef.artboards[documentRef.artboards.getActiveArtboardIndex()].artboardRect;
    var widthPt = artboard[2] - artboard[0];
    var heightPt = artboard[1] - artboard[3];
    var warningRows = [];
    for (i = 0; i < warnings.length; i += 1) {
        warningRows.push(jsonString(warnings[i]));
    }

    var report = "{" +
        "\n  \"source_document\": " + jsonString(sourceFile.fsName) + "," +
        "\n  \"illustrator_version\": " + jsonString(app.version) + "," +
        "\n  \"document_color_space\": " + jsonString(String(documentRef.documentColorSpace)) + "," +
        "\n  \"active_artboard\": {\"width_pt\": " + numberOrNull(widthPt) +
            ", \"height_pt\": " + numberOrNull(heightPt) +
            ", \"width_mm\": " + numberOrNull(widthPt / 2.8346456693) +
            ", \"height_mm\": " + numberOrNull(heightPt / 2.8346456693) + "}," +
        "\n  \"counts\": {" +
            "\"text_frames\": " + documentRef.textFrames.length +
            ", \"path_items\": " + documentRef.pathItems.length +
            ", \"compound_path_items\": " + documentRef.compoundPathItems.length +
            ", \"group_items\": " + documentRef.groupItems.length +
            ", \"placed_items\": " + documentRef.placedItems.length +
            ", \"raster_items\": " + documentRef.rasterItems.length + "}," +
        "\n  \"text_frames\": [\n    " + textRows.join(",\n    ") + "\n  ]," +
        "\n  \"path_items\": [\n    " + pathRows.join(",\n    ") + "\n  ]," +
        "\n  \"warnings\": [" + (warnings.length ? "\n    " + warningRows.join(",\n    ") + "\n  " : "") + "]" +
        "\n}\n";

    var baseName = sourceFile.name.replace(/\.[^.]+$/, "");
    var outputFile = new File(sourceFile.parent.fsName + "/" + baseName + "_illustrator_audit.json");
    if (outputFile.exists) {
        alert("Audit output already exists and will not be overwritten:\n" + outputFile.fsName);
        return;
    }
    outputFile.encoding = "UTF-8";
    if (!outputFile.open("w")) {
        alert("Could not create audit output:\n" + outputFile.fsName);
        return;
    }
    outputFile.write(report);
    outputFile.close();

    alert(
        "Illustrator audit created:\n" + outputFile.fsName +
        "\n\nText frames: " + documentRef.textFrames.length +
        "\nPaths: " + documentRef.pathItems.length +
        "\nRaster/placed: " + (documentRef.rasterItems.length + documentRef.placedItems.length) +
        "\nWarnings: " + warnings.length
    );
}());
