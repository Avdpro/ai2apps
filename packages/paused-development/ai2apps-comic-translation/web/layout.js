(() => {
    'use strict';
    const FULL = [0, 0, 1, 1];
    const MIN = .004;
    const pixels = ([x, y, right, bottom], width, height) => {
        const left = Math.floor(x * width), top = Math.floor(y * height);
        return [left, top, Math.ceil(right * width) - left, Math.ceil(bottom * height) - top];
    };
    const intersect = (a, b) => [
        Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3]),
    ];
    const area = box => Math.max(0, box[2] - box[0]) * Math.max(0, box[3] - box[1]);
    const union = (a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
    const bounds = ({x, y, w, h}) => [x, y, x + w, y + h];
    const canvas = (width, height) => Object.assign(document.createElement('canvas'), {width, height});
    const png = surface => new Promise((resolve, reject) =>
        surface.toBlob(file => file ? resolve(file) : reject(Error('PNG export failed')), 'image/png'));
    const url = file => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
    const decode = async (file, max = 24_000_000) => {
        const bitmap = await createImageBitmap(file);
        try {
            if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > max) throw Error('Image exceeds 24 megapixels');
            const surface = canvas(bitmap.width, bitmap.height);
            const context = surface.getContext('2d', {alpha: false});
            context.fillStyle = '#fff';
            context.fillRect(0, 0, surface.width, surface.height);
            context.drawImage(bitmap, 0, 0);
            return surface;
        } finally { bitmap.close(); }
    };
    function crop(surface, box, maxEdge = Infinity, parts = null) {
        const [x, y, w, h] = pixels(box, surface.width, surface.height);
        const scale = Math.min(1, maxEdge / Math.max(w, h));
        const result = canvas(Math.max(1, Math.round(w * scale)), Math.max(1, Math.round(h * scale)));
        const context = result.getContext('2d', {alpha: false});
        if (parts) {
            context.fillStyle = '#fff';
            context.fillRect(0, 0, result.width, result.height);
            const sx = result.width / w, sy = result.height / h;
            for (const part of parts) {
                const [px, py, pw, ph] = pixels(part, surface.width, surface.height);
                context.drawImage(surface, px, py, pw, ph, (px - x) * sx, (py - y) * sy, pw * sx, ph * sy);
            }
        } else {
            context.drawImage(surface, x, y, w, h, 0, 0, result.width, result.height);
        }
        return result;
    }
    function layout(context, text, width, height, language, maxSize) {
        const segmenter = new Intl.Segmenter(language, {granularity: 'word'});
        const segments = Array.from(segmenter.segment(text.replace(/\s+/g, ' ')), entry => entry.segment)
            .flatMap(unit => /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(unit) ? [...unit] : [unit]);
        const units = [];
        for (const segment of segments) {
            // Closing punctuation travels with the preceding word or glyph.
            if (units.length && /^[!?.,:;…，。！？、；：）」』】》]+$/u.test(segment)) {
                units[units.length - 1] = units.at(-1) + segment;
            } else units.push(segment);
        }
        let best;
        for (let low = 7, high = Math.min(maxSize, Math.floor(height / 1.15)); low <= high;) {
            const size = Math.floor((low + high) / 2);
            const font = `600 ${size}px system-ui, sans-serif`;
            context.font = font;
            const lines = [];
            let line = '';
            for (const unit of units) {
                if (line && context.measureText(line + unit).width > width) {
                    lines.push(line.trim());
                    line = '';
                }
                line += line ? unit : unit.trimStart();
            }
            if (line.trim()) lines.push(line.trim());
            const lineHeight = size * 1.19;
            if (lines.length * lineHeight <= height && lines.every(value => context.measureText(value).width <= width)) {
                best = {font, lines, lineHeight, size};
                low = size + 1;
            } else high = size - 1;
        }
        return best;
    }
    function fitTranslation(context, region, width, height, language, maxSize = 160) {
        const fit = rotated => {
            const prepared = layout(context, region.translated.trim(), rotated ? height : width,
                rotated ? width : height, language, maxSize);
            return prepared && {...prepared, rotated};
        };
        if (region.orientation === 'rotate') return fit(true);
        const horizontal = fit(false);
        if (region.orientation === 'horizontal' || language !== 'en' || height < width * 1.3) return horizontal;
        const vertical = fit(true);
        return vertical && (!horizontal || vertical.size >= horizontal.size * 1.2) ? vertical : horizontal;
    }
    function background(context, x, y, w, h) {
        const {data} = context.getImageData(x, y, w, h);
        const edge = [];
        const pixel = (i, j) => Array.from(data.subarray((j * w + i) * 4, (j * w + i) * 4 + 3));
        for (let i = 0; i < w; i += Math.max(1, Math.floor(w / 48))) edge.push(pixel(i, 0), pixel(i, h - 1));
        for (let j = 0; j < h; j += Math.max(1, Math.floor(h / 48))) edge.push(pixel(0, j), pixel(w - 1, j));
        const rgb = [0, 1, 2].map(channel => edge.map(sample => sample[channel]).sort((a, b) => a - b)[Math.floor(edge.length / 2)]);
        return edge.filter(sample => sample.every((value, channel) => Math.abs(value - rgb[channel]) <= 26)).length >= edge.length * .89 ? rgb : null;
    }

    function flood(state, width, height, start, from, to, queue) {
        let count = 0;
        const enqueue = index => {
            if (state[index] !== from) return;
            state[index] = to;
            queue[count++] = index;
        };
        enqueue(start);
        let enclosed = true;
        for (let i = 0; i < count; i++) {
            const index = queue[i], x = index % width;
            if (!x || x === width - 1 || index < width || index >= state.length - width) enclosed = false;
            if (x) enqueue(index - 1);
            if (x < width - 1) enqueue(index + 1);
            if (index >= width) enqueue(index - width);
            if (index < state.length - width) enqueue(index + width);
        }
        return enclosed;
    }

    function balloon(context, erase, blockers, nearby = []) {
        const [left, top, right, bottom] = erase.map(bounds).reduce(union);
        const [searchLeft, searchTop, searchRight, searchBottom] =
            nearby.reduce(union, [left, top, right, bottom]);
        const inset = Math.ceil(Math.max(searchRight - searchLeft, searchBottom - searchTop) * .65);
        const x = Math.max(0, searchLeft - inset), y = Math.max(0, searchTop - inset);
        const w = Math.min(context.canvas.width, searchRight + inset) - x;
        const h = Math.min(context.canvas.height, searchBottom + inset) - y;
        if (w * h > 1_000_000) return null;
        const {data} = context.getImageData(x, y, w, h);
        const labels = new Int32Array(w * h);
        const queue = new Int32Array(labels.length);
        for (let i = 0; i < labels.length; i++) {
            if (Math.min(data[i * 4], data[i * 4 + 1], data[i * 4 + 2]) >= 202) labels[i] = -1;
        }
        const rectPixels = ({x: rx, y: ry, w: rw, h: rh}, callback) => {
            for (let dy = ry - y; dy < ry - y + rh; dy++) {
                for (let dx = rx - x; dx < rx - x + rw; dx++) callback(dy * w + dx);
            }
        };
        const closed = new Set();
        let next = 0;
        const coverage = erase.map(rect => {
            const votes = new Map();
            rectPixels(rect, index => {
                if (labels[index] === -1) {
                    const id = ++next;
                    if (flood(labels, w, h, index, -1, id, queue)) closed.add(id);
                }
                const id = labels[index];
                if (closed.has(id)) votes.set(id, (votes.get(id) || 0) + 1);
            });
            return new Set([...votes].filter(([, count]) => count >= rect.w * rect.h * .43).map(([id]) => id));
        });
        const id = [...coverage[0]].find(candidate => coverage.every(votes => votes.has(candidate)));
        if (!id) return null;
        // Only pixels inside this light component and its enclosed ink holes
        // can be changed. A contour connected to the exterior stays intact.
        const mask = Uint8Array.from(labels, value => value === id ? 1 : 0);
        flood(mask, w, h, 0, 0, 2, queue);
        const ink = new Uint8Array(mask.length);
        const tone = [0, 0, 0];
        let samples = 0;
        for (const rect of erase) {
            rectPixels(rect, index => {
                if (mask[index] !== 2) ink[index] = 1;
                if (mask[index] !== 1) return;
                const rgba = index * 4;
                if (Math.min(data[rgba], data[rgba + 1], data[rgba + 2]) < 230) return;
                for (let c = 0; c < 3; c++) tone[c] += data[rgba + c];
                samples++;
            });
        }
        if (!samples) return null;
        const rgb = tone.map(value => Math.round(value / samples));
        const step = Math.max(2, Math.ceil(Math.max(w, h) / 200));
        const columns = Math.floor(w / step), rows = Math.floor(h / step);
        const heights = new Int32Array(columns);
        const choices = new Map();
        const obstructed = new Uint8Array(columns * rows);
        for (const [left, top, right, bottom] of blockers) {
            const start = Math.max(0, Math.floor((left - x) / step));
            const end = Math.min(columns, Math.ceil((right - x) / step));
            if (start >= end) continue;
            for (let row = Math.max(0, Math.floor((top - y) / step)); row < Math.min(rows, Math.ceil((bottom - y) / step)); row++) {
                obstructed.fill(1, row * columns + start, row * columns + end);
            }
        }
        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < columns; col++) {
                let free = !obstructed[row * columns + col];
                const tileX = x + col * step, tileY = y + row * step;
                if (free) rectPixels({x: tileX, y: tileY, w: step, h: step}, index => {
                    if (mask[index] !== 1 && !ink[index]) free = false;
                });
                heights[col] = free ? heights[col] + 1 : 0;
            }
            const stack = [];
            for (let col = 0; col <= columns; col++) {
                const height = heights[col] || 0;
                let start = col;
                while (stack.length && stack.at(-1).height > height) {
                    const last = stack.pop();
                    start = last.start;
                    const rw = (col - start) * step, rh = last.height * step;
                    if (rw < 12 || rh < 12) continue;
                    const rx = x + start * step, ry = y + (row + 1 - last.height) * step;
                    const rect = [rx, ry, rx + rw, ry + rh];
                    if (area(intersect(rect, [left, top, right, bottom])) < rw * rh * .2) continue;
                    const key = Math.round(Math.log2(rw / rh) * 5);
                    if (rw * rh > (choices.get(key)?.size || 0)) {
                        choices.set(key, {size: rw * rh, x: rx, y: ry, w: rw, h: rh, rgb});
                    }
                }
                if (height && (!stack.length || stack.at(-1).height < height)) stack.push({start, height});
            }
        }
        const runs = [];
        for (let row = 0; row < h; row++) {
            for (let col = 0; col < w;) {
                if (!ink[row * w + col]) { col++; continue; }
                const start = col++;
                while (col < w && ink[row * w + col]) col++;
                runs.push([x + start, y + row, col - start]);
            }
        }
        return {choices: [...choices.values()], clear(output) {
            output.fillStyle = `rgb(${rgb.join(',')})`;
            for (const [px, py, length] of runs) output.fillRect(px, py, length, 1);
        }};
    }

    function bestFit(context, region, choices, language) {
        return choices.map(rect => ({...rect,
            prepared: fitTranslation(context, region, rect.w - 4, rect.h - 4, language)}))
            .filter(rect => rect.prepared).sort((a, b) => b.prepared.size - a.prepared.size)[0];
    }
    async function render(page, language) {
        const source = await decode(page.file);
        const [left, top, width, height] = pixels(page.crop || FULL, source.width, source.height);
        const original = canvas(width, height);
        original.getContext('2d', {alpha: false}).drawImage(source, left, top, width, height, 0, 0, width, height);
        source.width = source.height = 0;
        const output = canvas(width, height);
        const context = output.getContext('2d', {alpha: false, willReadFrequently: true});
        context.drawImage(original, 0, 0);
        const patches = [], issues = [];
        const toRect = box => {
            const [x, y, w, h] = pixels(box, page.width, page.height);
            return {x: x - left, y: y - top, w, h};
        };
        const rows = page.regions.map((region, index) => ({region, index, erase: (region.parts || [region.box]).map(toRect)}));
        const valid = ({erase}) => erase.length > 0 && erase.every(({x, y, w, h}) =>
            w >= 8 && h >= 8 && x >= 0 && y >= 0 && x + w <= width && y + h <= height);
        const active = rows.filter(({region}) => region.enabled && region.translated.trim());
        const byId = new Map(active.map(row => [row.region.id, row]));
        const grouped = new Set();
        const used = [];
        // Pixel rounding and OCR padding can leave a narrow seam between boxes.
        const conflicts = (a, b) => {
            const overlap = intersect(a, b);
            if (area(overlap) <= 4) return false;
            return [0, 1].every(axis => overlap[axis + 2] - overlap[axis] >
                Math.min(6, Math.min(a[axis + 2] - a[axis], b[axis + 2] - b[axis]) * .15));
        };

        function place(members) {
            const [{region}] = members;
            const erase = members.flatMap(row => row.erase);
            if (!members.every(valid) || erase.some(rect => used.some(box => conflicts(box, bounds(rect))))) {
                return 'bounds';
            }
            const memberSet = new Set(members);
            const neighboringBoxes = rows.filter(row => !memberSet.has(row) && valid(row))
                .flatMap(row => row.erase.map(bounds));
            const blockers = [...used, ...neighboringBoxes];
            const text = members.map(row => row.region.translated.trim()).join(/^(zh|ja)$/.test(language) ? '' : ' ');
            const combined = {...region, translated: text};
            const orientations = new Set(members.map(row => row.region.orientation).filter(value => value && value !== 'auto'));
            if (orientations.size > 1) return 'text';
            if (orientations.size) combined.orientation = [...orientations][0];
            let interior;
            let fitted;
            if (members.every(row => !row.region.manualBounds)) {
                interior = balloon(context, erase, blockers);
                fitted = interior && bestFit(context, combined, interior.choices, language);
                if (!fitted && members.length === 1) {
                    // Find the full contour using adjacent boxes while erasing only this region.
                    const nearby = neighboringBoxes.filter(box => erase.some(rect => {
                        const source = bounds(rect);
                        return area(intersect(box, source)) > 0 && !conflicts(box, source);
                    }));
                    if (nearby.length) {
                        interior = balloon(context, erase, blockers, nearby);
                        fitted = interior && bestFit(context, combined, interior.choices, language);
                    }
                }
            }
            let clear;
            if (fitted) {
                clear = interior.clear;
            } else {
                if (members.length > 1) return 'text';
                for (const rect of erase) rect.rgb = background(context, rect.x, rect.y, rect.w, rect.h);
                if (erase.some(rect => !rect.rgb)) return 'background';
                const choices = [...erase];
                for (const [i, a] of erase.entries()) {
                    for (const b of erase.slice(i + 1)) {
                        const [x, y, right, bottom] = union(bounds(a), bounds(b));
                        const w = right - x, h = bottom - y;
                        if (blockers.some(box => area(intersect(box, [x, y, right, bottom])) > 0)) continue;
                        const rgb = background(context, x, y, w, h);
                        if (rgb) choices.push({x, y, w, h, rgb});
                    }
                }
                fitted = bestFit(context, region, choices, language);
                if (!fitted) return 'text';
                clear = output => {
                    for (const rect of erase) {
                        output.fillStyle = `rgb(${rect.rgb.join(',')})`;
                        output.fillRect(rect.x, rect.y, rect.w, rect.h);
                    }
                };
            }
            const fittedBounds = bounds(fitted);
            if (patches.some(patch => area(intersect(bounds(patch), fittedBounds)) > 0)) return 'bounds';
            const touched = [...erase.map(bounds), fittedBounds];
            used.push(...touched);
            const reveal = touched.reduce(union).map((value, axis) => value / (axis % 2 ? height : width));
            patches.push({...fitted, clear, reveal});
            return null;
        }

        for (const ids of page.bubbleGroups || []) {
            const members = ids.map(id => byId.get(id));
            if (members.length < 2 || !members.every(row => row && !grouped.has(row))) continue;
            members.forEach(row => grouped.add(row));
            if (!place(members)) continue;
            const firstPatch = patches.length, firstUsed = used.length;
            for (const row of members) {
                const reason = place([row]);
                if (!reason) continue;
                patches.length = firstPatch;
                used.length = firstUsed;
                issues.push({index: row.index, reason});
                break;
            }
            if (patches.length === firstPatch) continue;
            const size = Math.min(...patches.slice(firstPatch).map(patch => patch.prepared.size));
            members.forEach(({region}, index) => {
                const patch = patches[firstPatch + index];
                const orientation = patch.prepared.rotated ? 'rotate' : 'horizontal';
                patch.prepared = fitTranslation(context, {...region, orientation}, patch.w - 4, patch.h - 4, language, size);
            });
        }
        for (const row of active) {
            if (grouped.has(row)) continue;
            const reason = place([row]);
            if (reason) issues.push({index: row.index, reason});
        }
        for (const {region, index} of rows) {
            if (region.enabled && region.source?.trim() && !region.translated.trim()) issues.push({index, reason: 'untranslated'});
        }
        for (const patch of patches) patch.clear(context);
        for (const {x, y, w, h, rgb, prepared} of patches) {
            context.save();
            context.beginPath();
            context.rect(x, y, w, h);
            context.clip();
            context.translate(x + w / 2, y + h / 2);
            if (prepared.rotated) context.rotate(Math.PI / 2);
            context.fillStyle = rgb.reduce((sum, value) => sum + value, 0) > 420 ? '#111' : '#fff';
            context.font = prepared.font;
            context.textAlign = 'center';
            context.textBaseline = 'middle';
            prepared.lines.forEach((line, index) => context.fillText(line, 0,
                (index - (prepared.lines.length - 1) / 2) * prepared.lineHeight));
            context.restore();
        }
        return {original, output, boxes: patches.map(item => item.reveal), issues};
    }
    function orderDialogue(rows, vertical) {
        return [...rows].sort((a, b) => {
            const delta = a.box[1] - b.box[1];
            return Math.abs(delta) > .075 ? delta : vertical ? b.box[0] - a.box[0] : a.box[0] - b.box[0];
        });
    }
    function bubbleCandidates(page, rows) {
        const pairs = [];
        const boxes = rows.map(row => pixels(row.box, page.width, page.height));
        const closeAcross = (a, b, axis) => {
            const cross = 1 - axis;
            const gap = Math.max(a[axis], b[axis]) - Math.min(a[axis] + a[axis + 2], b[axis] + b[axis + 2]);
            const overlap = Math.min(a[cross] + a[cross + 2], b[cross] + b[cross + 2]) - Math.max(a[cross], b[cross]);
            const depth = Math.min(a[cross + 2], b[cross + 2]);
            return overlap >= depth * .4 && gap <= Math.min(a[axis + 2], b[axis + 2], depth) * .4;
        };
        for (let i = 0; i < boxes.length; i++) {
            for (let j = i + 1; j < boxes.length; j++) {
                const shared = page.bubbleLinks.some(link => link.includes(rows[i].id) && link.includes(rows[j].id));
                if (shared || closeAcross(boxes[i], boxes[j], 0) || closeAcross(boxes[i], boxes[j], 1)) {
                    pairs.push([i, j, shared]);
                }
            }
        }
        return pairs.sort((a, b) => Number(b[2]) - Number(a[2])).slice(0, 64);
    }
    window.ComicLayout = {FULL, MIN, area, canvas, crop, decode, intersect, pixels, png, render, url,
        orderDialogue, bubbleCandidates};
})();
