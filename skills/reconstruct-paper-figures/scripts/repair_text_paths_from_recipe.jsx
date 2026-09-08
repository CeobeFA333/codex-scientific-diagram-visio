#target illustrator

/*
Repair SVG text-on-path objects that Illustrator imports as one POINTTEXT frame
per character. The script is intentionally conservative: it mutates nothing
unless the recipe phrase, imported curve, font, fragment count, fragment order,
parent/bounds evidence, and supported alignment all pass preflight.

Adobe Illustrator scripting references:
- TextFrameItems.pathText(): https://ai-scripting.docsforadobe.dev/jsobjref/TextFrameItems/
- TextFrameItem.kind/textPath: https://ai-scripting.docsforadobe.dev/jsobjref/TextFrameItem/
- PathItem.duplicate(): https://ai-scripting.docsforadobe.dev/jsobjref/PathItem/
*/

(function () {
    if (app.documents.length === 0) {
        alert("No active Illustrator document. Open the imported SVG or AI file first.");
        return;
    }

    var documentRef = app.activeDocument;
    var recipeFile = File.openDialog("Select the reconstruction recipe JSON", "JSON:*.json");
    if (!recipeFile) {
        return;
    }

    function fail(message) {
        throw new Error(message);
    }

    function readUtf8(fileRef) {
        fileRef.encoding = "UTF-8";
        if (!fileRef.open("r")) {
            fail("Could not open recipe: " + fileRef.fsName);
        }
        var value = fileRef.read();
        fileRef.close();
        if (value.length && value.charCodeAt(0) === 0xFEFF) {
            value = value.substring(1);
        }
        return value;
    }

    function strictJsonParse(source) {
        var text = String(source);
        var index = 0;

        function error(message) {
            fail("Strict JSON parse error at character " + index + ": " + message);
        }

        function skipWhitespace() {
            while (index < text.length && /[\u0020\u0009\u000A\u000D]/.test(text.charAt(index))) {
                index += 1;
            }
        }

        function parseString() {
            if (text.charAt(index) !== '"') {
                error("expected string");
            }
            index += 1;
            var value = "";
            while (index < text.length) {
                var character = text.charAt(index);
                index += 1;
                if (character === '"') {
                    return value;
                }
                if (character === "\\") {
                    if (index >= text.length) {
                        error("unterminated escape");
                    }
                    var escape = text.charAt(index);
                    index += 1;
                    if (escape === '"' || escape === "\\" || escape === "/") {
                        value += escape;
                    } else if (escape === "b") {
                        value += "\b";
                    } else if (escape === "f") {
                        value += "\f";
                    } else if (escape === "n") {
                        value += "\n";
                    } else if (escape === "r") {
                        value += "\r";
                    } else if (escape === "t") {
                        value += "\t";
                    } else if (escape === "u") {
                        var hexadecimal = text.substr(index, 4);
                        if (!/^[0-9a-fA-F]{4}$/.test(hexadecimal)) {
                            error("invalid Unicode escape");
                        }
                        value += String.fromCharCode(parseInt(hexadecimal, 16));
                        index += 4;
                    } else {
                        error("invalid escape");
                    }
                } else {
                    if (character.charCodeAt(0) < 0x20) {
                        error("unescaped control character");
                    }
                    value += character;
                }
            }
            error("unterminated string");
        }

        function parseNumber() {
            var match = /^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?/.exec(
                text.substring(index)
            );
            if (!match) {
                error("invalid number");
            }
            index += match[0].length;
            var value = Number(match[0]);
            if (!isFinite(value)) {
                error("number is not finite");
            }
            return value;
        }

        function parseLiteral(literal, value) {
            if (text.substr(index, literal.length) !== literal) {
                error("invalid literal");
            }
            index += literal.length;
            return value;
        }

        function parseArray() {
            var result = [];
            index += 1;
            skipWhitespace();
            if (text.charAt(index) === "]") {
                index += 1;
                return result;
            }
            while (index < text.length) {
                result.push(parseValue());
                skipWhitespace();
                if (text.charAt(index) === "]") {
                    index += 1;
                    return result;
                }
                if (text.charAt(index) !== ",") {
                    error("expected comma or closing bracket");
                }
                index += 1;
                skipWhitespace();
            }
            error("unterminated array");
        }

        function parseObject() {
            var result = {};
            index += 1;
            skipWhitespace();
            if (text.charAt(index) === "}") {
                index += 1;
                return result;
            }
            while (index < text.length) {
                var key = parseString();
                skipWhitespace();
                if (text.charAt(index) !== ":") {
                    error("expected colon");
                }
                index += 1;
                if (key === "__proto__" || key === "constructor" || key === "prototype" ||
                        Object.prototype.hasOwnProperty.call(result, key)) {
                    error("duplicate or unsafe object key");
                }
                result[key] = parseValue();
                skipWhitespace();
                if (text.charAt(index) === "}") {
                    index += 1;
                    return result;
                }
                if (text.charAt(index) !== ",") {
                    error("expected comma or closing brace");
                }
                index += 1;
                skipWhitespace();
            }
            error("unterminated object");
        }

        function parseValue() {
            skipWhitespace();
            var character = text.charAt(index);
            if (character === '"') {
                return parseString();
            }
            if (character === "{") {
                return parseObject();
            }
            if (character === "[") {
                return parseArray();
            }
            if (character === "t") {
                return parseLiteral("true", true);
            }
            if (character === "f") {
                return parseLiteral("false", false);
            }
            if (character === "n") {
                return parseLiteral("null", null);
            }
            if (character === "-" || /[0-9]/.test(character)) {
                return parseNumber();
            }
            error("unexpected token");
        }

        var parsed = parseValue();
        skipWhitespace();
        if (index !== text.length) {
            error("trailing content");
        }
        return parsed;
    }

    function parseRecipe(fileRef) {
        try {
            var source = readUtf8(fileRef);
            if (typeof JSON !== "undefined" && typeof JSON.parse === "function") {
                return JSON.parse(source);
            }
            return strictJsonParse(source);
        } catch (error) {
            fail("Invalid recipe JSON: " + error.message);
        }
    }

    function collectTextPathElements(elements, output, parentId) {
        var i;
        for (i = 0; i < elements.length; i += 1) {
            if (elements[i].type === "text_path") {
                output.push({element: elements[i], parentId: parentId});
            }
            if (elements[i].type === "group" && elements[i].children) {
                collectTextPathElements(elements[i].children, output, String(elements[i].id || ""));
            }
        }
    }

    function elementText(element) {
        if (element.text !== undefined) {
            return String(element.text);
        }
        var value = "";
        var runs = element.runs || [];
        var i;
        for (i = 0; i < runs.length; i += 1) {
            value += String(runs[i].text || "");
        }
        return value;
    }

    function reverseString(value) {
        var reversed = "";
        var i;
        for (i = value.length - 1; i >= 0; i -= 1) {
            reversed += value.charAt(i);
        }
        return reversed;
    }

    function lower(value) {
        return String(value || "").toLowerCase();
    }

    function isBold(weight) {
        var value = lower(weight);
        return value === "bold" || Number(value) >= 600;
    }

    function isItalic(style) {
        var value = lower(style);
        return value === "italic" || value === "oblique";
    }

    function resolveFont(family, weight, style) {
        var bold = isBold(weight);
        var italic = isItalic(style);
        var candidates = [];
        if (lower(family) === "times new roman") {
            if (bold && italic) {
                candidates.push("TimesNewRomanPS-BoldItalicMT");
            } else if (bold) {
                candidates.push("TimesNewRomanPS-BoldMT");
            } else if (italic) {
                candidates.push("TimesNewRomanPS-ItalicMT");
            } else {
                candidates.push("TimesNewRomanPSMT");
            }
        }
        candidates.push(String(family));

        var i;
        for (i = 0; i < candidates.length; i += 1) {
            try {
                return app.textFonts.getByName(candidates[i]);
            } catch (candidateError) {
                // Continue to the family/style scan.
            }
        }

        for (i = 0; i < app.textFonts.length; i += 1) {
            var font = app.textFonts[i];
            if (lower(font.family) !== lower(family)) {
                continue;
            }
            var fontStyle = lower(font.style);
            var fontBold = fontStyle.indexOf("bold") >= 0;
            var fontItalic = fontStyle.indexOf("italic") >= 0 || fontStyle.indexOf("oblique") >= 0;
            if (fontBold === bold && fontItalic === italic) {
                return font;
            }
        }
        fail("Required font is not installed: " + family + " (" + weight + ", " + style + ")");
    }

    function rgbFromHex(value) {
        var text = String(value || "#000000");
        var match = /^#([0-9a-fA-F]{6})$/.exec(text);
        if (!match) {
            fail("Illustrator text-path repair currently requires a #RRGGBB fill, got: " + text);
        }
        var color = new RGBColor();
        color.red = parseInt(match[1].substring(0, 2), 16);
        color.green = parseInt(match[1].substring(2, 4), 16);
        color.blue = parseInt(match[1].substring(4, 6), 16);
        return color;
    }

    function rgbMatches(actual, expected) {
        return actual && actual.typename === "RGBColor" &&
            Math.abs(Number(actual.red) - Number(expected.red)) <= 0.5 &&
            Math.abs(Number(actual.green) - Number(expected.green)) <= 0.5 &&
            Math.abs(Number(actual.blue) - Number(expected.blue)) <= 0.5;
    }

    function importedCurveNames(elementId) {
        var svgName = elementId + "__curve";
        return [svgName, svgName.replace(/_/g, " ")];
    }

    function importedObjectNames(elementId) {
        return [String(elementId), String(elementId).replace(/_/g, " ")];
    }

    function parentNameMatches(item, expectedParentId) {
        if (!expectedParentId) {
            return true;
        }
        var names = importedObjectNames(expectedParentId);
        var parentName = String(item.parent.name || "");
        return item.parent.typename === "GroupItem" &&
            (parentName === names[0] || parentName === names[1]);
    }

    function findUniqueCurve(elementId, expectedText, sizePt, expectedParentId) {
        var names = importedCurveNames(elementId);
        var matches = [];
        var i;
        var j;
        for (i = 0; i < documentRef.pathItems.length; i += 1) {
            var itemName = String(documentRef.pathItems[i].name || "");
            for (j = 0; j < names.length; j += 1) {
                if (itemName === names[j]) {
                    matches.push(documentRef.pathItems[i]);
                    break;
                }
            }
        }
        if (matches.length !== 1) {
            fail(
                "Expected exactly one imported curve for " + elementId +
                "; accepted names: " + names.join(" | ") +
                "; found: " + matches.length
            );
        }
        if (matches[0].closed || matches[0].hidden || matches[0].locked ||
                matches[0].filled || matches[0].stroked ||
                matches[0].pathPoints.length < 2 || !isFinite(Number(matches[0].length)) ||
                Number(matches[0].length) <= expectedText.length * sizePt * 0.3) {
            fail(
                "Imported curve is closed, hidden, locked, degenerate, or too short for phrase-level text: " +
                elementId
            );
        }
        var bounds = matches[0].geometricBounds;
        if (!(bounds[2] > bounds[0]) || !(bounds[1] > bounds[3])) {
            fail("Imported text_path curve has empty bounds: " + elementId);
        }
        if (!parentNameMatches(matches[0], expectedParentId)) {
            fail("Imported curve is not inside the recipe parent group: " + expectedParentId);
        }
        return matches[0];
    }

    function findExistingPathText(
        elementId, expectedText, family, weight, style, sizePt, fillColor, expectedParentId
    ) {
        var matches = [];
        var i;
        for (i = 0; i < documentRef.textFrames.length; i += 1) {
            var frame = documentRef.textFrames[i];
            if (String(frame.name || "") === elementId) {
                matches.push(frame);
            }
        }
        if (matches.length > 1) {
            fail("Multiple text frames already use recipe id: " + elementId);
        }
        if (matches.length === 1) {
            var attributes = matches[0].textRange.characterAttributes;
            var bounds = matches[0].geometricBounds;
            if (matches[0].kind !== TextType.PATHTEXT || matches[0].contents !== expectedText ||
                    !fontStyleMatches(attributes.textFont, family, weight, style) ||
                    Math.abs(Number(attributes.size) - sizePt) > 0.05 ||
                    !rgbMatches(attributes.fillColor, fillColor) ||
                    !parentNameMatches(matches[0], expectedParentId) ||
                    !(bounds[2] > bounds[0]) || !(bounds[1] > bounds[3])) {
                fail("Existing named text frame is not the required phrase-level PATHTEXT: " + elementId);
            }
            return matches[0];
        }
        return null;
    }

    function sameParent(first, second) {
        try {
            return first.parent === second.parent || first.parent == second.parent;
        } catch (error) {
            return false;
        }
    }

    function fragmentInDirectAnonymousWrapper(frame, curve) {
        try {
            var wrapper = frame.parent;
            return wrapper.typename === "GroupItem" && String(wrapper.name || "") === "" &&
                (wrapper.parent === curve.parent || wrapper.parent == curve.parent);
        } catch (error) {
            return false;
        }
    }

    function sameContainer(first, second) {
        try {
            return first === second || first == second;
        } catch (error) {
            return false;
        }
    }

    function fragmentSizeMatches(frame, sizePt) {
        try {
            var attributes = frame.textRange.characterAttributes;
            return Math.abs(Number(attributes.size) - sizePt) <= 0.2;
        } catch (error) {
            return false;
        }
    }

    function fragmentBoundsNearCurve(frame, curve, sizePt) {
        var frameBounds = frame.geometricBounds;
        var curveBounds = curve.geometricBounds;
        var margin = Math.max(12, sizePt * 4);
        return frameBounds[0] >= curveBounds[0] - margin &&
            frameBounds[2] <= curveBounds[2] + margin &&
            frameBounds[1] <= curveBounds[1] + margin &&
            frameBounds[3] >= curveBounds[3] - margin;
    }

    function isFragmentCandidate(frame, curve, sizePt) {
        if (frame.kind !== TextType.POINTTEXT || String(frame.name || "") !== "" ||
                frame.hidden || frame.locked || String(frame.contents).length !== 1 ||
                !fragmentSizeMatches(frame, sizePt)) {
            return false;
        }
        return (sameParent(frame, curve) || fragmentInDirectAnonymousWrapper(frame, curve)) &&
            fragmentBoundsNearCurve(frame, curve, sizePt);
    }

    function collectFragments(curve, expectedText, sizePt) {
        var fragments = [];
        var importedText = "";
        var fragmentContainer = null;
        var oneContainer = true;
        var i;
        for (i = 0; i < documentRef.textFrames.length; i += 1) {
            var frame = documentRef.textFrames[i];
            if (isFragmentCandidate(frame, curve, sizePt)) {
                if (fragmentContainer === null) {
                    fragmentContainer = frame.parent;
                } else if (!sameContainer(fragmentContainer, frame.parent)) {
                    oneContainer = false;
                }
                fragments.push(frame);
                importedText += frame.contents;
            }
        }
        return {
            fragments: fragments,
            importedText: importedText,
            exact: oneContainer && fragments.length === expectedText.length &&
                (importedText === expectedText || importedText === reverseString(expectedText))
        };
    }

    function findExactFragments(curve, expectedText, sizePt) {
        var sameParentEvidence = collectFragments(curve, expectedText, sizePt);
        if (sameParentEvidence.fragments.length) {
            if (sameParentEvidence.exact) {
                return sameParentEvidence.fragments;
            }
            fail(
                "Found same-parent POINTTEXT evidence for " + expectedText +
                " but count/order was not an exact phrase match. No wider bounds fallback was attempted."
            );
        }
        fail(
            "Could not prove the exact imported fragment set for " + expectedText +
            ". No objects were changed. Expected unnamed single-character POINTTEXT frames " +
            "whose count/order, font, size, bounds, and one shared container match the recipe curve " +
            "directly or through one direct unnamed wrapper group."
        );
    }

    function fontStyleMatches(font, family, weight, style) {
        if (lower(font.family) !== lower(family)) {
            return false;
        }
        var fontStyle = lower(font.style);
        var fontBold = fontStyle.indexOf("bold") >= 0;
        var fontItalic = fontStyle.indexOf("italic") >= 0 || fontStyle.indexOf("oblique") >= 0;
        return fontBold === isBold(weight) && fontItalic === isItalic(style);
    }

    function fontFromFragments(fragments, family, weight, style, sizePt, fillColor) {
        var font;
        try {
            font = fragments[0].textRange.characterAttributes.textFont;
        } catch (error) {
            fail("Could not read the imported fragment font for " + fragments[0].contents);
        }
        if (!fontStyleMatches(font, family, weight, style)) {
            fail(
                "Imported fragment font does not match recipe family/style: " +
                font.family + " / " + font.style
            );
        }
        var i;
        for (i = 0; i < fragments.length; i += 1) {
            var attributes = fragments[i].textRange.characterAttributes;
            if (attributes.textFont.name !== font.name ||
                    Math.abs(Number(attributes.size) - sizePt) > 0.2 ||
                    !rgbMatches(attributes.fillColor, fillColor)) {
                fail("Imported text_path fragments do not have one consistent font, size, and fill.");
            }
        }
        return font;
    }

    function justificationFor(element) {
        var anchor = String(element.anchor || "middle");
        var offset = Number(element.start_offset_percent === undefined ? 50 : element.start_offset_percent);
        if (anchor === "middle" && Math.abs(offset - 50) < 0.0001) {
            return Justification.CENTER;
        }
        fail(
            "Only anchor=middle with start_offset_percent=50 is currently supported for reliable " +
            "Illustrator repair: " +
            element.id + " (" + anchor + ", " + offset + ")"
        );
    }

    function preflight(element, defaults, expectedParentId) {
        var expectedText = elementText(element);
        if (!element.id || !expectedText) {
            fail("Each text_path requires a non-empty id and phrase.");
        }
        if (element.runs && element.runs.length) {
            fail(
                "Styled runs in text_path are not repaired yet because uniform formatting would lose " +
                "run-level semantics: " + element.id
            );
        }
        var family = String(element.font_family || defaults.font_family || "Times New Roman");
        var sizePt = Number(element.font_size_pt || defaults.font_size_pt || 8.5);
        var weight = String(element.font_weight || "normal");
        var style = String(element.font_style || "normal");
        var fillColor = rgbFromHex(element.fill || defaults.text_fill || "#000000");
        if (!isFinite(sizePt) || sizePt <= 0) {
            fail("Invalid font size for text_path " + element.id);
        }
        resolveFont(family, weight, style);
        var existing = findExistingPathText(
            String(element.id), expectedText, family, weight, style, sizePt, fillColor,
            expectedParentId
        );
        if (existing) {
            return {element: element, alreadyRepaired: true};
        }

        var curve = findUniqueCurve(String(element.id), expectedText, sizePt, expectedParentId);
        var fragments = findExactFragments(curve, expectedText, sizePt);
        var font = fontFromFragments(fragments, family, weight, style, sizePt, fillColor);
        return {
            element: element,
            alreadyRepaired: false,
            text: expectedText,
            expectedParentId: expectedParentId,
            curve: curve,
            fragments: fragments,
            curveGeometry: pathItemGeometry(curve),
            font: font,
            sizePt: sizePt,
            fillColor: fillColor,
            justification: justificationFor(element),
            workPath: null,
            newFrame: null,
            curveBackup: null,
            fragmentBackups: []
        };
    }

    function safeRemove(item) {
        if (!item) {
            return;
        }
        try {
            item.remove();
        } catch (error) {
            // The path may already have been consumed by pathText().
        }
    }

    function discardBackups(plan) {
        var i;
        safeRemove(plan.curveBackup);
        for (i = plan.fragmentBackups.length - 1; i >= 0; i -= 1) {
            safeRemove(plan.fragmentBackups[i]);
        }
        plan.curveBackup = null;
        plan.fragmentBackups = [];
    }

    function removeBackupsStrict(plan) {
        var i;
        if (plan.curveBackup) {
            plan.curveBackup.remove();
        }
        for (i = plan.fragmentBackups.length - 1; i >= 0; i -= 1) {
            plan.fragmentBackups[i].remove();
        }
        plan.curveBackup = null;
        plan.fragmentBackups = [];
    }

    function prepareBackups(plan) {
        plan.curveBackup = plan.curve.duplicate();
        plan.curveBackup.name = String(plan.curve.name || "");
        plan.curveBackup.hidden = true;
        var i;
        for (i = 0; i < plan.fragments.length; i += 1) {
            var backup = plan.fragments[i].duplicate();
            plan.fragmentBackups.push(backup);
            backup.name = String(plan.fragments[i].name || "");
            backup.hidden = true;
        }
    }

    function rollbackCreated(plans) {
        var i;
        for (i = plans.length - 1; i >= 0; i -= 1) {
            safeRemove(plans[i].newFrame);
            safeRemove(plans[i].workPath);
            discardBackups(plans[i]);
        }
    }

    function restoreBackups(plans) {
        var i;
        var j;
        for (i = plans.length - 1; i >= 0; i -= 1) {
            safeRemove(plans[i].newFrame);
            safeRemove(plans[i].workPath);
            safeRemove(plans[i].curve);
            for (j = plans[i].fragments.length - 1; j >= 0; j -= 1) {
                safeRemove(plans[i].fragments[j]);
            }
            if (plans[i].curveBackup) {
                plans[i].curveBackup.hidden = false;
            }
            for (j = 0; j < plans[i].fragmentBackups.length; j += 1) {
                plans[i].fragmentBackups[j].hidden = false;
            }
            plans[i].curveBackup = null;
            plans[i].fragmentBackups = [];
        }
    }

    function textTypeDiagnostic(kind) {
        if (kind === TextType.PATHTEXT) {
            return "PATHTEXT";
        }
        if (kind === TextType.POINTTEXT) {
            return "POINTTEXT";
        }
        if (kind === TextType.AREATEXT) {
            return "AREATEXT";
        }
        return String(kind);
    }

    function colorDiagnostic(color) {
        if (!color || color.typename !== "RGBColor") {
            return color ? String(color.typename) : "<none>";
        }
        return "RGB(" + Number(color.red) + "," + Number(color.green) + "," +
            Number(color.blue) + ")";
    }

    function parentDiagnostic(item) {
        try {
            return String(item.parent.typename || "") + ":" + String(item.parent.name || "");
        } catch (error) {
            return "<unavailable>";
        }
    }

    function boundsDiagnostic(bounds) {
        return "[" + Number(bounds[0]) + "," + Number(bounds[1]) + "," +
            Number(bounds[2]) + "," + Number(bounds[3]) + "]";
    }

    function pointDiagnostic(point) {
        if (!point || point.length < 2) {
            return "null";
        }
        return "[" + Number(point[0]) + "," + Number(point[1]) + "]";
    }

    function pathItemGeometry(pathItem) {
        var pointCount = pathItem.pathPoints.length;
        return {
            bounds: pathItem.geometricBounds,
            closed: Boolean(pathItem.closed),
            pointCount: pointCount,
            startAnchor: pointCount ? pathItem.pathPoints[0].anchor : null,
            endAnchor: pointCount ? pathItem.pathPoints[pointCount - 1].anchor : null
        };
    }

    function textPathGeometry(frame) {
        var textPath = frame.textPath;
        var pointCount = textPath.pathPoints.length;
        return {
            bounds: [
                Number(textPath.left), Number(textPath.top),
                Number(textPath.left) + Number(textPath.width),
                Number(textPath.top) - Number(textPath.height)
            ],
            closed: Boolean(textPath.closed),
            pointCount: pointCount,
            startAnchor: pointCount ? textPath.pathPoints[0].anchor : null,
            endAnchor: pointCount ? textPath.pathPoints[pointCount - 1].anchor : null
        };
    }

    function numbersNear(first, second, tolerance) {
        return isFinite(Number(first)) && isFinite(Number(second)) &&
            Math.abs(Number(first) - Number(second)) <= tolerance;
    }

    function pointsNear(first, second, tolerance) {
        return first !== null && second !== null &&
            numbersNear(first[0], second[0], tolerance) &&
            numbersNear(first[1], second[1], tolerance);
    }

    function boundsNear(first, second, tolerance) {
        return first && second && first.length === 4 && second.length === 4 &&
            numbersNear(first[0], second[0], tolerance) &&
            numbersNear(first[1], second[1], tolerance) &&
            numbersNear(first[2], second[2], tolerance) &&
            numbersNear(first[3], second[3], tolerance);
    }

    function pathGeometryMatches(actual, expected, tolerance) {
        var mismatches = [];
        if (!boundsNear(actual.bounds, expected.bounds, tolerance)) {
            mismatches.push("bounds");
        }
        if (actual.closed !== expected.closed) {
            mismatches.push("closed");
        }
        if (actual.pointCount !== expected.pointCount) {
            mismatches.push("pointCount");
        }
        if (!pointsNear(actual.startAnchor, expected.startAnchor, tolerance)) {
            mismatches.push("startAnchor");
        }
        if (!pointsNear(actual.endAnchor, expected.endAnchor, tolerance)) {
            mismatches.push("endAnchor");
        }
        return {matches: mismatches.length === 0, mismatches: mismatches};
    }

    function pathGeometryDiagnostic(geometry) {
        return "bounds=" + boundsDiagnostic(geometry.bounds) +
            ",closed=" + geometry.closed +
            ",pointCount=" + geometry.pointCount +
            ",startAnchor=" + pointDiagnostic(geometry.startAnchor) +
            ",endAnchor=" + pointDiagnostic(geometry.endAnchor);
    }

    function createPathText(plan) {
        plan.workPath = plan.curve.duplicate();
        plan.workPath.name = String(plan.element.id) + "__pathtext_work";
        plan.newFrame = documentRef.textFrames.pathText(plan.workPath);
        plan.newFrame.contents = plan.text;
        plan.newFrame.name = String(plan.element.id);
        plan.newFrame.textRange.characterAttributes.textFont = plan.font;
        plan.newFrame.textRange.characterAttributes.size = plan.sizePt;
        plan.newFrame.textRange.characterAttributes.fillColor = plan.fillColor;
        plan.newFrame.paragraphs[0].paragraphAttributes.justification = plan.justification;

        if (!sameParent(plan.newFrame, plan.curve)) {
            plan.newFrame.move(plan.curve.parent, ElementPlacement.PLACEATEND);
        }
        redraw();
        var attributes = plan.newFrame.textRange.characterAttributes;
        var actualPathGeometry = textPathGeometry(plan.newFrame);
        var geometryCheck = pathGeometryMatches(actualPathGeometry, plan.curveGeometry, 0.25);
        var failedChecks = [];
        if (plan.newFrame.kind !== TextType.PATHTEXT) {
            failedChecks.push("kind actual=" + textTypeDiagnostic(plan.newFrame.kind) + " expected=PATHTEXT");
        }
        if (plan.newFrame.contents !== plan.text) {
            failedChecks.push(
                "content actualLength=" + plan.newFrame.contents.length +
                " expectedLength=" + plan.text.length
            );
        }
        if (plan.newFrame.name !== plan.element.id) {
            failedChecks.push(
                "name actual=" + String(plan.newFrame.name) + " expected=" + String(plan.element.id)
            );
        }
        if (plan.newFrame.contents.length !== plan.text.length) {
            failedChecks.push(
                "characterCount actual=" + plan.newFrame.contents.length +
                " expected=" + plan.text.length
            );
        }
        if (attributes.textFont.name !== plan.font.name) {
            failedChecks.push(
                "font actual=" + attributes.textFont.name + " expected=" + plan.font.name
            );
        }
        if (Math.abs(Number(attributes.size) - plan.sizePt) > 0.05) {
            failedChecks.push(
                "size actual=" + Number(attributes.size) + " expected=" + plan.sizePt
            );
        }
        if (!rgbMatches(attributes.fillColor, plan.fillColor)) {
            failedChecks.push(
                "fill actual=" + colorDiagnostic(attributes.fillColor) +
                " expected=" + colorDiagnostic(plan.fillColor)
            );
        }
        if (!sameParent(plan.newFrame, plan.curve)) {
            failedChecks.push(
                "parent actual=" + parentDiagnostic(plan.newFrame) +
                " expected=" + parentDiagnostic(plan.curve)
            );
        }
        if (plan.newFrame.paragraphs[0].paragraphAttributes.justification !== Justification.CENTER) {
            failedChecks.push(
                "justification actual=" +
                String(plan.newFrame.paragraphs[0].paragraphAttributes.justification) +
                " expected=CENTER"
            );
        }
        if (!geometryCheck.matches) {
            failedChecks.push(
                "textPathGeometry mismatches=" + geometryCheck.mismatches.join(",") +
                " actual={" + pathGeometryDiagnostic(actualPathGeometry) + "}" +
                " expected={" + pathGeometryDiagnostic(plan.curveGeometry) + "}" +
                " tolerancePt=0.25"
            );
        }
        if (failedChecks.length) {
            fail(
                "Illustrator did not create the required phrase-level PATHTEXT: " +
                plan.element.id + ". Failed checks: " + failedChecks.join("; ")
            );
        }
    }

    function commitRepair(plan) {
        var i;
        for (i = plan.fragments.length - 1; i >= 0; i -= 1) {
            plan.fragments[i].remove();
        }
        plan.curve.remove();
    }

    function validateDocumentCanvas(recipeValue) {
        var canvas = recipeValue.canvas || {};
        var widthPx = Number(canvas.width_px);
        var heightPx = Number(canvas.height_px);
        var widthMm = Number(canvas.print_width_mm);
        if (!(widthPx > 0) || !(heightPx > 0) || !(widthMm > 0)) {
            fail("Recipe canvas width_px, height_px, and print_width_mm must be positive.");
        }
        var artboard = documentRef.artboards[
            documentRef.artboards.getActiveArtboardIndex()
        ].artboardRect;
        var actualWidthPt = artboard[2] - artboard[0];
        var actualHeightPt = artboard[1] - artboard[3];
        var expectedWidthPt = widthMm * 72 / 25.4;
        var expectedHeightPt = expectedWidthPt * heightPx / widthPx;
        if (Math.abs(actualWidthPt - expectedWidthPt) > 0.25 ||
                Math.abs(actualHeightPt - expectedHeightPt) > 0.25) {
            fail(
                "Active artboard does not match recipe canvas. Expected " +
                expectedWidthPt + " x " + expectedHeightPt + " pt; got " +
                actualWidthPt + " x " + actualHeightPt + " pt."
            );
        }
    }

    function ensureDisjointPlans(actionablePlans) {
        var i;
        var j;
        var a;
        var b;
        for (i = 0; i < actionablePlans.length; i += 1) {
            for (j = i + 1; j < actionablePlans.length; j += 1) {
                if (actionablePlans[i].curve === actionablePlans[j].curve ||
                        actionablePlans[i].curve == actionablePlans[j].curve) {
                    fail("Two text_path plans resolved to the same curve.");
                }
                for (a = 0; a < actionablePlans[i].fragments.length; a += 1) {
                    for (b = 0; b < actionablePlans[j].fragments.length; b += 1) {
                        if (actionablePlans[i].fragments[a] === actionablePlans[j].fragments[b] ||
                                actionablePlans[i].fragments[a] == actionablePlans[j].fragments[b]) {
                            fail("Two text_path plans resolved to the same imported text fragment.");
                        }
                    }
                }
            }
        }
    }

    var recipe;
    var plans = [];
    var actionable = [];
    try {
        recipe = parseRecipe(recipeFile);
        validateDocumentCanvas(recipe);
        var textPathElements = [];
        collectTextPathElements(recipe.elements || [], textPathElements, "");
        if (!textPathElements.length) {
            fail("Recipe contains no text_path elements.");
        }

        var defaults = recipe.defaults || {};
        var i;
        for (i = 0; i < textPathElements.length; i += 1) {
            var plan = preflight(
                textPathElements[i].element, defaults, textPathElements[i].parentId
            );
            plans.push(plan);
            if (!plan.alreadyRepaired) {
                actionable.push(plan);
            }
        }
        if (!actionable.length) {
            alert("All recipe text_path objects are already phrase-level PATHTEXT. No changes made.");
            return;
        }
        ensureDisjointPlans(actionable);

        try {
            for (i = 0; i < actionable.length; i += 1) {
                prepareBackups(actionable[i]);
            }
            for (i = 0; i < actionable.length; i += 1) {
                createPathText(actionable[i]);
            }
        } catch (createError) {
            rollbackCreated(actionable);
            fail("Creation failed; new work objects were removed and imported objects were retained. " + createError.message);
        }

        try {
            for (i = 0; i < actionable.length; i += 1) {
                commitRepair(actionable[i]);
            }
        } catch (commitError) {
            restoreBackups(actionable);
            fail(
                "Commit failed; hidden backups were restored and new path text was removed. " +
                commitError.message
            );
        }
        for (i = 0; i < actionable.length; i += 1) {
            try {
                removeBackupsStrict(actionable[i]);
            } catch (cleanupError) {
                fail(
                    "Hidden backup cleanup failed. Do not save this document; Undo or close without " +
                    "saving, then inspect hidden artwork. " + cleanupError.message
                );
            }
        }
        redraw();
        alert(
            "Repaired " + actionable.length + " text_path object(s) as phrase-level PATHTEXT.\n" +
            "The document was not saved. Run audit_active_document.jsx, inspect direction/placement, " +
            "then Save As a new AI file."
        );
    } catch (error) {
        alert("Text-path repair stopped:\n" + error.message);
    }
}());
