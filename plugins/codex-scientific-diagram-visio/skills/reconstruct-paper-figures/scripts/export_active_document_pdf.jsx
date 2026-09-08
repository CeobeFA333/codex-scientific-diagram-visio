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
        alert("This document has never been saved. Save it once under a new AI filename, then run the exporter.");
        return;
    }

    var baseName = sourceFile.name.replace(/\.[^.]+$/, "");
    var outputFile = new File(sourceFile.parent.fsName + "/" + baseName + "_editable.pdf");
    if (outputFile.exists) {
        alert("Output already exists and will not be overwritten:\n" + outputFile.fsName);
        return;
    }

    var options = new PDFSaveOptions();
    options.compatibility = PDFCompatibility.ACROBAT7;
    options.preserveEditability = true;
    options.generateThumbnails = true;
    options.optimization = true;
    options.viewAfterSaving = false;
    documentRef.saveAs(outputFile, options);
    alert("Editable PDF created:\n" + outputFile.fsName);
}());
