#target illustrator

/*
 * Read-only paired AI/PDF audit for a fail-closed staging group.
 * Select an *_ai_roundtrip_test.ai file; the sibling editable PDF is derived.
 * The script refuses to overwrite its JSON output and never saves a document.
 */
(function () {
    var TARGET_GROUP = "blocked-live-overlay-staging";

    function escapeJson(value) {
        return String(value)
            .replace(/\\/g, "\\\\")
            .replace(/\"/g, "\\\"")
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t");
    }

    function quote(value) { return "\"" + escapeJson(value) + "\""; }

    function findNamedGroups(documentRef, name) {
        var matches = [];
        var i;
        for (i = 0; i < documentRef.groupItems.length; i += 1) {
            if (String(documentRef.groupItems[i].name || "") === name) {
                matches.push(documentRef.groupItems[i]);
            }
        }
        return matches;
    }

    function inspectDocument(fileRef, stage) {
        var documentRef = app.open(fileRef);
        try {
            var matches = findNamedGroups(documentRef, TARGET_GROUP);
            if (matches.length !== 1) {
                throw new Error(stage + " expected exactly one " + TARGET_GROUP +
                    " group but found " + matches.length);
            }
            var group = matches[0];
            return {
                stage: stage,
                source: fileRef.fsName,
                opacity: Number(group.opacity),
                hidden: Boolean(group.hidden),
                locked: Boolean(group.locked),
                pageItemCount: Number(group.pageItems.length)
            };
        } finally {
            documentRef.close(SaveOptions.DONOTSAVECHANGES);
        }
    }

    function stageJson(stage) {
        return "{" +
            "\"stage\":" + quote(stage.stage) +
            ",\"source_document\":" + quote(stage.source) +
            ",\"group_name\":" + quote(TARGET_GROUP) +
            ",\"opacity_percent\":" + stage.opacity +
            ",\"hidden\":" + (stage.hidden ? "true" : "false") +
            ",\"locked\":" + (stage.locked ? "true" : "false") +
            ",\"page_item_count\":" + stage.pageItemCount +
            "}";
    }

    var aiFile = File.openDialog("Select an AI roundtrip file for staging-group audit", "AI:*.ai");
    if (!aiFile) { return; }
    if (!/_ai_roundtrip_test\.ai$/i.test(aiFile.name)) {
        alert("Expected a filename ending in _ai_roundtrip_test.ai");
        return;
    }
    var stem = aiFile.name.replace(/_ai_roundtrip_test\.ai$/i, "");
    var pdfFile = new File(aiFile.parent.fsName + "/" + stem + "_ai_roundtrip_test_editable.pdf");
    var outputFile = new File(aiFile.parent.fsName + "/" + stem +
        "_staging_group_roundtrip_illustrator_audit.json");
    if (!pdfFile.exists) {
        alert("Sibling editable PDF is missing:\n" + pdfFile.fsName);
        return;
    }
    if (outputFile.exists) {
        alert("Audit output already exists and will not be overwritten:\n" + outputFile.fsName);
        return;
    }

    try {
        var aiStage = inspectDocument(aiFile, "ai_reopen");
        var pdfStage = inspectDocument(pdfFile, "editable_pdf_reopen");
        var pass = aiStage.opacity === 0 && pdfStage.opacity === 0 &&
            aiStage.pageItemCount > 0 && aiStage.pageItemCount === pdfStage.pageItemCount;
        var report = "{\n" +
            "  \"pass\": " + (pass ? "true" : "false") + ",\n" +
            "  \"illustrator_version\": " + quote(app.version) + ",\n" +
            "  \"required_group\": " + quote(TARGET_GROUP) + ",\n" +
            "  \"acceptance\": {\"opacity_percent\": 0, \"same_nonzero_page_item_count\": true},\n" +
            "  \"stages\": [\n    " + stageJson(aiStage) + ",\n    " + stageJson(pdfStage) + "\n  ]\n" +
            "}\n";
        outputFile.encoding = "UTF-8";
        if (!outputFile.open("w")) { throw new Error("Could not create " + outputFile.fsName); }
        outputFile.write(report);
        outputFile.close();
        alert("Staging-group audit " + (pass ? "PASS" : "FAILED") + ".\n" + outputFile.fsName);
    } catch (error) {
        alert("Staging-group audit FAILED:\n" + error.message + "\nLine: " + error.line);
    }
}());
