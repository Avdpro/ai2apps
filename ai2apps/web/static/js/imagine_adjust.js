(() => {
    'use strict';

    const DEFAULTS = Object.freeze({
        exposure: 0, brilliance: 0, highlights: 0, shadows: 0,
        contrast: 0, brightness: 0, saturation: 0, vibrance: 0,
        blackPoint: 0, colorBalance: 0, warmth: 0, tint: 0,
        sharpness: 0, definition: 0, noiseReduction: 0, vignette: 0,
    });
    const CONTROLS = Object.freeze([
        ['exposure', 'adjustExposure'], ['brilliance', 'adjustBrilliance'],
        ['highlights', 'adjustHighlights'], ['shadows', 'adjustShadows'],
        ['contrast', 'adjustContrast'], ['brightness', 'adjustBrightness'],
        ['saturation', 'adjustSaturation'], ['vibrance', 'adjustVibrance'],
        ['blackPoint', 'adjustBlackPoint', 0], ['colorBalance', 'adjustColorBalance'],
        ['warmth', 'adjustWarmth'], ['tint', 'adjustTint'],
        ['sharpness', 'adjustSharpness', 0], ['definition', 'adjustDefinition', 0],
        ['noiseReduction', 'adjustNoiseReduction', 0], ['vignette', 'adjustVignette', 0],
    ].map(([id, label, min = -100]) => ({ id, label, min, max: 100, step: 1 })));
    const CROP_RATIOS = Object.freeze([
        { value: 'original', label: 'adjustOriginal' },
        { value: '1:1', label: 'OpenAI / Google · 1024×1024 (1:1)', modelPreset: true },
        { value: '3:2', label: 'OpenAI · 1536×1024 (3:2)', modelPreset: true },
        { value: '2:3', label: 'OpenAI · 1024×1536 (2:3)', modelPreset: true },
        { value: '1264:848', label: 'Google · 1264×848', modelPreset: true },
        { value: '848:1264', label: 'Google · 848×1264', modelPreset: true },
        { value: '4:3', label: '4:3' },
        { value: '3:4', label: '3:4' }, { value: '16:9', label: '16:9' },
        { value: '9:16', label: '9:16' },
    ]);

    const clamp = value => Math.max(0, Math.min(255, value));
    const ratioValue = value => {
        if (!value || value === 'original') return 0;
        const [width, height] = value.split(':').map(Number);
        return width > 0 && height > 0 ? width / height : 0;
    };
    function cropRect(width, height, ratio) {
        const target = ratioValue(ratio);
        if (!target) return { x: 0, y: 0, width, height };
        const source = width / height;
        if (source > target) {
            const cropWidth = Math.round(height * target);
            return { x: Math.round((width - cropWidth) / 2), y: 0, width: cropWidth, height };
        }
        const cropHeight = Math.round(width / target);
        return { x: 0, y: Math.round((height - cropHeight) / 2), width, height: cropHeight };
    }
    function applyColor(imageData, values) {
        const data = imageData.data;
        const exposure = 2 ** (Number(values.exposure || 0) / 50);
        const brightness = Number(values.brightness || 0) * 1.1;
        const contrast = Math.max(-0.95, Number(values.contrast || 0) / 100);
        const saturation = 1 + Number(values.saturation || 0) / 100;
        const vibrance = Number(values.vibrance || 0) / 100;
        const brilliance = Number(values.brilliance || 0) / 100;
        const highlights = Number(values.highlights || 0) / 100;
        const shadows = Number(values.shadows || 0) / 100;
        const blackPoint = Math.max(0, Number(values.blackPoint || 0)) * 1.05;
        const balance = Number(values.colorBalance || 0) * 0.45;
        const warmth = Number(values.warmth || 0) * 0.55;
        const tint = Number(values.tint || 0) * 0.35;
        const definition = Number(values.definition || 0) / 100;
        const vignette = Number(values.vignette || 0) / 100;
        const width = imageData.width, height = imageData.height;
        const maxRadius = Math.sqrt(width * width + height * height) / 2;
        for (let offset = 0; offset < data.length; offset += 4) {
            let red = data[offset] * exposure;
            let green = data[offset + 1] * exposure;
            let blue = data[offset + 2] * exposure;
            let luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722;
            const highlightWeight = Math.max(0, (luminance - 128) / 127);
            const shadowWeight = Math.max(0, (128 - luminance) / 128);
            const tonal = highlights * highlightWeight * 72 + shadows * shadowWeight * 72;
            const midtone = (1 - Math.abs(luminance - 128) / 128) * brilliance * 54;
            red += tonal + midtone + brightness;
            green += tonal + midtone + brightness;
            blue += tonal + midtone + brightness;
            const contrastFactor = 1 + contrast + definition * (1 - Math.abs(luminance - 128) / 128) * 0.35;
            red = (red - 128) * contrastFactor + 128;
            green = (green - 128) * contrastFactor + 128;
            blue = (blue - 128) * contrastFactor + 128;
            luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722;
            const currentSaturation = Math.max(red, green, blue) - Math.min(red, green, blue);
            const vibranceFactor = 1 + vibrance * (1 - Math.min(1, currentSaturation / 128));
            const colorFactor = saturation * vibranceFactor;
            red = luminance + (red - luminance) * colorFactor;
            green = luminance + (green - luminance) * colorFactor;
            blue = luminance + (blue - luminance) * colorFactor;
            red += balance + warmth + tint * 0.35;
            green -= tint;
            blue -= balance + warmth - tint * 0.35;
            if (blackPoint) {
                const scale = 255 / Math.max(1, 255 - blackPoint);
                red = (red - blackPoint) * scale;
                green = (green - blackPoint) * scale;
                blue = (blue - blackPoint) * scale;
            }
            if (vignette) {
                const pixel = offset / 4;
                const x = pixel % width, y = Math.floor(pixel / width);
                const distance = Math.sqrt((x - width / 2) ** 2 + (y - height / 2) ** 2) / maxRadius;
                const edge = Math.max(0, (distance - 0.35) / 0.65) ** 2;
                const factor = 1 - vignette * edge * 0.8;
                red *= factor; green *= factor; blue *= factor;
            }
            data[offset] = clamp(red); data[offset + 1] = clamp(green); data[offset + 2] = clamp(blue);
        }
    }
    function sharpen(imageData, amount) {
        const strength = Math.max(0, Number(amount || 0)) / 100;
        if (!strength) return;
        const { width, height, data } = imageData;
        const source = new Uint8ClampedArray(data);
        for (let y = 1; y < height - 1; y += 1) {
            for (let x = 1; x < width - 1; x += 1) {
                const offset = (y * width + x) * 4;
                for (let channel = 0; channel < 3; channel += 1) {
                    const center = source[offset + channel];
                    const neighbors = source[offset - 4 + channel] + source[offset + 4 + channel]
                        + source[offset - width * 4 + channel] + source[offset + width * 4 + channel];
                    data[offset + channel] = clamp(center + (center * 4 - neighbors) * strength * 0.35);
                }
            }
        }
    }
    function render(source, canvas, state, maxEdge = 1400) {
        if (!source || !canvas) return null;
        const crop = cropRect(source.width, source.height, state.cropRatio);
        const quarterTurn = Math.abs(Number(state.rotation || 0) / 90) % 2 === 1;
        const naturalWidth = quarterTurn ? crop.height : crop.width;
        const naturalHeight = quarterTurn ? crop.width : crop.height;
        const scale = maxEdge > 0 ? Math.min(1, maxEdge / Math.max(naturalWidth, naturalHeight)) : 1;
        const outputWidth = Math.max(1, Math.round(naturalWidth * scale));
        const outputHeight = Math.max(1, Math.round(naturalHeight * scale));
        canvas.width = outputWidth; canvas.height = outputHeight;
        const context = canvas.getContext('2d', { willReadFrequently: true });
        context.clearRect(0, 0, outputWidth, outputHeight);
        context.save();
        context.translate(outputWidth / 2, outputHeight / 2);
        context.rotate(Number(state.rotation || 0) * Math.PI / 180);
        context.scale(state.flipX ? -1 : 1, state.flipY ? -1 : 1);
        const blur = Math.max(0, Number(state.values?.noiseReduction || 0)) / 100 * 1.8;
        context.filter = blur ? `blur(${blur}px)` : 'none';
        context.drawImage(source, crop.x, crop.y, crop.width, crop.height, -crop.width * scale / 2, -crop.height * scale / 2, crop.width * scale, crop.height * scale);
        context.restore(); context.filter = 'none';
        const imageData = context.getImageData(0, 0, outputWidth, outputHeight);
        applyColor(imageData, state.values || DEFAULTS);
        sharpen(imageData, state.values?.sharpness);
        context.putImageData(imageData, 0, 0);
        return { width: outputWidth, height: outputHeight, naturalWidth, naturalHeight };
    }

    window.ImagineAdjustEngine = {
        defaults: () => ({ ...DEFAULTS }), controls: CONTROLS, cropRatios: CROP_RATIOS,
        state: () => ({ values: { ...DEFAULTS }, rotation: 0, flipX: false, flipY: false, cropRatio: 'original' }),
        clone: state => JSON.parse(JSON.stringify(state)), render,
    };
})();
