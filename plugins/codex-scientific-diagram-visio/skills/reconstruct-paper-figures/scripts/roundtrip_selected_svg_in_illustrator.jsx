#target illustrator

/*
 * Reusable, fail-closed SVG -> AI -> editable PDF roundtrip for Illustrator.
 *
 * The operator selects one SVG. The script creates new sibling artifacts and
 * three stage audits without overwriting anything:
 *   <stem>_ai_roundtrip_test.ai
 *   <stem>_ai_roundtrip_test_illustrator_audit.json
 *   <stem>_ai_roundtrip_test_editable.pdf
 *   <stem>_ai_roundtrip_test_editable_illustrator_audit.json
 *   <stem>_svg_import_roundtrip_illustrator_audit.json
 *   <stem>_roundtrip_log.txt
 *
 * The PDF is closed and reopened before its audit is written. This is a true
 * persistence check, not an audit of the in-memory AI document after Save As.
 */
(function () {
    var PT_PER_MM = 2.8346456693;
    var silentMode = $.global.__roundtripSilent === true;

    function stopWithMessage(message) {
        if (silentMode) { throw new Error(message); }
        alert(message);
    }

    function escapeJson(value) {
        return String(value)
            .replace(/\\/g, "\\\\")
            .replace(/\"/g, "\\\"")
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function quote(value) { return "\"" + escapeJson(value) + "\""; }

    function finiteNumber(value) {
        var number = Number(value);
        if (!isFinite(number)) { return "null"; }
        return String(Math.round(number * 10000) / 10000);
    }

    function textKindName(kind) {
        if (kind === TextType.POINTTEXT) { return "point"; }
        if (kind === TextType.AREATEXT) { return "area"; }
        if (kind === TextType.PATHTEXT) { return "path"; }
        return "unknown";
    }

    function boundsJson(bounds) {
        return "[" + finiteNumber(bounds[0]) + "," + finiteNumber(bounds[1]) +
            "," + finiteNumber(bounds[2]) + "," + finiteNumber(bounds[3]) + "]";
    }

    function collectAudit(documentRef, stage, sourcePath) {
        var warnings = [];
        var textRows = [];
        var pathRows = [];
        var placedRows = [];
        var i;
        var artboard = documentRef.artboards[documentRef.artboards.getActiveArtboardIndex()].artboardRect;
        var widthPt = artboard[2] - artboard[0];
        var heightPt = artboard[1] - artboard[3];

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

        for (i = 0; i < documentRef.placedItems.length; i += 1) {
            var placedItem = documentRef.placedItems[i];
            var placedBounds = placedItem.geometricBounds;
            var placedFilePath = "";
            try {
                placedFilePath = placedItem.file.fsName;
            } catch (placedFileError) {
                warnings.push("Placed item " + i + " has no accessible linked file path.");
            }
            placedRows.push(
                "{" +
                "\"index\":" + i +
                ",\"name\":" + quote(placedItem.name || "") +
                ",\"file_path\":" + quote(placedFilePath) +
                ",\"bounds_pt\":" + boundsJson(placedBounds) +
                ",\"placement_mm\":{" +
                    "\"x\":" + finiteNumber((placedBounds[0] - artboard[0]) / PT_PER_MM) +
                    ",\"y\":" + finiteNumber((artboard[1] - placedBounds[1]) / PT_PER_MM) +
                    ",\"width\":" + finiteNumber((placedBounds[2] - placedBounds[0]) / PT_PER_MM) +
                    ",\"height\":" + finiteNumber((placedBounds[1] - placedBounds[3]) / PT_PER_MM) +
                "}" +
                "}"
            );
        }

        var warningRows = [];
        for (i = 0; i < warnings.length; i += 1) { warningRows.push(quote(warnings[i])); }

        return "{" +
            "\n  \"stage\": " + quote(stage) + "," +
            "\n  \"source_document\": " + quote(sourcePath) + "," +
            "\n  \"illustrator_version\": " + quote(app.version) + "," +
            "\n  \"active_artboard\": {\"bounds_pt\": " + boundsJson(artboard) +
                ", \"width_pt\": " + finiteNumber(widthPt) +
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
            "\n  \"placed_items\": [\n    " + placedRows.join(",\n    ") + "\n  ]," +
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

    function readTextFile(fileRef) {
        fileRef.encoding = "UTF-8";
        if (!fileRef.open("r")) { throw new Error("Could not read " + fileRef.fsName); }
        var contents = fileRef.read();
        fileRef.close();
        return contents;
    }

    function parseJson(contents) {
        if (typeof JSON !== "undefined" && JSON.parse) { return JSON.parse(contents); }
        // Illustrator's legacy ExtendScript engine may not expose JSON.
        // The companion file is generated locally beside the selected SVG.
        return eval("(" + contents + ")");
    }

    function placeCompanionRasterAtoms(documentRef, svgFile) {
        var placementsFile = new File(
            svgFile.parent.fsName + "/" + svgFile.name.replace(/\.svg$/i, ".placements.json")
        );
        if (!placementsFile.exists) { return 0; }
        var manifest = parseJson(readTextFile(placementsFile));
        if (!manifest.atoms || manifest.atoms.length === 0) {
            throw new Error("Companion placements manifest has no atoms.");
        }
        var artboard = documentRef.artboards[documentRef.artboards.getActiveArtboardIndex()].artboardRect;
        var artboardLeft = artboard[0];
        var artboardTop = artboard[1];
        var i;
        for (i = 0; i < manifest.atoms.length; i += 1) {
            var atom = manifest.atoms[i];
            var atomFile = new File(svgFile.parent.fsName + "/" + atom.href);
            if (!atomFile.exists) { throw new Error("Missing companion raster atom: " + atomFile.fsName); }
            var placed = documentRef.placedItems.add();
            placed.file = atomFile;
            // Assign the semantic ID after setting .file: Illustrator resets
            // the PlacedItem name when the linked file is attached.
            placed.name = atom.id;
            placed.position = [
                artboardLeft + Number(atom.placement_mm.x) * PT_PER_MM,
                artboardTop - Number(atom.placement_mm.y) * PT_PER_MM
            ];
            placed.width = Number(atom.placement_mm.width) * PT_PER_MM;
            placed.height = Number(atom.placement_mm.height) * PT_PER_MM;
            placed.zOrder(ZOrderMethod.SENDTOBACK);
        }
        return manifest.atoms.length;
    }

    var injectedSvgPath = String($.global.__roundtripSvgPath || "");
    $.global.__roundtripSvgPath = null;
    $.global.__roundtripSilent = null;
    var svgFile = injectedSvgPath ? new File(injectedSvgPath) :
        File.openDialog("Choose one SVG for a real AI/PDF roundtrip", "SVG:*.svg");
    if (!svgFile) { return; }
    if (!/\.svg$/i.test(svgFile.name)) {
        stopWithMessage("The selected file is not an SVG.");
        return;
    }
    if (!svgFile.exists) {
        stopWithMessage("The selected SVG does not exist: " + svgFile.fsName);
        return;
    }

    var stem = svgFile.name.replace(/\.svg$/i, "");
    var parent = svgFile.parent;
    var aiFile = new File(parent.fsName + "/" + stem + "_ai_roundtrip_test.ai");
    var pdfFile = new File(parent.fsName + "/" + stem + "_ai_roundtrip_test_editable.pdf");
    var svgAudit = new File(parent.fsName + "/" + stem + "_svg_import_roundtrip_illustrator_audit.json");
    var aiAudit = new File(parent.fsName + "/" + stem + "_ai_roundtrip_test_illustrator_audit.json");
    var pdfAudit = new File(parent.fsName + "/" + stem + "_ai_roundtrip_test_editable_illustrator_audit.json");
    var logFile = new File(parent.fsName + "/" + stem + "_roundtrip_log.txt");
    var outputs = [aiFile, pdfFile, svgAudit, aiAudit, pdfAudit, logFile];
    var outputNames = [];
    var i;
    for (i = 0; i < outputs.length; i += 1) {
        if (outputs[i].exists) {
            stopWithMessage("Roundtrip aborted because an output already exists:\n" + outputs[i].fsName);
            return;
        }
        outputNames.push(outputs[i].fsName);
    }

    var documentRef = null;
    try {
        documentRef = app.open(svgFile);
        placeCompanionRasterAtoms(documentRef, svgFile);
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
        documentRef.close(SaveOptions.SAVECHANGES);
        documentRef = null;

        documentRef = app.open(pdfFile);
        writeNewFile(pdfAudit, collectAudit(documentRef, "editable_pdf_reopen", pdfFile.fsName));
        documentRef.close(SaveOptions.DONOTSAVECHANGES);
        documentRef = null;

        writeNewFile(
            logFile,
            "Illustrator " + app.version + "\n" +
            "Source: " + svgFile.fsName + "\n" +
            "Result: PASS\n" +
            "The editable PDF was closed and reopened before audit.\n" +
            "Outputs:\n" + outputNames.join("\n") + "\n"
        );
        if (!silentMode) {
            alert("Roundtrip PASS.\nAI and editable PDF were closed, reopened, and audited.\n\n" + logFile.fsName);
        }
    } catch (error) {
        if (documentRef) { closeWithoutSaving(documentRef); }
        if (silentMode) { throw error; }
        alert("Roundtrip FAILED:\n" + error.message + "\nLine: " + error.line);
    }
}());
