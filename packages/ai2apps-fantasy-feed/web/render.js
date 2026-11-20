'use strict';

window.FantasyFeedRenderer = function createRenderer(canvas, tr) {
  const ctx = canvas.getContext('2d');
  const themes = {
    wechat: {bg:'#ededed', bar:'#ededed', input:'#f6f6f6', in:'#fff', out:'#95ec69', accent:'#161616', radius:7},
    whatsapp: {bg:'#efe7db', bar:'#f7f6f2', input:'#f6f3ee', in:'#fff', out:'#d9fdd3', accent:'#12654e', radius:12},
    telegram: {bg:'#dce9ce', bar:'#f7faff', input:'#eff5ef', in:'#fff', out:'#e5ffcb', accent:'#237eae', radius:15},
    imessage: {bg:'#fff', bar:'#f6f6f8', input:'#fff', in:'#e9e9eb', out:'#087af5', accent:'#087af5', radius:24},
  };
  // iPhone WeChat light theme, measured against the chat screenshot.
  const wechatHeaderHeight = 180;
  const wechatFooterHeight = 165;
  const wechatGroupSpacing = {lead:40, firstSeparator:74, separator:80, rowGap:26};
  const wechatText = {fontSize:30, inset:22, lineHeight:39, firstBaseline:48, verticalPadding:36};
  const colors = ['#5676b7','#3c866f','#a26751','#815f9d','#9c546e'];
  const hhmm = value => new Date(value).toISOString().slice(11,16);
  const day = value => new Date(value).toISOString().slice(0,10);
  const graphemes = new Intl.Segmenter(undefined,{granularity:'grapheme'});
  const dateLocale = tr('en-US','zh-CN');
  const calendar = new Intl.DateTimeFormat(dateLocale,{month:'short',day:'numeric',timeZone:'UTC'});
  const calendarWithYear = new Intl.DateTimeFormat(dateLocale,{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'});
  const weekday = new Intl.DateTimeFormat(dateLocale,{weekday:'long',timeZone:'UTC'});

  function wechatTimestamp(time,captureTime) {
    const elapsed = (Date.parse(day(captureTime))-Date.parse(day(time))) / 86400000;
    let label = '';
    if (elapsed === 1) label = tr('Yesterday','昨天');
    else if (elapsed >= 2 && elapsed <= 6) label = weekday.format(time);
    else if (elapsed !== 0) {
      const format = day(time).slice(0,4) === day(captureTime).slice(0,4) ? calendar : calendarWithYear;
      label = format.format(time);
    }
    return [label,hhmm(time)].filter(Boolean).join(' ');
  }
  function path(x,y,w,h,r) {
    ctx.beginPath();
    ctx.roundRect(x,y,w,h,r);
  }
  function box(x,y,w,h,r,color) {
    path(x,y,w,h,r);
    ctx.fillStyle = color;
    ctx.fill();
  }
  function text(value,x,y,{size=24,color='#17191c',bold=false,align='left',max} = {}) {
    ctx.font = (bold ? '600 ' : '') + size + 'px system-ui';
    ctx.fillStyle = color;
    ctx.textAlign = align;
    const valueString = String(value ?? '');
    if (max) ctx.fillText(valueString,x,y,max);
    else ctx.fillText(valueString,x,y);
  }
  function wrap(value,width,fontSize=28) {
    ctx.font = fontSize + 'px system-ui';
    return String(value || '…').split('\n').flatMap(paragraph => {
      let line = '';
      const lines = [];
      for (const {segment} of graphemes.segment(paragraph)) {
        if (line && ctx.measureText(line + segment).width > width) {
          lines.push(line);
          line = '';
        }
        line += segment;
      }
      return [...lines,line];
    });
  }
  function cover(asset,x,y,w,h,r) {
    const image = asset?.image;
    if (!image) return false;
    const scale = Math.max(w/image.width,h/image.height);
    const sw = w/scale, sh = h/scale;
    ctx.save();
    path(x,y,w,h,r);
    ctx.clip();
    ctx.drawImage(image,(image.width-sw)/2,(image.height-sh)/2,sw,sh,x,y,w,h);
    ctx.restore();
    return true;
  }
  function avatar(person,x,y,size,radius) {
    if (cover(person?.avatar,x,y,size,size,radius)) return;
    const name = person?.name.trim() || '?';
    const color = colors[Number(person?.id || 0) % colors.length];
    box(x,y,size,size,radius,color);
    const initial = graphemes.segment(name)[Symbol.iterator]().next().value.segment;
    text(initial,x+size/2,y+size*.66,{size:size*.43,color:'#fff',bold:true,align:'center'});
  }
  function icon(name,x,y,color,size=24) {
    ctx.save();
    ctx.translate(x,y);
    ctx.scale(size/24,size/24);
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1.8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    switch (name) {
      case 'back': ctx.moveTo(14,4); ctx.lineTo(6,12); ctx.lineTo(14,20); break;
      case 'plus': ctx.arc(12,12,11,0,2*Math.PI); ctx.moveTo(6,12); ctx.lineTo(18,12); ctx.moveTo(12,6); ctx.lineTo(12,18); break;
      case 'smile': ctx.arc(12,12,11,0,2*Math.PI); ctx.moveTo(7,13); ctx.quadraticCurveTo(12,20,17,13); ctx.moveTo(8,8); ctx.lineTo(8,8.5); ctx.moveTo(16,8); ctx.lineTo(16,8.5); break;
      case 'mic': ctx.roundRect(9,3,6,12,3); ctx.moveTo(5,11); ctx.arc(12,11,7,Math.PI,0,true); ctx.moveTo(12,18); ctx.lineTo(12,22); break;
      case 'pin': ctx.moveTo(12,23); ctx.bezierCurveTo(0,12,2,2,12,2); ctx.bezierCurveTo(22,2,24,12,12,23); ctx.fill(); ctx.beginPath(); ctx.fillStyle='#fff'; ctx.arc(12,9,2.5,0,2*Math.PI); ctx.fill(); ctx.restore(); return;
      case 'play': ctx.moveTo(8,4); ctx.lineTo(21,12); ctx.lineTo(8,20); ctx.closePath(); ctx.fill(); ctx.restore(); return;
      case 'envelope': ctx.roundRect(3,2,18,20,3); ctx.moveTo(4,7); ctx.quadraticCurveTo(12,15,20,7); break;
      case 'transfer': ctx.moveTo(3,8); ctx.lineTo(21,8); ctx.lineTo(16,3); ctx.moveTo(21,16); ctx.lineTo(3,16); ctx.lineTo(8,21); break;
      default: break;
    }
    ctx.stroke();
    ctx.restore();
  }
  // Paths traced from the light iPhone composer reference, on a 48 px grid.
  function wechatComposerIcon(name,x,y) {
    ctx.save();
    ctx.translate(x,y);
    ctx.strokeStyle = name === 'mic' ? '#777' : '#151515';
    ctx.fillStyle = ctx.strokeStyle;
    ctx.lineWidth = 2.7;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    if (name !== 'mic') {
      ctx.arc(0,0,23,0,2*Math.PI);
      ctx.stroke();
      ctx.beginPath();
    }
    switch (name) {
      case 'voice':
        ctx.moveTo(-10,0);
        ctx.lineTo(-6.5,-3);
        ctx.quadraticCurveTo(-5.3,-3.5,-5.3,-2);
        ctx.lineTo(-5.3,2);
        ctx.quadraticCurveTo(-5.3,3.5,-6.5,3);
        ctx.closePath();
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(-2.3,-6.7);
        ctx.quadraticCurveTo(3.4,0,-2.3,6.7);
        ctx.moveTo(2.3,-11.7);
        ctx.quadraticCurveTo(11.5,0,2.3,11.7);
        break;
      case 'keyboard':
        for (let row=0;row<3;row++) {
          for (let col=0;col<4;col++) ctx.fillRect(-13+col*7,-11+row*7,5,4);
        }
        ctx.fillRect(-7,11,14,3);
        break;
      case 'smile':
        ctx.moveTo(-13.3,2.5);
        ctx.lineTo(13.3,2.5);
        ctx.bezierCurveTo(11.9,9.1,6.6,14.1,0,14.1);
        ctx.bezierCurveTo(-6.6,14.1,-11.9,9.1,-13.3,2.5);
        ctx.closePath();
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(-7,-7,3.3,0,2*Math.PI);
        ctx.moveTo(10.3,-7);
        ctx.arc(7,-7,3.3,0,2*Math.PI);
        ctx.fill();
        ctx.restore();
        return;
      case 'plus':
        ctx.moveTo(-12,0); ctx.lineTo(12,0);
        ctx.moveTo(0,-12); ctx.lineTo(0,12);
        break;
      case 'mic':
        ctx.roundRect(-5.2,-14,10.4,21,5.2);
        ctx.moveTo(-10.5,-0.6);
        ctx.lineTo(-10.5,1.8);
        ctx.bezierCurveTo(-10.5,7.5,-5.8,11.5,0,11.5);
        ctx.bezierCurveTo(5.8,11.5,10.5,7.5,10.5,1.8);
        ctx.lineTo(10.5,-0.6);
        ctx.moveTo(0,11.5); ctx.lineTo(0,15);
        break;
    }
    ctx.stroke();
    ctx.restore();
  }
  function footerLabel(scene,w,baseline) {
    const label = scene.footerText ?? tr('SIMULATED CHAT','虚构对话');
    if (label) text(label,w/2,baseline,{size:16,color:'#595f64',align:'center',max:w-32});
  }
  function wechatComposer(scene,w,y,h) {
    const centerY = y+51;
    const voiceMode = scene.composerMode === 'voice';
    const fieldLeft = 88;
    const fieldRight = w-161;
    box(fieldLeft,y+15,fieldRight-fieldLeft,73,8,'#fff');
    wechatComposerIcon(voiceMode?'keyboard':'voice',44,centerY);
    wechatComposerIcon('smile',w-118,centerY);
    wechatComposerIcon('plus',w-44,centerY);
    if (voiceMode) {
      text(tr('Hold to Talk','按住 说话'),(fieldLeft+fieldRight)/2,centerY+11,
        {size:30,bold:true,align:'center'});
    } else {
      wechatComposerIcon('mic',fieldRight-41.2,centerY);
    }
    footerLabel(scene,w,h-14);
  }
  function mapPreview(item,x,y,w,h,r) {
    if (cover(item.map,x,y,w,h,r)) return;
    box(x,y,w,h,r,'#e7eee0');
    ctx.save();
    path(x,y,w,h,r);
    ctx.clip();
    box(x+w*.65,y+4,w*.25,h*.47,12,'#c6e0bc');
    ctx.strokeStyle = '#c9e1ee';
    ctx.lineWidth = 23;
    ctx.beginPath();
    ctx.moveTo(x+w*.78,y-12);
    ctx.quadraticCurveTo(x+w*.55,y+h*.55,x+w*.94,y+h+10);
    ctx.stroke();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 7;
    for (let i=-1;i<6;i++) {
      ctx.beginPath();
      ctx.moveTo(x+i*w*.25,y);
      ctx.lineTo(x+(i+.5)*w*.25,y+h);
      ctx.moveTo(x,y+i*34);
      ctx.lineTo(x+w,y+i*34-20);
      ctx.stroke();
    }
    icon('pin',x+w/2-16,y+h/2-20,'#dc4c4d',32);
    text(tr('Illustrative map','示意地图'),x+8,y+h-8,{size:13,color:'#46544c'});
    ctx.restore();
  }
  function isSingleEmoji(value) {
    const text = String(value || '').trim();
    if (!text || [...graphemes.segment(text)].length !== 1) return false;
    return /^(?:\p{Emoji_Presentation}|\p{Extended_Pictographic}(?=\uFE0F|\u200D)|[#*0-9]\uFE0F?\u20E3)/u.test(text)
      && !text.includes('\uFE0E');
  }
  function measure(item,themeId,limit) {
    const hasTime = themeId === 'whatsapp' || themeId === 'telegram';
    const footer = hasTime ? 26 : 0;
    if (item.kind === 'voice') {
      const seconds = Math.max(1,Math.min(60,Number(item.voiceSeconds) || 1));
      const width = seconds <= 4 ? 171+(seconds-3)*16 :
        seconds <= 16 ? 187+(seconds-4)*109/12 : 296+(seconds-16)*1.9;
      const transcript = item.transcript?.trim();
      const transcriptWidth = Math.min(limit,492);
      const lines = transcript ? wrap(transcript,transcriptWidth-2*wechatText.inset,wechatText.fontSize) : [];
      const card = lines.length ? {
        lines, w:Math.min(transcriptWidth,Math.max(...lines.map(line=>ctx.measureText(line).width))+2*wechatText.inset),
        h:lines.length*wechatText.lineHeight+wechatText.verticalPadding,
      } : null;
      return {w:Math.min(limit,Math.round(width)),h:75+footer,seconds,card};
    }
    if (item.kind === 'call') {
      const label = tr('Call duration','通话时长')+' '+(item.callDuration || '00:00');
      ctx.font = '600 30px system-ui';
      return {w:Math.min(limit,Math.round(ctx.measureText(label).width+115)),h:75+footer,label};
    }
    if (item.kind === 'text') {
      if (themeId === 'wechat' && isSingleEmoji(item.text)) {
        return {w:82,h:75,emoji:item.text.trim()};
      }
      const metrics = themeId === 'wechat' ? wechatText :
        {fontSize:28, inset:16, lineHeight:36, firstBaseline:34, verticalPadding:22};
      const padding = 2*metrics.inset;
      const lines = wrap(item.text,limit-padding,metrics.fontSize);
      const width = Math.max(hasTime ? 100 : 56,...lines.map(line => ctx.measureText(line).width+padding));
      return {lines,w:width,h:lines.length*metrics.lineHeight+metrics.verticalPadding+footer,metrics};
    }
    if (item.kind === 'image' || item.kind === 'video') {
      const asset = item[item.kind]?.image;
      const wechatPhoto = themeId === 'wechat' && item.kind === 'image';
      const scale = asset ? Math.min((wechatPhoto?360:340)/asset.width,
        (wechatPhoto?360:245)/asset.height,limit/asset.width,wechatPhoto?1.22:Infinity) : 1;
      const lines = item.caption ? wrap(item.caption,Math.min(340,limit)-32).slice(0,3) : [];
      const imageW = asset ? Math.max(60,asset.width*scale) : 220;
      const imageH = asset ? Math.max(48,asset.height*scale) : 110;
      const w = Math.max(lines.length ?  Math.min(340,limit) : 0,hasTime ? 100 : 0,imageW);
      return {lines,w,h:imageH + (lines.length ? lines.length*32+14 : 0)+footer,imageW,imageH};
    }
    if (item.kind === 'link' && themeId === 'wechat') {
      const w = Math.min(448,limit);
      const title = wrap(item.title || item.domain || tr('Web link','网页链接'),w-36,30).slice(0,2);
      const lines = item.summary ? wrap(item.summary,w-(item.cover?146:36),25).slice(0,3) : [];
      const bodyHeight = Math.max(lines.length*36,item.cover?100:0);
      return {w,h:48+title.length*45+bodyHeight+25,title,lines};
    }
    if (item.kind === 'link') {
      const imageH = item.cover && themeId !== 'wechat' ? 104 : 0;
      const lines = item.summary ? wrap(item.summary,Math.min(370,limit)-(item.cover && themeId === 'wechat' ? 106 : 32)).slice(0,2) : [];
      return {lines,w:Math.min(370,limit),h:imageH+82+lines.length*28+footer,imageH};
    }
    const w = Math.min(350,limit);
    const heights = {location:174,contact:100,transfer:112,envelope:112};
    return {w,h:heights[item.kind]+footer};
  }
  function duration(seconds) {
    const value = Math.floor(seconds || 0);
    return Math.floor(value/60) + ':' + String(value%60).padStart(2,'0');
  }
  function paintBubble(item,layout,x,y,scene,theme) {
    const {w,h,lines} = layout;
    const base = item.own ? theme.out : theme.in;
    const bubble = ['text','voice','call'].includes(item.kind);
    const ink = scene.theme === 'imessage' && item.own && bubble ? '#fff' : '#17191c';
    const money = item.kind === 'transfer' || item.kind === 'envelope';
    const wechatPay = money && scene.theme === 'wechat';
    const applePay = item.kind === 'transfer' && scene.theme === 'imessage' && item.currency === 'USD';
    const unsupported = (item.kind === 'envelope' && scene.theme !== 'wechat') ||
      (item.kind === 'transfer' && (scene.theme === 'telegram' ||
        (scene.theme === 'imessage' && !applePay) ||
        (scene.theme === 'whatsapp' && !['BRL','INR'].includes(item.currency))));
    const media = item.kind === 'image' || item.kind === 'video';
    const plainMedia = media && scene.theme === 'wechat' && !item.caption;
    const wechatLink = scene.theme === 'wechat' && item.kind === 'link';
    const fill = wechatLink ? '#fff' : wechatPay ? (item.state === 'sent' ? '#fa9f43' : '#edb88d') :
      applePay ? '#25262a' : scene.theme === 'imessage' && !bubble ? '#f0f0f3' : base;
    if (!plainMedia) {
      box(x,y,w,h,theme.radius,fill);
      if (bubble || wechatPay || wechatLink) {
        const edge = item.own ? x+w : x;
        const side = item.own ? 1 : -1;
        ctx.fillStyle = fill;
        ctx.beginPath();
        if (scene.theme === 'wechat' && (bubble || wechatLink)) {
          ctx.moveTo(edge-side*2,y+26);
          ctx.quadraticCurveTo(edge+side*2,y+30,edge+side*8,y+34);
          ctx.quadraticCurveTo(edge+side*11,y+36,edge+side*8,y+38);
          ctx.quadraticCurveTo(edge+side*2,y+42,edge-side*2,y+46);
        } else {
          const tail = scene.theme === 'imessage' ? y+h-17 : y+10;
          ctx.moveTo(edge-side*3,tail);
          ctx.lineTo(edge+side*9,tail+(scene.theme === 'imessage' ? 16 : 8));
          ctx.lineTo(edge-side*3,tail+17);
        }
        ctx.fill();
      }
    }
    switch (item.kind) {
      case 'voice': {
        const centerY = y+37.5;
        const iconX = item.own ? x+w-54 : x+54;
        ctx.save();
        ctx.translate(iconX,centerY);
        ctx.scale(item.own ? 1 : -1,1);
        ctx.strokeStyle = ink;
        ctx.lineWidth = 3.2;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(5,-12);
        ctx.quadraticCurveTo(-3,0,5,12);
        ctx.moveTo(11,-8);
        ctx.quadraticCurveTo(5,0,11,8);
        ctx.moveTo(17,-4);
        ctx.quadraticCurveTo(13,0,17,4);
        ctx.stroke();
        ctx.restore();
        text(layout.seconds+'″',item.own ? x+w-73 : x+73,y+46,
          {size:25,bold:true,color:ink,align:item.own?'right':'left'});
        break;
      }
      case 'call': {
        const iconX = item.own ? x+w-64 : x+22;
        const centerY = y+37;
        ctx.save();
        ctx.translate(iconX,centerY);
        ctx.strokeStyle = ink;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(0,3);
        ctx.bezierCurveTo(0,-12,40,-12,40,3);
        ctx.quadraticCurveTo(40,9,32,6);
        ctx.lineTo(28,0);
        ctx.quadraticCurveTo(20,-5,12,0);
        ctx.lineTo(8,6);
        ctx.quadraticCurveTo(0,9,0,3);
        ctx.stroke();
        ctx.restore();
        text(layout.label,item.own?x+22:x+81,y+48,{size:30,bold:true,color:ink,max:w-101});
        break;
      }
      case 'text': {
        if (layout.emoji) {
          ctx.font = '36px system-ui';
          const {actualBoundingBoxAscent,actualBoundingBoxDescent} = ctx.measureText(layout.emoji);
          const baseline = y+h/2+(actualBoundingBoxAscent-actualBoundingBoxDescent)/2;
          text(layout.emoji,x+w/2,baseline,{size:36,align:'center'});
          break;
        }
        const {inset,firstBaseline,lineHeight,fontSize} = layout.metrics;
        lines.forEach((line,i) => text(line,x+inset,y+firstBaseline+i*lineHeight,{size:fontSize,color:ink}));
        break;
      }
      case 'image':
      case 'video': {
        const inset = plainMedia ? 0 : 3;
        const height = layout.imageH-inset;
        const imageW = layout.imageW-2*inset;
        const imageX = item.own ? x+w-imageW-inset : x+inset;
        if (!cover(item[item.kind],imageX,y+inset,imageW,height,theme.radius))
          box(imageX,y+inset,imageW,height,theme.radius,'#d8e0e8');
        if (item.kind === 'video') {
          box(imageX+imageW/2-21,y+height/2-20,42,42,21,'#0009');
          icon('play',imageX+imageW/2-11,y+height/2-10,'#fff',22);
          box(imageX+imageW-60,y+height-26,54,21,6,'#0009');
          text(duration(item.video?.duration),imageX+imageW-11,y+height-10,{size:15,color:'#fff',align:'right'});
        }
        lines.forEach((line,i) => text(line,x+14,y+layout.imageH+28+i*32,{size:23,max:w-28}));
        break;
      }
      case 'link': {
        if (wechatLink) {
          layout.title.forEach((line,i) => text(line,x+18,y+47+i*45,{size:30,bold:true,max:w-36}));
          const body = y+16+layout.title.length*45;
          if (item.cover) cover(item.cover,x+w-114,body,92,100,4);
          lines.forEach((line,i) => text(line,x+18,body+29+i*36,{size:25,color:'#626669',max:w-(item.cover?146:36)}));
          text(item.source?.trim() || item.domain || '',x+18,y+h-19,{size:21,color:'#626669',max:w-36});
          break;
        }
        const left = scene.theme === 'telegram' ? 20 : 14;
        if (layout.imageH) cover(item.cover,x+4,y+4,w-8,layout.imageH-4,theme.radius);
        const top = y+layout.imageH;
        if (scene.theme === 'telegram') box(x+7,top+11,4,h-layout.imageH-43,2,theme.accent);
        text(item.title || item.domain || tr('Web link','网页链接'),x+left,top+33,{size:25,bold:true,max:w-left-12});
        lines.forEach((line,i) => text(line,x+left,top+60+i*28,{size:19,color:'#56616a',max:w-left-12}));
        text(item.domain || 'https://…',x+left,top+68+lines.length*28,{size:17,color:'#53606b',max:w-left-12});
        break;
      }
      case 'location':
        if (scene.theme === 'wechat') {
          text(item.place || tr('Location','位置'),x+14,y+30,{size:24,bold:true,max:w-28});
          text(item.address,x+14,y+54,{size:18,color:'#59646b',max:w-28});
          mapPreview(item,x+4,y+65,w-8,104,theme.radius);
        } else {
          mapPreview(item,x+4,y+4,w-8,104,theme.radius);
          text(item.place || tr('Location','位置'),x+14,y+136,{size:24,bold:true,max:w-28});
          text(item.address,x+14,y+160,{size:18,color:'#59646b',max:w-28});
        }
        break;
      case 'contact':
        avatar({id:0,name:item.contact || '?',avatar:item.avatar},x+13,y+12,54,scene.theme === 'wechat' ? 6 : 27);
        text(item.contact || tr('Contact','联系人'),x+80,y+37,{size:24,bold:true,max:w-94});
        text(item.handle,x+80,y+60,{size:18,color:'#53616a',max:w-94});
        box(x+12,y+73,w-24,1,0,'#89919933');
        text(tr('Contact card','个人名片'),x+13,y+94,{size:17,color:theme.accent});
        break;
      case 'transfer':
      case 'envelope': {
        const envelope = item.kind === 'envelope';
        const light = wechatPay || applePay;
        const label = unsupported ? (envelope ? tr('Fictional red envelope','虚构红包') : tr('Fictional transfer','虚构转账'))
          : envelope ? tr('WeChat red envelope','微信红包')
          : applePay ? 'Apple Cash'
          : tr('Transfer','转账');
        const state = item.state === 'received' ? (envelope ? tr('Opened','已领取') : tr('Received','已收款'))
          : item.state === 'expired' ? (envelope ? tr('Expired','已过期') : tr('Returned','已退回'))
          : envelope ? tr('Unopened','待领取') : tr('Pending','待收款');
        const amount = item.amount ? new Intl.NumberFormat(tr('en-US','zh-CN'),{
          style:'currency',currency:item.currency || 'CNY',currencyDisplay:'narrowSymbol',
        }).format(Number(item.amount)) : '';
        const showAmount = !envelope || unsupported;
        const heading = showAmount && amount ? amount : item.note || (envelope ? tr('Best wishes','恭喜发财，大吉大利') : label);
        const fg = light ? '#fff' : '#263c36';
        icon(envelope?'envelope':'transfer',x+15,y+18,fg,32);
        text(heading,x+60,y+33,{size:25,bold:true,color:fg,max:w-75});
        text((showAmount && item.note ? item.note+' · ' : '')+state,x+60,y+59,{size:18,color:fg,max:w-75});
        box(x+10,y+75,w-20,1,0,light?'#ffffff65':'#89919955');
        text(label,x+14,y+100,{size:17,color:fg,max:w-28});
        break;
      }
      default: break;
    }
    if (scene.theme === 'whatsapp' || scene.theme === 'telegram') {
      const light = wechatPay || applePay;
      text(hhmm(item.time),x+w-(item.own?35:10),y+h-8,{align:'right',size:16,color:light?'#fff':'#546762'});
      if (item.own) text('✓✓',x+w-10,y+h-8,{align:'right',size:16,color:'#176e99'});
    }
  }
  function timeline(scene,count,limit) {
    const result = [];
    let lastTime, lastDay, lastMarker;
    const perBubble = scene.theme === 'whatsapp' || scene.theme === 'telegram';
    const groupGap = scene.theme === 'wechat' ? 5*60*1000 : 60*60*1000;
    for (const item of scene.messages.slice(0,count)) {
      const date = day(item.time);
      const dayChanged = lastDay !== date;
      if (dayChanged || (!perBubble && item.time-(scene.theme === 'wechat' ? lastMarker : lastTime) >= groupGap)) {
        const dateLabel = date === day(scene.start) && !perBubble ? '' : calendar.format(item.time);
        const label = scene.theme === 'wechat'
          ? wechatTimestamp(item.time,scene.captureTime ?? scene.start)
          : perBubble ? dateLabel : [dateLabel,hhmm(item.time)].filter(Boolean).join('  ');
        const group = scene.theme === 'wechat' && scene.group;
        const first = result.length === 0;
        const height = group ? (first ? wechatGroupSpacing.firstSeparator : wechatGroupSpacing.separator)
          : scene.theme === 'wechat' ? 57 : 44;
        result.push({label,height,baseline:group ? (first ? 36 : 44) : scene.theme === 'wechat' ? 37 : 27});
        lastMarker = item.time;
      }
      const showName = scene.group && !item.own;
      const layout = measure(item,scene.theme,limit);
      const nameSpace = showName ? (scene.theme === 'wechat' ? 29 : 27) : 0;
      const rowGap = scene.theme === 'wechat' ? (scene.group ? wechatGroupSpacing.rowGap : 31) : 18;
      const bubbleHeight = layout.h + (layout.card ? 7+layout.card.h : 0);
      const height = Math.max(bubbleHeight+nameSpace,scene.theme === 'wechat' ? 75 : 64)+rowGap;
      result.push({item,layout,nameSpace,height});
      lastDay = date;
      lastTime = item.time;
    }
    return result;
  }
  function statusWifi(x,y,size) {
    ctx.save();
    ctx.translate(x,y);
    ctx.scale(size/32,size/32);
    ctx.strokeStyle = '#111';
    ctx.fillStyle = '#111';
    ctx.lineWidth = 4.6;
    ctx.lineCap = 'round';
    for (const radius of [19,12]) {
      ctx.beginPath();
      ctx.arc(0,11,radius,Math.PI*1.27,Math.PI*1.73);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(0,11,3.8,0,2*Math.PI);
    ctx.fill();
    ctx.restore();
  }
  function iosWifi(x,y) {
    ctx.save();
    ctx.translate(x,y);
    ctx.fillStyle = '#111';
    ctx.strokeStyle = '#111';
    ctx.lineWidth = 5.4;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(-14,0);
    ctx.quadraticCurveTo(0,-13.5,14,0);
    ctx.moveTo(-8.1,6.6);
    ctx.quadraticCurveTo(0,-1.2,8.1,6.6);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-4.3,10);
    ctx.quadraticCurveTo(0,6.5,4.3,10);
    ctx.quadraticCurveTo(5.1,10.8,4.2,11.8);
    ctx.lineTo(1.1,14.8);
    ctx.quadraticCurveTo(0,16,-1.1,14.8);
    ctx.lineTo(-4.2,11.8);
    ctx.quadraticCurveTo(-5.1,10.8,-4.3,10);
    ctx.fill();
    ctx.restore();
  }
  function iosSilent(x,y,background) {
    ctx.save();
    ctx.translate(x,y);
    ctx.fillStyle = '#111';
    ctx.beginPath();
    ctx.moveTo(-10,7);
    ctx.quadraticCurveTo(-7,3,-7,-3);
    ctx.bezierCurveTo(-7,-13,7.5,-13,7.5,-3);
    ctx.quadraticCurveTo(7.5,3,11,7);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0,9,3.6,0,Math.PI);
    ctx.fill();
    ctx.lineCap = 'round';
    ctx.strokeStyle = background;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(-10.2,-10.5);
    ctx.lineTo(12,12.4);
    ctx.stroke();
    ctx.strokeStyle = '#111';
    ctx.lineWidth = 2.4;
    ctx.stroke();
    ctx.restore();
  }
  function statusBar(scene,w,fallbackClock,background) {
    const clock = scene.clock || fallbackClock;
    const battery = Math.min(100,Math.max(0,Math.round(scene.battery ?? 60)));
    if (scene.statusOS === 'samsung') {
      text(clock,32,62,{size:27,bold:true,color:'#111'});
      statusWifi(w-135,49,27);
      ctx.fillStyle = '#111';
      ctx.beginPath();
      ctx.moveTo(w-119,63);
      ctx.lineTo(w-96,40);
      ctx.lineTo(w-96,63);
      ctx.closePath();
      ctx.fill();
      box(w-85,39,53,25,12.5,'#333');
      text(String(battery),w-58.5,58,{size:19,bold:true,align:'center',color:'#fff'});
      return;
    }
    const clockX = 71;
    text(clock,clockX,65,{size:32,bold:true,color:'#111'});
    iosSilent(clockX+ctx.measureText(clock).width+24,53,background);
    for (let i=0;i<4;i++) box(w-205+9*i,65-(10+i*5),6,10+i*5,2.6,i<2?'#111':'#a8a8a8');
    iosWifi(w-140,49.5);
    const batteryX = w-111;
    box(batteryX,42,46,23,7,'#b4b4b4');
    if (battery > 0) {
      ctx.save();
      path(batteryX,42,46,23,7);
      ctx.clip();
      box(batteryX,42,46*battery/100,23,0,'#111');
      ctx.restore();
    }
    box(batteryX+47,49,3,9,1.5,'#a4a4a4');
  }
  function wechatHeaderButtons(w) {
    ctx.save();
    ctx.strokeStyle = '#191919';
    ctx.fillStyle = '#191919';
    ctx.lineWidth = 2.8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(45,125);
    ctx.lineTo(32,139);
    ctx.lineTo(45,153);
    ctx.stroke();
    for (const offset of [65,52,39]) {
      ctx.beginPath();
      ctx.arc(w-offset,139,2.9,0,2*Math.PI);
      ctx.fill();
    }
    ctx.restore();
  }
  function bars(scene,count,theme,w,h) {
    const time = count ? scene.messages[count-1].time : scene.start;
    const wechat = scene.theme === 'wechat';
    const imessage = scene.theme === 'imessage';
    const barHeight = wechat ? wechatHeaderHeight : 130;
    box(0,0,w,barHeight,0,theme.bar);
    statusBar(scene,w,hhmm(time),theme.bar);
    if (wechat) wechatHeaderButtons(w);
    else icon('back',22,105,theme.accent,26);
    const peer = scene.people[1] || scene.people[0];
    if (!wechat && !imessage) avatar(peer,62,77,44,22);
    const title = wechat && scene.group ? scene.title+' ('+scene.people.length+')' : scene.title;
    if (imessage) avatar(peer,w/2-18,62,36,18);
    const centered = wechat || imessage;
    text(title,centered?w/2:118,wechat?151:imessage?120:107,
      {size:imessage?20:wechat?29:28,bold:true,align:centered?'center':'left',max:w-(centered?145:200)});
    if (!wechat) text('•••',w-36,103,{size:22,align:'center'});
    box(0,barHeight-1,w,1,0,'#0000000e');
    const footer = wechat ? wechatFooterHeight : 91;
    box(0,h-footer,w,footer,0,theme.input);
    box(0,h-footer,w,1,0,'#0000000e');
    if (wechat) {
      wechatComposer(scene,w,h-footer,h);
      return;
    } else {
      icon('plus',18,h-76,theme.accent,35);
      box(66,h-79,w-123,52,26,imessage?'#f4f4f6':'#fff');
      text(imessage?'iMessage':tr('Message','消息'),85,h-46,{size:21,color:'#626b72'});
      icon('mic',w-46,h-68,theme.accent,26);
    }
    footerLabel(scene,w,h-11);
  }
  return function render(scene,count) {
    const [w,h] = scene.size;
    if (canvas.width !== w || canvas.height !== h) { canvas.width=w; canvas.height=h; }
    const theme = themes[scene.theme];
    const wechat = scene.theme === 'wechat';
    const ownAvatar = wechat;
    const leftAvatar = wechat || scene.group;
    const top = wechat ? wechatHeaderHeight : 130;
    const bottom = h-(wechat?wechatFooterHeight:91);
    box(0,0,w,h,0,theme.bg);
    const rows = timeline(scene,count,Math.min(540,w-195));
    const total = rows.reduce((height,row) => height+row.height,0);
    const groupLead = wechat && scene.group ? wechatGroupSpacing.lead : 0;
    let y = Math.min(top+8+groupLead,bottom-total);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0,top,w,bottom-top);
    ctx.clip();
    for (const row of rows) {
      if (y+row.height <= top) { y += row.height; continue; }
      if (row.label) {
        if (!wechat && scene.theme !== 'imessage') box(w/2-94,y+5,188,32,16,'#ffffffa0');
        text(row.label,w/2,y+row.baseline,{size:wechat?24:19,color:wechat?'#8b8b8b':'#6c7072',align:'center'});
      } else {
        const {item,layout,nameSpace} = row;
        const pad = wechat ? 120 : (item.own ? ownAvatar : leftAvatar) ? 107 : 29;
        const x = item.own ? w-pad-layout.w : pad;
        const bubbleY = y+nameSpace;
        if (item.own ? ownAvatar : leftAvatar) {
          const size = wechat ? 75 : 49;
          const margin = wechat ? 22 : 19;
          avatar(item.person,item.own?w-size-margin:margin,y+(wechat && !nameSpace ? 0 : 5),size,wechat?7:size/2);
        }
        if (nameSpace) text(item.person.name || tr('Unnamed','未命名'),x,y+(wechat?18:21),
          {size:wechat?21:18,color:wechat?'#747879':theme.accent,max:layout.w+58});
        paintBubble(item,layout,x,bubbleY,scene,theme);
        if (layout.card) {
          const card = layout.card;
          const cardX = item.own ? w-pad-card.w : pad;
          const cardY = bubbleY+layout.h+7;
          box(cardX,cardY,card.w,card.h,theme.radius,'#fff');
          card.lines.forEach((line,index) => text(line,cardX+wechatText.inset,
            cardY+wechatText.firstBaseline+index*wechatText.lineHeight,{size:wechatText.fontSize}));
        }
      }
      y += row.height;
    }
    ctx.restore();
    bars(scene,count,theme,w,h);
  };
};
