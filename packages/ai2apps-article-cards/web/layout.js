'use strict';

window.ArticleCards = (() => {
  const maxPages = 30;
  const graphemes = new Intl.Segmenter('zh', {granularity: 'grapheme'});
  const words = new Intl.Segmenter('zh', {granularity: 'word'});
  const fontFamily = '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif';
  const stickers = ['', '✨', '🌿', '💡', '🍜', '💛', '😂', '📌', '📚', '✈️', '☕', '💪'];
  const themes = {
    paper: ['奶油手账', '#fff9e9', '#c58b58', '#3c2c24'],
    sage: ['鼠尾草', '#eef4e8', '#73917c', '#243e32'],
    ink: ['夜读', '#222e40', '#8fa6c6', '#f4eddc'],
  };

  function defaults(key) {
    const [name, paper, border, ink] = themes[key];
    return {name, paper, border, ink, font: 44, left: 11, right: 11, top: 10, bottom: 15,
      stickerX: 14, stickerY: 90, numberX: 87, numberY: 91, number: true, stickers: true,
      sliceLeft: 25, sliceRight: 25, sliceTop: 25, sliceBottom: 25, frame: 12, background: '', backgroundMode: 'fixed'};
  }

  function layout(ctx, template, width, height) {
    const x = width * template.left / 100;
    const y = height * template.top / 100;
    const textWidth = width * (100 - template.left - template.right) / 100;
    const textHeight = height * (100 - template.top - template.bottom) / 100;
    const step = Math.round(template.font * 1.55);
    ctx.font = `${template.font}px ${fontFamily}`;
    return {x, y, textWidth, textHeight, step, capacity: Math.floor(textHeight / step)};
  }

  function wrap(ctx, text, width) {
    const lines = [];
    let offset = 0;
    const paragraphs = text.split('\n');
    for (const [index, paragraph] of paragraphs.entries()) {
      const pieces = Array.from(graphemes.segment(paragraph), part => part.index);
      const breaks = new Set(Array.from(words.segment(paragraph), part => part.index));
      pieces.push(paragraph.length);
      let start = 0;
      while (start < pieces.length - 1) {
        let end = start + 1;
        while (end < pieces.length - 1
            && ctx.measureText(paragraph.slice(pieces[start], pieces[end + 1])).width <= width) end++;
        if (end < pieces.length - 1) {
          let boundary = end;
          while (boundary > start + 1 && !breaks.has(pieces[boundary])) boundary--;
          if (breaks.has(pieces[boundary])) end = boundary;
        }
        lines.push({text: paragraph.slice(pieces[start], pieces[end]), end: offset + pieces[end]});
        start = end;
      }
      if (!paragraph.length) lines.push({text: '', end: offset});
      offset += paragraph.length;
      if (index < paragraphs.length - 1) {
        offset++;
        Object.assign(lines.at(-1), {end: offset, paragraphEnd: true});
      }
    }
    return lines;
  }

  function stickerFor(text, index) {
    if (/方法|技巧|建议|tip|how to/i.test(text)) return '💡';
    if (/开心|笑|哈哈|funny/i.test(text)) return '😂';
    if (/做饭|美食|餐厅|菜谱|recipe|dinner/i.test(text)) return '🍜';
    if (/旅行|旅途|出发|travel/i.test(text)) return '✈️';
    if (/读书|阅读|学习|book|study/i.test(text)) return '📚';
    if (/爱|温暖|感谢|love|thank/i.test(text)) return '💛';
    return ['✨', '🌿', '📌', '☕'][index % 4];
  }

  function paginate(ctx, text, template, width, height) {
    const box = layout(ctx, template, width, height);
    const lines = wrap(ctx, text, box.textWidth);
    const pages = [];
    let offset = 0;
    let start = 0;
    while (start < lines.length) {
      let end = Math.min(start + box.capacity, lines.length);
      if (end < lines.length) {
        const earliest = start + Math.ceil(box.capacity * 0.7);
        for (let boundary = end; boundary >= earliest; boundary--) {
          if (lines[boundary - 1].paragraphEnd && lines[boundary - 1].text.trim()) {
            end = boundary;
            break;
          }
        }
      }
      const next = lines[end - 1].end;
      const pageText = text.slice(offset, next);
      if (pageText) pages.push({text: pageText, sticker: stickerFor(pageText, pages.length)});
      if (pages.length > maxPages) throw Error(`排版超过 ${maxPages} 页。请缩小字号、扩大文字区或缩短文章。`);
      start = end;
      offset = next;
    }
    return pages;
  }

  function builtinBackground(template) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 144;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = template.paper;
    ctx.fillRect(0, 0, 144, 144);
    ctx.strokeStyle = template.border;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(14, 14, 116, 116);
    ctx.globalAlpha = .44;
    ctx.strokeRect(18, 18, 108, 108);
    ctx.globalAlpha = 1;
    ctx.fillStyle = template.border;
    for (const x of [15, 129]) {
      for (const y of [15, 129]) {
        ctx.beginPath();
        ctx.moveTo(x, y - 6);
        ctx.lineTo(x + 6, y);
        ctx.lineTo(x, y + 6);
        ctx.lineTo(x - 6, y);
        ctx.closePath();
        ctx.fill();
      }
    }
    return canvas;
  }

  function drawBackground(ctx, template, image, width, height) {
    if (image && template.backgroundMode === 'fixed') {
      drawFullImage(ctx, image, width, height, template.paper);
      return {dx: [], dy: []};
    }
    const source = image || builtinBackground(template);
    const sourceWidth = source.naturalWidth || source.width;
    const sourceHeight = source.naturalHeight || source.height;
    const left = image ? template.sliceLeft : 25;
    const right = image ? template.sliceRight : 25;
    const top = image ? template.sliceTop : 25;
    const bottom = image ? template.sliceBottom : 25;
    const xs = [0, Math.max(1, Math.round(sourceWidth * left / 100)), Math.min(sourceWidth - 1, Math.round(sourceWidth * (100 - right) / 100)), sourceWidth];
    const ys = [0, Math.max(1, Math.round(sourceHeight * top / 100)), Math.min(sourceHeight - 1, Math.round(sourceHeight * (100 - bottom) / 100)), sourceHeight];
    // Preserve the corner proportions by using a common scale on both axes.
    const edge = Math.round(Math.min(width, height) * template.frame / 100);
    const scale = edge / Math.max(xs[1], sourceWidth - xs[2], ys[1], sourceHeight - ys[2]);
    const dx = [0, Math.round(xs[1] * scale), width - Math.round((sourceWidth - xs[2]) * scale), width];
    const dy = [0, Math.round(ys[1] * scale), height - Math.round((sourceHeight - ys[2]) * scale), height];
    ctx.fillStyle = template.paper;
    ctx.fillRect(0, 0, width, height);
    for (let row = 0; row < 3; row++) {
      for (let col = 0; col < 3; col++) {
        ctx.drawImage(source, xs[col], ys[row], xs[col + 1] - xs[col], ys[row + 1] - ys[row],
          dx[col], dy[row], dx[col + 1] - dx[col], dy[row + 1] - dy[row]);
      }
    }
    return {dx, dy};
  }

  function render(canvas, template, image, page, index, total, guides = false) {
    const {width, height} = canvas;
    const ctx = canvas.getContext('2d');
    const {dx, dy} = drawBackground(ctx, template, image, width, height);
    const box = layout(ctx, template, width, height);
    ctx.textBaseline = 'top';
    ctx.textAlign = 'left';
    ctx.fillStyle = template.ink;
    const lines = wrap(ctx, (page?.text || '').replace(/\n$/, ''), box.textWidth);
    const overflow = Math.max(0, lines.length - box.capacity);
    ctx.save();
    ctx.beginPath();
    ctx.rect(box.x, box.y, box.textWidth, box.textHeight);
    ctx.clip();
    for (const [row, line] of lines.slice(0, box.capacity).entries()) {
      ctx.fillText(line.text, box.x, box.y + row * box.step);
    }
    ctx.restore();
    ctx.textBaseline = 'middle';
    if (template.stickers && page?.sticker) {
      ctx.font = `${Math.round(template.font * 1.1)}px ${fontFamily}`;
      ctx.textAlign = 'center';
      ctx.fillText(page.sticker, width * template.stickerX / 100, height * template.stickerY / 100);
    }
    if (template.number && page) {
      ctx.font = `600 ${Math.round(template.font * .52)}px ${fontFamily}`;
      ctx.textAlign = 'right';
      ctx.fillText(`${String(index + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}`,
        width * template.numberX / 100, height * template.numberY / 100);
    }
    if (guides) {
      ctx.strokeStyle = '#e44257';
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 7]);
      ctx.strokeRect(box.x, box.y, box.textWidth, box.textHeight);
      ctx.beginPath();
      for (const x of dx.slice(1, -1)) { ctx.moveTo(x, 0); ctx.lineTo(x, height); }
      for (const y of dy.slice(1, -1)) { ctx.moveTo(0, y); ctx.lineTo(width, y); }
      ctx.stroke();
      ctx.setLineDash([]);
    }
    return overflow;
  }

  function drawFullImage(ctx, image, width, height, paper) {
    const {naturalWidth, naturalHeight} = image;
    const scale = Math.max(width / naturalWidth, height / naturalHeight);
    const w = naturalWidth * scale, h = naturalHeight * scale;
    ctx.fillStyle = paper;
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(image, (width - w) / 2, (height - h) / 2, w, h);
  }

  function renderCover(canvas, template, background, cover, guides = false) {
    const {width, height} = canvas;
    const ctx = canvas.getContext('2d');
    render(canvas, template, background, null, 0, 0, guides && !cover.image);
    if (cover.image) {
      drawFullImage(ctx, cover.image, width, height, template.paper);
      const shade = ctx.createLinearGradient(0, 0, 0, height);
      shade.addColorStop(0, '#0000');
      shade.addColorStop(.5, '#0009');
      shade.addColorStop(1, '#0000');
      ctx.fillStyle = shade;
      ctx.fillRect(0, 0, width, height);
    }
    const box = layout(ctx, template, width, height);
    const title = cover.title.trim();
    const preferredSize = Math.round(Math.min(width * .15, template.font * 2.6));
    let size = preferredSize;
    let lines, step;
    do {
      ctx.font = `750 ${size}px ${fontFamily}`;
      lines = wrap(ctx, title, box.textWidth);
      step = Math.round(size * 1.28);
      const lastLineWidth = ctx.measureText(lines.at(-1).text.trim()).width;
      const shortLastLine = !title.includes('\n') && lines.length > 1
        && lastLineWidth < box.textWidth * .32 && size > preferredSize * .78;
      if (lines.length <= 5 && lines.length * step <= box.textHeight && !shortLastLine) break;
      size -= 2;
    } while (size >= 30);
    if (lines.length > 5 || lines.length * step > box.textHeight) return true;
    ctx.fillStyle = cover.image ? '#fff' : template.ink;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    const center = box.x + box.textWidth / 2;
    const top = box.y + (box.textHeight - (lines.length - 1) * step) / 2;
    for (const [index, line] of lines.entries()) ctx.fillText(line.text.trim(), center, top + index * step);
    return false;
  }

  return {defaults, themes, paginate, render, renderCover, stickerFor, stickers, maxPages};
})();
