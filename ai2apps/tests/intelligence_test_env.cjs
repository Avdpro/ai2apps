// Default-language dependencies for focused functions extracted from the UI.
exports.lt = text => text;
exports.it = (parts, ...values) => parts.reduce((text, part, index) =>
    text + part + (index < values.length ? values[index] : ''), '');
