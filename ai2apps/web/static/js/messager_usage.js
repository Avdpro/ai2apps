(() => {
    const units = [[1e9, 'G'], [1e6, 'M'], [1e3, 'K']];

    window.formatMessagerUsage = function (amount, lowerBound = false) {
        const number = Number(amount);
        const locale = document.documentElement.lang || undefined;
        if (!Number.isFinite(number) || Math.abs(number) < 1e3) {
            return typeof amount === 'number'
                ? amount.toLocaleString(locale)
                : String(amount).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
        }

        const magnitude = Math.abs(number);
        // Promote rounded values at the unit boundary. Round reported lower
        // bounds toward zero so the abbreviation never overstates them.
        const [scale, suffix] = units.find(([scale]) =>
            magnitude >= (lowerBound || scale === 1e3 ? scale : scale - scale / 20_000));
        const value = lowerBound ? Math.trunc(number / (scale / 10)) / 10 : number / scale;
        return value.toLocaleString(locale, {
            useGrouping: false, minimumFractionDigits: 1, maximumFractionDigits: 1,
        }) + suffix;
    };
})();
