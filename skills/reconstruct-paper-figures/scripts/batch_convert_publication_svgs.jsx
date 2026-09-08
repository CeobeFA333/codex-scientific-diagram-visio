#target illustrator

/*
 * Convert the final fig01..fig09 publication SVG candidates to AI and
 * Illustrator-editable PDF files, recording a separate object audit at each
 * stage. The script is deliberately fail-closed and never overwrites files.
 * It leaves documents that were already open before the run untouched.
 */
(function () {
    var PT_PER_MM = 2.8346456693;
    var projectRoot = new File($.fileName).parent.parent.parent.parent;
    var logLines = [];
    var processed = 0;
    var skipped = 0;
    var failed = 0;

    function escapeJson(value) {
        return String(value)
            .replace(/\\/g, "\\\\")
            .replace(/\"/g, "\\\"")
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function quote(value) {
        return "\"" + escapeJson(value) + "\"";
    }

    function finiteNumber(value) {
        var n = Number(value);
        if (!isFinite(n)) { return "null"; }
        return String(Math.round(n * 10000) / 10000);
    }

    function textKindName(kind) {
        if (kind === TextType.POINTTEXT) { return "point"; }
        if (kind === TextType.AREATEXT) { return "area"; }
        if (kind === TextType.PATHTEXT) { return "path"; }
        return "unknown";
    }

    function colorJson(color) {
        if (!color || !color.typename) { return "{\"type\":\"Unknown\"}"; }
        if (color.typename === "RGBColor") {
            return "{\"type\":\"RGB\",\"red\":" + finiteNumber(color.red) +
                ",\"green\":" + finiteNumber(color.green) +
                ",\"blue\":" + finiteNumber(color.blue) + "}";
        }
        if (color.typename === "CMYKColor") {
            return "{\"type\":\"CMYK\",\"cyan\":" + finiteNumber(color.cyan) +
                ",\"magenta\":" + finiteNumber(color.magenta) +
                ",\"yellow\":" + finiteNumber(color.yellow) +
                ",\"black\":" + finiteNumber(color.black) + "}";
        }
        if (color.typename === "GrayColor") {
            return "{\"type\":\"Gray\",\"gray\":" + finiteNumber(color.gray) + "}";
        }
        return "{\"type\":" + quote(color.typename) + "}";
    }

    function boundsJson(bounds) {
        return "[" + finiteNumber(bounds[0]) + "," + finiteNumber(bounds[1]) +
            "," + finiteNumber(bounds[2]) + "," + finiteNumber(bounds[3]) + "]";
    }

    function collectAudit(documentRef, stage, sourcePath) {
        var warnings = [];
        var textRows = [];
        var pathRows = [];
        var i;

        for (i = 0; i < documentRef.textFrames.length; i += 1) {
            var frame = documentRef.textFrames[i];
            var attributes = frame.textRange.characterAttributes;
            var fontName = "";
            var fontFamily = "";
            var fontStyle = "";
            try {
                fontName = attributes.textFont.name;
                fontFamily = attributes.textFont.family;
                fontStyle = attributes.textFont.style;
            } catch (fontError) {
                fontName = "<mixed-or-missing>";
                warnings.push("Text frame " + i + " has a mixed or missing font.");
            }
            var sizePt = Number(attributes.size);
            if (isFinite(sizePt) && Math.abs(sizePt - 8.5) > 0.05) {
                warnings.push("Text frame " + i + " is " + sizePt + " pt; verify documented exception.");
            }
            if (fontFamily !== "Times New Roman") {
                warnings.push("Text frame " + i + " uses " + fontFamily + "; expected Times New Roman or approved fallback.");
            }
            textRows.push(
                "{" +
                "\"index\":" + i +
                ",\"name\":" + quote(frame.name || "") +
                ",\"contents\":" + quote(frame.contents) +
                ",\"kind\":" + quote(textKindName(frame.kind)) +
                ",\"font_postscript_name\":" + quote(fontName) +
                ",\"font_family\":" + quote(fontFamily) +
                ",\"font_style\":" + quote(fontStyle) +
                ",\"size_pt\":" + finiteNumber(sizePt) +
                ",\"horizontal_scale\":" + finiteNumber(attributes.horizontalScale) +
                ",\"vertical_scale\":" + finiteNumber(attributes.verticalScale) +
                ",\"fill\":" + colorJson(attributes.fillColor) +
                ",\"bounds_pt\":" + boundsJson(frame.geometricBounds) +
                "}"
            );
        }

        for (i = 0; i < documentRef.pathItems.length; i += 1) {
            var pathItem = documentRef.pathItems[i];
            pathRows.push(
                "{" +
                "\"index\":" + i +
                ",\"name\":" + quote(pathItem.name || "") +
                ",\"closed\":" + (pathItem.closed ? "true" : "false") +
                ",\"filled\":" + (pathItem.filled ? "true" : "false") +
                ",\"stroked\":" + (pathItem.stroked ? "true" : "false") +
                ",\"stroke_width_pt\":" + finiteNumber(pathItem.strokeWidth) +
                ",\"point_count\":" + pathItem.pathPoints.length +
                ",\"bounds_pt\":" + boundsJson(pathItem.geometricBounds) +
                "}"
            );
        }

        var artboard = documentRef.artboards[documentRef.artboards.getActiveArtboardIndex()].artboardRect;
        var widthPt = artboard[2] - artboard[0];
        var heightPt = artboard[1] - artboard[3];
        var warningRows = [];
        for (i = 0; i < warnings.length; i += 1) { warningRows.push(quote(warnings[i])); }

        return "{" +
            "\n  \"stage\": " + quote(stage) + "," +
            "\n  \"source_document\": " + quote(sourcePath) + "," +
            "\n  \"illustrator_version\": " + quote(app.version) + "," +
            "\n  \"active_artboard\": {\"width_pt\": " + finiteNumber(widthPt) +
                ", \"height_pt\": " + finiteNumber(heightPt) +
                ", \"width_mm\": " + finiteNumber(widthPt / PT_PER_MM) +
                ", \"height_mm\": " + finiteNumber(heightPt / PT_PER_MM) + "}," +
            "\n  \"counts\": {\"text_frames\": " + documentRef.textFrames.length +
                ", \"path_items\": " + documentRef.pathItems.length +
                ", \"compound_path_items\": " + documentRef.compoundPathItems.length +
                ", \"group_items\": " + documentRef.groupItems.length +
                ", \"placed_items\": " + documentRef.placedItems.length +
                ", \"raster_items\": " + documentRef.rasterItems.length + "}," +
            "\n  \"text_frames\": [\n    " + textRows.join(",\n    ") + "\n  ]," +
            "\n  \"path_items\": [\n    " + pathRows.join(",\n    ") + "\n  ]," +
            "\n  \"warnings\": [" + (warningRows.length ? "\n    " + warningRows.join(",\n    ") + "\n  " : "") + "]" +
            "\n}\n";
    }

    function writeNewFile(fileRef, contents) {
        if (fileRef.exists) { throw new Error("Refusing to overwrite " + fileRef.fsName); }
        fileRef.encoding = "UTF-8";
        if (!fileRef.open("w")) { throw new Error("Could not create " + fileRef.fsName); }
        fileRef.write(contents);
        fileRef.close();
    }

    function closeWithoutSaving(documentRef) {
        try { documentRef.close(SaveOptions.DONOTSAVECHANGES); } catch (ignore) {}
    }

    function convertFigure(figureId) {
        var vectorFolder = new Folder(projectRoot.fsName + "/organized/figures/" + figureId + "/vector");
        var stem = figureId + "_publication_tnr_8_5pt";
        var svgFile = new File(vectorFolder.fsName + "/" + stem + ".svg");
        var aiFile = new File(vectorFolder.fsName + "/" + stem + ".ai");
        var pdfFile = new File(vectorFolder.fsName + "/" + stem + "_editable.pdf");
        var svgAudit = new File(vectorFolder.fsName + "/" + stem + "_svg_import_illustrator_audit.json");
        var aiAudit = new File(vectorFolder.fsName + "/" + stem + "_ai_reopen_illustrator_audit.json");
        var pdfAudit = new File(vectorFolder.fsName + "/" + stem + "_pdf_illustrator_audit.json");

        if (!svgFile.exists) {
            skipped += 1;
            logLines.push(figureId + ": skipped; publication SVG is missing.");
            return;
        }
        if (aiFile.exists || pdfFile.exists || svgAudit.exists || aiAudit.exists || pdfAudit.exists) {
            skipped += 1;
            logLines.push(figureId + ": skipped; one or more outputs already exist.");
            return;
        }

        var documentRef = null;
        try {
            documentRef = app.open(svgFile);
            writeNewFile(svgAudit, collectAudit(documentRef, "svg_import", svgFile.fsName));

            var aiOptions = new IllustratorSaveOptions();
            aiOptions.pdfCompatible = true;
            aiOptions.compressed = true;
            aiOptions.embedICCProfile = true;
            documentRef.saveAs(aiFile, aiOptions);
            documentRef.close(SaveOptions.SAVECHANGES);
            documentRef = null;

            documentRef = app.open(aiFile);
            writeNewFile(aiAudit, collectAudit(documentRef, "ai_reopen", aiFile.fsName));

            var pdfOptions = new PDFSaveOptions();
            pdfOptions.compatibility = PDFCompatibility.ACROBAT7;
            pdfOptions.preserveEditability = true;
            pdfOptions.generateThumbnails = true;
            pdfOptions.optimization = true;
            pdfOptions.viewAfterSaving = false;
            documentRef.saveAs(pdfFile, pdfOptions);
            writeNewFile(pdfAudit, collectAudit(documentRef, "editable_pdf", pdfFile.fsName));
            documentRef.close(SaveOptions.SAVECHANGES);
            documentRef = null;

            processed += 1;
            logLines.push(figureId + ": AI and editable PDF created; all three audits recorded.");
        } catch (error) {
            failed += 1;
            logLines.push(figureId + ": FAILED: " + error.message + " (line " + error.line + ")");
            if (documentRef) { closeWithoutSaving(documentRef); }
        }
    }

    for (var n = 1; n <= 9; n += 1) {
        convertFigure("fig" + (n < 10 ? "0" + n : n));
    }

    var logFile = new File(projectRoot.fsName + "/organized/figures/batch_illustrator_conversion_log.txt");
    if (!logFile.exists) {
        writeNewFile(logFile, "Illustrator " + app.version + "\n" + logLines.join("\n") + "\n");
    }
    alert(
        "Publication batch finished.\n" +
        "Processed: " + processed + "\n" +
        "Skipped: " + skipped + "\n" +
        "Failed: " + failed + "\n\n" + logLines.join("\n")
    );
}());
