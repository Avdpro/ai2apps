const Stream=require("stream");
const EventEmitter = require('events');

var normal = 0
	, escaped = 1
	, csi = 2
	, osc = 3
	, charset = 4
	, dcs = 5
	, ignore = 6
	, UDK = { type: 'udk' };

/**
 * Terminal
 */

function Terminal(options) {
	var self = this;
	
	if (!(this instanceof Terminal)) {
		return new Terminal(arguments[0], arguments[1], arguments[2]);
	}
	
	Stream.call(this);
	
	if (typeof options === 'number') {
		options = {
			cols: arguments[0],
			rows: arguments[1],
			handler: arguments[2]
		};
	}
	
	options = options || {};
	
	each(keys(Terminal.defaults), function(key) {
		if (options[key] == null) {
			options[key] = Terminal.options[key];
			// Legacy:
			if (Terminal[key] !== Terminal.defaults[key]) {
				options[key] = Terminal[key];
			}
		}
		self[key] = options[key];
	});
	
	if (options.colors.length === 8) {
		options.colors = options.colors.concat(Terminal._colors.slice(8));
	} else if (options.colors.length === 16) {
		options.colors = options.colors.concat(Terminal._colors.slice(16));
	} else if (options.colors.length === 10) {
		options.colors = options.colors.slice(0, -2).concat(
			Terminal._colors.slice(8, -2), options.colors.slice(-2));
	} else if (options.colors.length === 18) {
		options.colors = options.colors.slice(0, -2).concat(
			Terminal._colors.slice(16, -2), options.colors.slice(-2));
	}
	this.colors = options.colors;
	
	this.options = options;
	
	this.columns =this.cols = options.cols || options.geometry[0];
	this.rows = options.rows || options.geometry[1];
	
	// Act as though we are a node TTY stream:
	this.setRawMode;
	this.isTTY = true;
	this.isRaw = true;
	
	if (options.handler) {
		this.on('data', options.handler);
	}
	
	this.ybase = 0;
	this.ydisp = 0;
	this.x = 0;
	this.y = 0;
	this.cursorState = 0;
	this.cursorHidden = false;
	this.convertEol;
	this.state = 0;
	this.queue = '';
	this.scrollTop = 0;
	this.scrollBottom = this.rows - 1;
	
	// modes
	this.applicationKeypad = false;
	this.applicationCursor = false;
	this.originMode = false;
	this.insertMode = false;
	this.wraparoundMode = false;
	this.normal = null;
	
	// select modes
	this.prefixMode = false;
	this.selectMode = false;
	this.visualMode = false;
	this.searchMode = false;
	this.searchDown;
	this.entry = '';
	this.entryPrefix = 'Search: ';
	this._real;
	this._selected;
	this._textarea;
	
	// charset
	this.charset = null;
	this.gcharset = null;
	this.glevel = 0;
	this.charsets = [null];
	
	// mouse properties
	this.decLocator;
	this.x10Mouse;
	this.vt200Mouse;
	this.vt300Mouse;
	this.normalMouse;
	this.mouseEvents;
	this.sendFocus;
	this.utfMouse;
	this.sgrMouse;
	this.urxvtMouse;
	
	// misc
	this.document;
	this.context;
	this.element;
	this.children;
	this.refreshStart;
	this.refreshEnd;
	this.savedX;
	this.savedY;
	this.savedCols;
	
	// stream
	this.readable = true;
	this.writable = true;
	
	this.defAttr = (0 << 18) | (257 << 9) | (256 << 0);
	this.curAttr = this.defAttr;
	
	this.params = [];
	this.currentParam = 0;
	this.prefix = '';
	this.postfix = '';
	
	this.lines = [];
	var i = this.rows;
	while (i--) {
		this.lines.push(this.blankLine());
	}
	
	this.tabs;
	this.setupStops();
}

inherits(Terminal, Stream);

/**
 * Colors
 */

// Colors 0-15
Terminal.tangoColors = [
	// dark:
	'#2e3436',
	'#cc0000',
	'#4e9a06',
	'#c4a000',
	'#3465a4',
	'#75507b',
	'#06989a',
	'#d3d7cf',
	// bright:
	'#555753',
	'#ef2929',
	'#8ae234',
	'#fce94f',
	'#729fcf',
	'#ad7fa8',
	'#34e2e2',
	'#eeeeec'
];

Terminal.xtermColors = [
	// dark:
	'#000000', // black
	'#cd0000', // red3
	'#00cd00', // green3
	'#cdcd00', // yellow3
	'#0000ee', // blue2
	'#cd00cd', // magenta3
	'#00cdcd', // cyan3
	'#e5e5e5', // gray90
	// bright:
	'#7f7f7f', // gray50
	'#ff0000', // red
	'#00ff00', // green
	'#ffff00', // yellow
	'#5c5cff', // rgb:5c/5c/ff
	'#ff00ff', // magenta
	'#00ffff', // cyan
	'#ffffff'  // white
];

// Colors 0-15 + 16-255
// Much thanks to TooTallNate for writing this.
Terminal.colors = (function() {
	let colors = Terminal.tangoColors.slice()
		, r = [0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff]
		, i;
	
	// 16-231
	i = 0;
	for (; i < 216; i++) {
		out(r[(i / 36) % 6 | 0], r[(i / 6) % 6 | 0], r[i % 6]);
	}
	
	// 232-255 (grey)
	i = 0;
	for (; i < 24; i++) {
		r = 8 + i * 10;
		out(r, r, r);
	}
	
	function out(r, g, b) {
		colors.push('#' + hex(r) + hex(g) + hex(b));
	}
	
	function hex(c) {
		c = c.toString(16);
		return c.length < 2 ? '0' + c : c;
	}
	
	return colors;
})();

// Default BG/FG
Terminal.colors[256] = '#000000';
Terminal.colors[257] = '#f0f0f0';

Terminal._colors = Terminal.colors.slice();

Terminal.vcolors = (function() {
	var out = []
		, colors = Terminal.colors
		, i = 0
		, color;
	
	for (; i < 256; i++) {
		color = parseInt(colors[i].substring(1), 16);
		out.push([
			(color >> 16) & 0xff,
			(color >> 8) & 0xff,
			color & 0xff
		]);
	}
	
	return out;
})();

/**
 * Options
 */

Terminal.defaults = {
	colors: Terminal.colors,
	convertEol: false,
	termName: 'xterm',
	geometry: [80, 24],
	cursorBlink: true,
	visualBell: false,
	popOnBell: false,
	scrollback: 1000,
	screenKeys: false,
	debug: false,
	useStyle: false
	// programFeatures: false,
	// focusKeys: false,
};

Terminal.options = {};

each(keys(Terminal.defaults), function(key) {
	Terminal[key] = Terminal.defaults[key];
	Terminal.options[key] = Terminal.defaults[key];
});

/**
 * Focused Terminal
 */

Terminal.focus = null;

Terminal.prototype.focus = function() {
	if (Terminal.focus === this) return;
	
	if (Terminal.focus) {
		Terminal.focus.blur();
	}
	
	if (this.sendFocus) this.send('\x1b[I');
	this.showCursor();
	Terminal.focus = this;
};

Terminal.prototype.blur = function() {
	if (Terminal.focus !== this) return;
	
	this.cursorState = 0;
	this.refresh(this.y, this.y);
	if (this.sendFocus) this.send('\x1b[O');
	Terminal.focus = null;
};

/**
 * Initialize global behavior
 */

Terminal.prototype.initGlobal = function() {
	//Do nothing...
};


/**
 * Open Terminal
 */

Terminal.prototype.open = function() {
	var self = this
		, i = 0
		, div;
	
	// Grab global elements.
	this.context = null;
	this.document = null;
	this.body = null;
	
	// Parse user-agent strings.
	this.isNode = false;
	this.isMac = false;
	this.isIpad = false;
	this.isIphone = false;
	this.isAndroid = false;
	this.isMobile = false;
	this.isMSIE = false;
	
	// Create our main terminal element.
	this.element = null
	
	// Create the lines for our terminal.
	this.children = [];
	
	// Draw the screen.
	this.refresh(0, this.rows - 1);
	
	this.initGlobal();
	
	Terminal.brokenBold = false;
	this.emit('open');
};

Terminal.prototype.setRawMode = function(value) {
	this.isRaw = !!value;
};

/**
 * Destroy Terminal
 */

Terminal.prototype.close =
	Terminal.prototype.destroySoon =
		Terminal.prototype.destroy = function() {
			if (this.destroyed) {
				return;
			}
			
			if (this._blink) {
				clearInterval(this._blink);
				delete this._blink;
			}
			
			this.readable = false;
			this.writable = false;
			this.destroyed = true;
			this._events = {};
			
			this.handler = function() {};
			this.write = function() {};
			this.end = function() {};
			
			this.emit('end');
			this.emit('close');
			this.emit('finish');
			this.emit('destroy');
		};

/**
 * Rendering Engine
 */

// In the screen buffer, each character
// is stored as a an array with a character
// and a 32-bit integer.
// First value: a utf-16 character.
// Second value:
// Next 9 bits: background color (0-511).
// Next 9 bits: foreground color (0-511).
// Next 14 bits: a mask for misc. flags:
//   1=bold, 2=underline, 4=blink, 8=inverse, 16=invisible

Terminal.prototype.refresh = function(start, end) {
	let x, y, i, line, out, ch, width, data, attr, bg, fg, flags, row, parent;
	
	if(!this.element) return;
	width = this.cols;
	y = start;
	
	if (end >= this.lines.length) {
		this.log('`end` is too large. Most likely a bad CSR.');
		end = this.lines.length - 1;
	}
	
	for (; y <= end; y++) {
		row = y + this.ydisp;
		
		line = this.lines[row];
		out = '';
		
		if (y === this.y
			&& this.cursorState
			&& (this.ydisp === this.ybase || this.selectMode)
			&& !this.cursorHidden) {
			x = this.x;
		} else {
			x = -1;
		}
		
		attr = this.defAttr;
		i = 0;
		
		for (; i < width; i++) {
			data = line[i][0];
			ch = line[i][1];
			
			if (i === x) data = -1;
			
			if (data !== attr) {
				if (attr !== this.defAttr) {
					out += '</span>';
				}
				if (data !== this.defAttr) {
					if (data === -1) {
						out += '<span class="reverse-video terminal-cursor">';
					} else {
						out += '<span style="';
						
						bg = data & 0x1ff;
						fg = (data >> 9) & 0x1ff;
						flags = data >> 18;
						
						// bold
						if (flags & 1) {
							if (!Terminal.brokenBold) {
								out += 'font-weight:bold;';
							}
							// See: XTerm*boldColors
							if (fg < 8) fg += 8;
						}
						
						// underline
						if (flags & 2) {
							out += 'text-decoration:underline;';
						}
						
						// blink
						if (flags & 4) {
							if (flags & 2) {
								out = out.slice(0, -1);
								out += ' blink;';
							} else {
								out += 'text-decoration:blink;';
							}
						}
						
						// inverse
						if (flags & 8) {
							bg = (data >> 9) & 0x1ff;
							fg = data & 0x1ff;
							// Should inverse just be before the
							// above boldColors effect instead?
							if ((flags & 1) && fg < 8) fg += 8;
						}
						
						// invisible
						if (flags & 16) {
							out += 'visibility:hidden;';
						}
						
						// out += '" class="'
						//   + 'term-bg-color-' + bg
						//   + ' '
						//   + 'term-fg-color-' + fg
						//   + '">';
						
						if (bg !== 256) {
							out += 'background-color:'
								+ this.colors[bg]
								+ ';';
						}
						
						if (fg !== 257) {
							out += 'color:'
								+ this.colors[fg]
								+ ';';
						}
						
						out += '">';
					}
				}
			}
			
			switch (ch) {
				case '&':
					out += '&amp;';
					break;
				case '<':
					out += '&lt;';
					break;
				case '>':
					out += '&gt;';
					break;
				default:
					if (ch <= ' ') {
						out += '&nbsp;';
					} else {
						if (isWide(ch)) i++;
						out += ch;
					}
					break;
			}
			
			attr = data;
		}
		
		if (attr !== this.defAttr) {
			out += '</span>';
		}
	}
};

Terminal.prototype._cursorBlink = function() {
	if (Terminal.focus !== this) return;
	this.cursorState ^= 1;
	this.refresh(this.y, this.y);
};

Terminal.prototype.showCursor = function() {
	if (!this.cursorState) {
		this.cursorState = 1;
		this.refresh(this.y, this.y);
	} else {
		// Temporarily disabled:
		// this.refreshBlink();
	}
};

Terminal.prototype.startBlink = function() {
	if (!this.cursorBlink) return;
	var self = this;
	this._blinker = function() {
		self._cursorBlink();
	};
	this._blink = setInterval(this._blinker, 500);
};

Terminal.prototype.refreshBlink = function() {
	if (!this.cursorBlink || !this._blink) return;
	clearInterval(this._blink);
	this._blink = setInterval(this._blinker, 500);
};

Terminal.prototype.scroll = function() {
	var row;
	
	if (++this.ybase === this.scrollback) {
		this.ybase = this.ybase / 2 | 0;
		this.lines = this.lines.slice(-(this.ybase + this.rows) + 1);
	}
	
	this.ydisp = this.ybase;
	
	// last line
	row = this.ybase + this.rows - 1;
	
	// subtract the bottom scroll region
	row -= this.rows - 1 - this.scrollBottom;
	
	if (row === this.lines.length) {
		// potential optimization:
		// pushing is faster than splicing
		// when they amount to the same
		// behavior.
		this.lines.push(this.blankLine());
	} else {
		// add our new line
		this.lines.splice(row, 0, this.blankLine());
	}
	
	if (this.scrollTop !== 0) {
		if (this.ybase !== 0) {
			this.ybase--;
			this.ydisp = this.ybase;
		}
		this.lines.splice(this.ybase + this.scrollTop, 1);
	}
	
	// this.maxRange();
	this.updateRange(this.scrollTop);
	this.updateRange(this.scrollBottom);
};

Terminal.prototype.scrollDisp = function(disp) {
	this.ydisp += disp;
	
	if (this.ydisp > this.ybase) {
		this.ydisp = this.ybase;
	} else if (this.ydisp < 0) {
		this.ydisp = 0;
	}
	
	this.refresh(0, this.rows - 1);
};

Terminal.prototype.write = function(data) {
	let l = data.length, i = 0, j, cs, ch;
	
	this.refreshStart = this.y;
	this.refreshEnd = this.y;
	
	if (this.ybase !== this.ydisp) {
		this.ydisp = this.ybase;
		this.maxRange();
	}
	
	// this.log(JSON.stringify(data.replace(/\x1b/g, '^[')));
	
	for (; i < l; i++, this.lch = ch) {
		ch = data[i];
		switch (this.state) {
			case normal:
				switch (ch) {
					// '\0'
					// case '\0':
					// case '\200':
					//   break;
					
					// '\a'
					case '\x07':
						this.bell();
						break;
					
					// '\n', '\v', '\f'
					case '\n':
					case '\x0b':
					case '\x0c':
						if (this.convertEol) {
							this.x = 0;
						}
						// TODO: Implement eat_newline_glitch.
						// if (this.realX >= this.cols) break;
						// this.realX = 0;
						this.y++;
						if (this.y > this.scrollBottom) {
							this.y--;
							this.scroll();
						}
						break;
					
					// '\r'
					case '\r':
						this.x = 0;
						break;
					
					// '\b'
					case '\x08':
						if (this.x > 0) {
							this.x--;
						}
						break;
					
					// '\t'
					case '\t':
						this.x = this.nextStop();
						break;
					
					// shift out
					case '\x0e':
						this.setgLevel(1);
						break;
					
					// shift in
					case '\x0f':
						this.setgLevel(0);
						break;
					
					// '\e'
					case '\x1b':
						this.state = escaped;
						break;
					
					default: {
						let line;
						// ' '
						if (ch >= ' ') {
							if (this.charset && this.charset[ch]) {
								ch = this.charset[ch];
							}
							
							if (this.x >= this.cols) {
								this.x = 0;
								this.y++;
								if (this.y > this.scrollBottom) {
									this.y--;
									this.scroll();
								}
							}
							line=this.lines[this.y + this.ybase];
							if(!line){
								//TODO: Add a blank line:
							}
							line[this.x] = [this.curAttr, ch];
							this.x++;
							this.updateRange(this.y);
							
							if (isWide(ch)) {
								j = this.y + this.ybase;
								if (this.cols < 2 || this.x >= this.cols) {
									this.lines[j][this.x - 1] = [this.curAttr, ' '];
									break;
								}
								this.lines[j][this.x] = [this.curAttr, ' '];
								this.x++;
							}
						}
						break;
					}
				}
				break;
			case escaped:
				switch (ch) {
					// ESC [ Control Sequence Introducer ( CSI is 0x9b).
					case '[':
						this.params = [];
						this.currentParam = 0;
						this.state = csi;
						break;
					
					// ESC ] Operating System Command ( OSC is 0x9d).
					case ']':
						this.params = [];
						this.currentParam = 0;
						this.state = osc;
						break;
					
					// ESC P Device Control String ( DCS is 0x90).
					case 'P':
						this.params = [];
						this.prefix = '';
						this.currentParam = '';
						this.state = dcs;
						break;
					
					// ESC _ Application Program Command ( APC is 0x9f).
					case '_':
						this.state = ignore;
						break;
					
					// ESC ^ Privacy Message ( PM is 0x9e).
					case '^':
						this.state = ignore;
						break;
					
					// ESC c Full Reset (RIS).
					case 'c':
						this.reset();
						break;
					
					// ESC E Next Line ( NEL is 0x85).
					// ESC D Index ( IND is 0x84).
					case 'E':
						this.x = 0;
						this.index();
						break;
					case 'D':
						this.index();
						break;
					
					// ESC M Reverse Index ( RI is 0x8d).
					case 'M':
						this.reverseIndex();
						break;
					
					// ESC % Select default/utf-8 character set.
					// @ = default, G = utf-8
					case '%':
						//this.charset = null;
						this.setgLevel(0);
						this.setgCharset(0, Terminal.charsets.US);
						this.state = normal;
						i++;
						break;
					
					// ESC (,),*,+,-,. Designate G0-G2 Character Set.
					case '(': // <-- this seems to get all the attention
					case ')':
					case '*':
					case '+':
					case '-':
					case '.':
						switch (ch) {
							case '(':
								this.gcharset = 0;
								break;
							case ')':
								this.gcharset = 1;
								break;
							case '*':
								this.gcharset = 2;
								break;
							case '+':
								this.gcharset = 3;
								break;
							case '-':
								this.gcharset = 1;
								break;
							case '.':
								this.gcharset = 2;
								break;
						}
						this.state = charset;
						break;
					
					// Designate G3 Character Set (VT300).
					// A = ISO Latin-1 Supplemental.
					// Not implemented.
					case '/':
						this.gcharset = 3;
						this.state = charset;
						i--;
						break;
					
					// ESC N
					// Single Shift Select of G2 Character Set
					// ( SS2 is 0x8e). This affects next character only.
					case 'N':
						break;
					// ESC O
					// Single Shift Select of G3 Character Set
					// ( SS3 is 0x8f). This affects next character only.
					case 'O':
						break;
					// ESC n
					// Invoke the G2 Character Set as GL (LS2).
					case 'n':
						this.setgLevel(2);
						break;
					// ESC o
					// Invoke the G3 Character Set as GL (LS3).
					case 'o':
						this.setgLevel(3);
						break;
					// ESC |
					// Invoke the G3 Character Set as GR (LS3R).
					case '|':
						this.setgLevel(3);
						break;
					// ESC }
					// Invoke the G2 Character Set as GR (LS2R).
					case '}':
						this.setgLevel(2);
						break;
					// ESC ~
					// Invoke the G1 Character Set as GR (LS1R).
					case '~':
						this.setgLevel(1);
						break;
					
					// ESC 7 Save Cursor (DECSC).
					case '7':
						this.saveCursor();
						this.state = normal;
						break;
					
					// ESC 8 Restore Cursor (DECRC).
					case '8':
						this.restoreCursor();
						this.state = normal;
						break;
					
					// ESC # 3 DEC line height/width
					case '#':
						this.state = normal;
						i++;
						break;
					
					// ESC H Tab Set (HTS is 0x88).
					case 'H':
						this.tabSet();
						break;
					
					// ESC = Application Keypad (DECPAM).
					case '=':
						this.log('Serial port requested application keypad.');
						this.applicationKeypad = true;
						this.state = normal;
						break;
					
					// ESC > Normal Keypad (DECPNM).
					case '>':
						this.log('Switching back to normal keypad.');
						this.applicationKeypad = false;
						this.state = normal;
						break;
					
					default:
						this.state = normal;
						this.error('Unknown ESC control: %s.', ch);
						break;
				}
				break;
			
			case charset:
				switch (ch) {
					case '0': // DEC Special Character and Line Drawing Set.
						cs = Terminal.charsets.SCLD;
						break;
					case 'A': // UK
						cs = Terminal.charsets.UK;
						break;
					case 'B': // United States (USASCII).
						cs = Terminal.charsets.US;
						break;
					case '4': // Dutch
						cs = Terminal.charsets.Dutch;
						break;
					case 'C': // Finnish
					case '5':
						cs = Terminal.charsets.Finnish;
						break;
					case 'R': // French
						cs = Terminal.charsets.French;
						break;
					case 'Q': // FrenchCanadian
						cs = Terminal.charsets.FrenchCanadian;
						break;
					case 'K': // German
						cs = Terminal.charsets.German;
						break;
					case 'Y': // Italian
						cs = Terminal.charsets.Italian;
						break;
					case 'E': // NorwegianDanish
					case '6':
						cs = Terminal.charsets.NorwegianDanish;
						break;
					case 'Z': // Spanish
						cs = Terminal.charsets.Spanish;
						break;
					case 'H': // Swedish
					case '7':
						cs = Terminal.charsets.Swedish;
						break;
					case '=': // Swiss
						cs = Terminal.charsets.Swiss;
						break;
					case '/': // ISOLatin (actually /A)
						cs = Terminal.charsets.ISOLatin;
						i++;
						break;
					default: // Default
						cs = Terminal.charsets.US;
						break;
				}
				this.setgCharset(this.gcharset, cs);
				this.gcharset = null;
				this.state = normal;
				break;
			
			case osc:
				// OSC Ps ; Pt ST
				// OSC Ps ; Pt BEL
				//   Set Text Parameters.
				if ((this.lch === '\x1b' && ch === '\\') || ch === '\x07') {
					if (this.lch === '\x1b') {
						if (typeof this.currentParam === 'string') {
							this.currentParam = this.currentParam.slice(0, -1);
						} else if (typeof this.currentParam == 'number') {
							this.currentParam = (this.currentParam - ('\x1b'.charCodeAt(0) - 48)) / 10;
						}
					}
					
					this.params.push(this.currentParam);
					
					switch (this.params[0]) {
						case 0:
						case 1:
						case 2:
							if (this.params[1]) {
								this.title = this.params[1];
								this.handleTitle(this.title);
							}
							break;
						case 3:
							// set X property
							break;
						case 4:
						case 5:
							// change dynamic colors
							break;
						case 10:
						case 11:
						case 12:
						case 13:
						case 14:
						case 15:
						case 16:
						case 17:
						case 18:
						case 19:
							// change dynamic ui colors
							break;
						case 46:
							// change log file
							break;
						case 50:
							// dynamic font
							break;
						case 51:
							// emacs shell
							break;
						case 52:
							// manipulate selection data
							break;
						case 104:
						case 105:
						case 110:
						case 111:
						case 112:
						case 113:
						case 114:
						case 115:
						case 116:
						case 117:
						case 118:
							// reset colors
							break;
					}
					
					this.params = [];
					this.currentParam = 0;
					this.state = normal;
				} else {
					if (!this.params.length) {
						if (ch >= '0' && ch <= '9') {
							this.currentParam =
								this.currentParam * 10 + ch.charCodeAt(0) - 48;
						} else if (ch === ';') {
							this.params.push(this.currentParam);
							this.currentParam = '';
						}
					} else {
						this.currentParam += ch;
					}
				}
				break;
			
			case csi:
				// '?', '>', '!'
				if (ch === '?' || ch === '>' || ch === '!') {
					this.prefix = ch;
					break;
				}
				
				// 0 - 9
				if (ch >= '0' && ch <= '9') {
					this.currentParam = this.currentParam * 10 + ch.charCodeAt(0) - 48;
					break;
				}
				
				// '$', '"', ' ', '\''
				if (ch === '$' || ch === '"' || ch === ' ' || ch === '\'') {
					this.postfix = ch;
					break;
				}
				
				this.params.push(this.currentParam);
				this.currentParam = 0;
				
				// ';'
				if (ch === ';') break;
				
				this.state = normal;
				
				switch (ch) {
					// CSI Ps A
					// Cursor Up Ps Times (default = 1) (CUU).
					case 'A':
						this.cursorUp(this.params);
						break;
					
					// CSI Ps B
					// Cursor Down Ps Times (default = 1) (CUD).
					case 'B':
						this.cursorDown(this.params);
						break;
					
					// CSI Ps C
					// Cursor Forward Ps Times (default = 1) (CUF).
					case 'C':
						this.cursorForward(this.params);
						break;
					
					// CSI Ps D
					// Cursor Backward Ps Times (default = 1) (CUB).
					case 'D':
						this.cursorBackward(this.params);
						break;
					
					// CSI Ps ; Ps H
					// Cursor Position [row;column] (default = [1,1]) (CUP).
					case 'H':
						this.cursorPos(this.params);
						break;
					
					// CSI Ps J  Erase in Display (ED).
					case 'J':
						this.eraseInDisplay(this.params);
						break;
					
					// CSI Ps K  Erase in Line (EL).
					case 'K':
						this.eraseInLine(this.params);
						break;
					
					// CSI Pm m  Character Attributes (SGR).
					case 'm':
						if (!this.prefix) {
							this.charAttributes(this.params);
						}
						break;
					
					// CSI Ps n  Device Status Report (DSR).
					case 'n':
						if (!this.prefix) {
							this.deviceStatus(this.params);
						}
						break;
					
					/**
					 * Additions
					 */
					
					// CSI Ps @
					// Insert Ps (Blank) Character(s) (default = 1) (ICH).
					case '@':
						this.insertChars(this.params);
						break;
					
					// CSI Ps E
					// Cursor Next Line Ps Times (default = 1) (CNL).
					case 'E':
						this.cursorNextLine(this.params);
						break;
					
					// CSI Ps F
					// Cursor Preceding Line Ps Times (default = 1) (CNL).
					case 'F':
						this.cursorPrecedingLine(this.params);
						break;
					
					// CSI Ps G
					// Cursor Character Absolute  [column] (default = [row,1]) (CHA).
					case 'G':
						this.cursorCharAbsolute(this.params);
						break;
					
					// CSI Ps L
					// Insert Ps Line(s) (default = 1) (IL).
					case 'L':
						this.insertLines(this.params);
						break;
					
					// CSI Ps M
					// Delete Ps Line(s) (default = 1) (DL).
					case 'M':
						this.deleteLines(this.params);
						break;
					
					// CSI Ps P
					// Delete Ps Character(s) (default = 1) (DCH).
					case 'P':
						this.deleteChars(this.params);
						break;
					
					// CSI Ps X
					// Erase Ps Character(s) (default = 1) (ECH).
					case 'X':
						this.eraseChars(this.params);
						break;
					
					// CSI Pm `  Character Position Absolute
					//   [column] (default = [row,1]) (HPA).
					case '`':
						this.charPosAbsolute(this.params);
						break;
					
					// 141 61 a * HPR -
					// Horizontal Position Relative
					case 'a':
						this.HPositionRelative(this.params);
						break;
					
					// CSI P s c
					// Send Device Attributes (Primary DA).
					// CSI > P s c
					// Send Device Attributes (Secondary DA)
					case 'c':
						this.sendDeviceAttributes(this.params);
						break;
					
					// CSI Pm d
					// Line Position Absolute  [row] (default = [1,column]) (VPA).
					case 'd':
						this.linePosAbsolute(this.params);
						break;
					
					// 145 65 e * VPR - Vertical Position Relative
					case 'e':
						this.VPositionRelative(this.params);
						break;
					
					// CSI Ps ; Ps f
					//   Horizontal and Vertical Position [row;column] (default =
					//   [1,1]) (HVP).
					case 'f':
						this.HVPosition(this.params);
						break;
					
					// CSI Pm h  Set Mode (SM).
					// CSI ? Pm h - mouse escape codes, cursor escape codes
					case 'h':
						this.setMode(this.params);
						break;
					
					// CSI Pm l  Reset Mode (RM).
					// CSI ? Pm l
					case 'l':
						this.resetMode(this.params);
						break;
					
					// CSI Ps ; Ps r
					//   Set Scrolling Region [top;bottom] (default = full size of win-
					//   dow) (DECSTBM).
					// CSI ? Pm r
					case 'r':
						this.setScrollRegion(this.params);
						break;
					
					// CSI s
					//   Save cursor (ANSI.SYS).
					case 's':
						this.saveCursor(this.params);
						break;
					
					// CSI u
					//   Restore cursor (ANSI.SYS).
					case 'u':
						this.restoreCursor(this.params);
						break;
					
					/**
					 * Lesser Used
					 */
					
					// CSI Ps I
					// Cursor Forward Tabulation Ps tab stops (default = 1) (CHT).
					case 'I':
						this.cursorForwardTab(this.params);
						break;
					
					// CSI Ps S  Scroll up Ps lines (default = 1) (SU).
					case 'S':
						this.scrollUp(this.params);
						break;
					
					// CSI Ps T  Scroll down Ps lines (default = 1) (SD).
					// CSI Ps ; Ps ; Ps ; Ps ; Ps T
					// CSI > Ps; Ps T
					case 'T':
						if (this.params.length < 2 && !this.prefix) {
							this.scrollDown(this.params);
						}
						break;
					
					// CSI Ps Z
					// Cursor Backward Tabulation Ps tab stops (default = 1) (CBT).
					case 'Z':
						this.cursorBackwardTab(this.params);
						break;
					
					// CSI Ps b  Repeat the preceding graphic character Ps times (REP).
					case 'b':
						this.repeatPrecedingCharacter(this.params);
						break;
					
					// CSI Ps g  Tab Clear (TBC).
					case 'g':
						this.tabClear(this.params);
						break;
					
					// CSI > Ps p  Set pointer mode.
					// CSI ! p   Soft terminal reset (DECSTR).
					// CSI Ps$ p
					//   Request ANSI mode (DECRQM).
					// CSI ? Ps$ p
					//   Request DEC private mode (DECRQM).
					// CSI Ps ; Ps " p
					case 'p':
						switch (this.prefix) {
							case '!':
								this.softReset(this.params);
								break;
						}
						break;
					
					// CSI Pt; Pl; Pb; Pr; Pp; Pt; Pl; Pp$ v
					// case 'v':
					//   if (this.postfix === '$') {
					//     this.copyRectagle(this.params);
					//   }
					//   break;
					
					default:
						this.error('Unknown CSI code: %s.', ch);
						break;
				}
				
				this.prefix = '';
				this.postfix = '';
				break;
			
			case dcs:
				if ((this.lch === '\x1b' && ch === '\\') || ch === '\x07') {
					// Workarounds:
					if (this.prefix === 'tmux;\x1b') {
						// `DCS tmux; Pt ST` may contain a Pt with an ST
						// XXX Does tmux work this way?
						// if (this.lch === '\x1b' & data[i + 1] === '\x1b' && data[i + 2] === '\\') {
						//   this.currentParam += ch;
						//   continue;
						// }
						// Tmux only accepts ST, not BEL:
						if (ch === '\x07') {
							this.currentParam += ch;
							continue;
						}
					}
					
					if (this.lch === '\x1b') {
						if (typeof this.currentParam === 'string') {
							this.currentParam = this.currentParam.slice(0, -1);
						} else if (typeof this.currentParam == 'number') {
							this.currentParam = (this.currentParam - ('\x1b'.charCodeAt(0) - 48)) / 10;
						}
					}
					
					this.params.push(this.currentParam);
					
					var pt = this.params[this.params.length - 1];
					
					switch (this.prefix) {
						// User-Defined Keys (DECUDK).
						// DCS Ps; Ps| Pt ST
						case UDK:
							this.emit('udk', {
								clearAll: this.params[0] === 0,
								eraseBelow: this.params[0] === 1,
								lockKeys: this.params[1] === 0,
								dontLockKeys: this.params[1] === 1,
								keyList: (this.params[2] + '').split(';').map(function(part) {
									part = part.split('/');
									return {
										keyCode: part[0],
										hexKeyValue: part[1]
									};
								})
							});
							break;
						
						// Request Status String (DECRQSS).
						// DCS $ q Pt ST
						// test: echo -e '\eP$q"p\e\\'
						case '$q': {
							let valid = 0;
							
							switch (pt) {
								// DECSCA
								// CSI Ps " q
								case '"q':
									pt = '0"q';
									valid = 1;
									break;
								
								// DECSCL
								// CSI Ps ; Ps " p
								case '"p':
									pt = '61;0"p';
									valid = 1;
									break;
								
								// DECSTBM
								// CSI Ps ; Ps r
								case 'r':
									pt = ''
										+ (this.scrollTop + 1)
										+ ';'
										+ (this.scrollBottom + 1)
										+ 'r';
									valid = 1;
									break;
								
								// SGR
								// CSI Pm m
								case 'm':
									// TODO: Parse this.curAttr here.
									// pt = '0m';
									// valid = 1;
									valid = 0; // Not implemented.
									break;
								
								default:
									this.error('Unknown DCS Pt: %s.', pt);
									valid = 0; // unimplemented
									break;
							}
							
							this.send('\x1bP' + valid + '$r' + pt + '\x1b\\');
							break;
						}
						
						// Set Termcap/Terminfo Data (xterm, experimental).
						// DCS + p Pt ST
						case '+p':
							this.emit('set terminfo', {
								name: this.params[0]
							});
							break;
						
						// Request Termcap/Terminfo String (xterm, experimental)
						// Regular xterm does not even respond to this sequence.
						// This can cause a small glitch in vim.
						// DCS + q Pt ST
						// test: echo -ne '\eP+q6b64\e\\'
						case '+q':
							var valid = false;
							this.send('\x1bP' + +valid + '+r' + pt + '\x1b\\');
							break;
						
						// Implement tmux sequence forwarding is
						// someone uses term.js for a multiplexer.
						// DCS tmux; ESC Pt ST
						case 'tmux;\x1b':
							this.emit('passthrough', pt);
							break;
						
						default:
							this.error('Unknown DCS prefix: %s.', pt);
							break;
					}
					
					this.currentParam = 0;
					this.prefix = '';
					this.state = normal;
				} else {
					this.currentParam += ch;
					if (!this.prefix) {
						if (/^\d*;\d*\|/.test(this.currentParam)) {
							this.prefix = UDK;
							this.params = this.currentParam.split(/[;|]/).map(function(n) {
								if (!n.length) return 0;
								return +n;
							}).slice(0, -1);
							this.currentParam = '';
						} else if (/^[$+][a-zA-Z]/.test(this.currentParam)
							|| /^\w+;\x1b/.test(this.currentParam)) {
							this.prefix = this.currentParam;
							this.currentParam = '';
						}
					}
				}
				break;
			
			case ignore:
				// For PM and APC.
				if ((this.lch === '\x1b' && ch === '\\') || ch === '\x07') {
					this.state = normal;
				}
				break;
		}
	}
	
	this.updateRange(this.y);
	this.refresh(this.refreshStart, this.refreshEnd);
	
	return true;
};

Terminal.prototype.writeln = function(data) {
	return this.write(data + '\r\n');
};

Terminal.prototype.end = function(data) {
	var ret = true;
	if (data) {
		ret = this.write(data);
	}
	this.destroySoon();
	return ret;
};

Terminal.prototype.setgLevel = function(g) {
	this.glevel = g;
	this.charset = this.charsets[g];
};

Terminal.prototype.setgCharset = function(g, charset) {
	this.charsets[g] = charset;
	if (this.glevel === g) {
		this.charset = charset;
	}
};

Terminal.prototype.send = function(data) {
	var self = this;
	
	if (!this.queue) {
		setTimeout(function() {
			self.handler(self.queue);
			self.queue = '';
		}, 1);
	}
	
	this.queue += data;
};

Terminal.prototype.bell = function() {
	this.emit('bell');
};

Terminal.prototype.log = function(...args) {
	console.log(...args);
};

Terminal.prototype.error = function(...args) {
	console.error(...args);
};

Terminal.prototype.resize = function(x, y) {
	let line, el, i, j, ch;
	
	if (x < 1) x = 1;
	if (y < 1) y = 1;
	
	// resize cols
	j = this.cols;
	if (j < x) {
		ch = [this.defAttr, ' ']; // does xterm use the default attr?
		i = this.lines.length;
		while (i--) {
			while (this.lines[i].length < x) {
				this.lines[i].push(ch);
			}
		}
	} else if (j > x) {
		i = this.lines.length;
		while (i--) {
			while (this.lines[i].length > x) {
				this.lines[i].pop();
			}
		}
	}
	this.setupStops(j);
	this.cols = x;
	this.columns = x;
	
	// resize rows
	j = this.rows;
	if (j < y) {
		while (j++ < y) {
			if (this.lines.length < y + this.ybase) {
				this.lines.push(this.blankLine());
			}
		}
	} else if (j > y) {
		while (j-- > y) {
			if (this.lines.length > y + this.ybase) {
				this.lines.pop();
			}
		}
	}
	this.rows = y;
	
	// make sure the cursor stays on screen
	if (this.y >= y) this.y = y - 1;
	if (this.x >= x) this.x = x - 1;
	
	this.scrollTop = 0;
	this.scrollBottom = y - 1;
	
	this.refresh(0, this.rows - 1);
	
	// it's a real nightmare trying
	// to resize the original
	// screen buffer. just set it
	// to null for now.
	this.normal = null;
	
	// Act as though we are a node TTY stream:
	this.emit('resize');
};

Terminal.prototype.updateRange = function(y) {
	if (y < this.refreshStart) this.refreshStart = y;
	if (y > this.refreshEnd) this.refreshEnd = y;
};

Terminal.prototype.maxRange = function() {
	this.refreshStart = 0;
	this.refreshEnd = this.rows - 1;
};

Terminal.prototype.setupStops = function(i) {
	if (i != null) {
		if (!this.tabs[i]) {
			i = this.prevStop(i);
		}
	} else {
		this.tabs = {};
		i = 0;
	}
	
	for (; i < this.cols; i += 8) {
		this.tabs[i] = true;
	}
};

Terminal.prototype.prevStop = function(x) {
	if (x == null) x = this.x;
	while (!this.tabs[--x] && x > 0);
	return x >= this.cols
		? this.cols - 1
		: x < 0 ? 0 : x;
};

Terminal.prototype.nextStop = function(x) {
	if (x == null) x = this.x;
	while (!this.tabs[++x] && x < this.cols);
	return x >= this.cols
		? this.cols - 1
		: x < 0 ? 0 : x;
};

// back_color_erase feature for xterm.
Terminal.prototype.eraseAttr = function() {
	// if (this.is('screen')) return this.defAttr;
	return (this.defAttr & ~0x1ff) | (this.curAttr & 0x1ff);
};

Terminal.prototype.eraseRight = function(x, y) {
	var line = this.lines[this.ybase + y]
		, ch = [this.eraseAttr(), ' ']; // xterm
	
	
	for (; x < this.cols; x++) {
		line[x] = ch;
	}
	
	this.updateRange(y);
};

Terminal.prototype.eraseLeft = function(x, y) {
	var line = this.lines[this.ybase + y]
		, ch = [this.eraseAttr(), ' ']; // xterm
	
	x++;
	while (x--) line[x] = ch;
	
	this.updateRange(y);
};

Terminal.prototype.eraseLine = function(y) {
	this.eraseRight(0, y);
};

Terminal.prototype.blankLine = function(cur) {
	var attr = cur
		? this.eraseAttr()
		: this.defAttr;
	
	var ch = [attr, ' ']
		, line = []
		, i = 0;
	
	for (; i < this.cols; i++) {
		line[i] = ch;
	}
	
	return line;
};

Terminal.prototype.ch = function(cur) {
	return cur
		? [this.eraseAttr(), ' ']
		: [this.defAttr, ' '];
};

Terminal.prototype.is = function(term) {
	var name = this.termName;
	return (name + '').indexOf(term) === 0;
};

Terminal.prototype.handler = function(data) {
	this.emit('data', data);
};

Terminal.prototype.handleTitle = function(title) {
	this.emit('title', title);
};

/**
 * ESC
 */

// ESC D Index (IND is 0x84).
Terminal.prototype.index = function() {
	this.y++;
	if (this.y > this.scrollBottom) {
		this.y--;
		this.scroll();
	}
	this.state = normal;
};

// ESC M Reverse Index (RI is 0x8d).
Terminal.prototype.reverseIndex = function() {
	var j;
	this.y--;
	if (this.y < this.scrollTop) {
		this.y++;
		// possibly move the code below to term.reverseScroll();
		// test: echo -ne '\e[1;1H\e[44m\eM\e[0m'
		// blankLine(true) is xterm/linux behavior
		this.lines.splice(this.y + this.ybase, 0, this.blankLine(true));
		j = this.rows - 1 - this.scrollBottom;
		this.lines.splice(this.rows - 1 + this.ybase - j + 1, 1);
		// this.maxRange();
		this.updateRange(this.scrollTop);
		this.updateRange(this.scrollBottom);
	}
	this.state = normal;
};

// ESC c Full Reset (RIS).
Terminal.prototype.reset = function() {
	this.options.rows = this.rows;
	this.options.cols = this.cols;
	Terminal.call(this, this.options);
	this.refresh(0, this.rows - 1);
};

// ESC H Tab Set (HTS is 0x88).
Terminal.prototype.tabSet = function() {
	this.tabs[this.x] = true;
	this.state = normal;
};

/**
 * CSI
 */

// CSI Ps A
// Cursor Up Ps Times (default = 1) (CUU).
Terminal.prototype.cursorUp = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y -= param;
	if (this.y < 0) this.y = 0;
};

// CSI Ps B
// Cursor Down Ps Times (default = 1) (CUD).
Terminal.prototype.cursorDown = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y += param;
	if (this.y >= this.rows) {
		this.y = this.rows - 1;
	}
};

// CSI Ps C
// Cursor Forward Ps Times (default = 1) (CUF).
Terminal.prototype.cursorForward = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.x += param;
	if (this.x >= this.cols) {
		this.x = this.cols - 1;
	}
};

// CSI Ps D
// Cursor Backward Ps Times (default = 1) (CUB).
Terminal.prototype.cursorBackward = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.x -= param;
	if (this.x < 0) this.x = 0;
};

// CSI Ps ; Ps H
// Cursor Position [row;column] (default = [1,1]) (CUP).
Terminal.prototype.cursorPos = function(params) {
	var row, col;
	
	row = params[0] - 1;
	
	if (params.length >= 2) {
		col = params[1] - 1;
	} else {
		col = 0;
	}
	
	if (row < 0) {
		row = 0;
	} else if (row >= this.rows) {
		row = this.rows - 1;
	}
	
	if (col < 0) {
		col = 0;
	} else if (col >= this.cols) {
		col = this.cols - 1;
	}
	
	this.x = col;
	this.y = row;
};

Terminal.prototype.eraseInDisplay = function(params) {
	var j;
	switch (params[0]) {
		case 0:
			this.eraseRight(this.x, this.y);
			j = this.y + 1;
			for (; j < this.rows; j++) {
				this.eraseLine(j);
			}
			break;
		case 1:
			this.eraseLeft(this.x, this.y);
			j = this.y;
			while (j--) {
				this.eraseLine(j);
			}
			break;
		case 2:
			j = this.rows;
			while (j--) this.eraseLine(j);
			break;
		case 3:
			break;
	}
};

// CSI Ps K  Erase in Line (EL).
//     Ps = 0  -> Erase to Right (default).
//     Ps = 1  -> Erase to Left.
//     Ps = 2  -> Erase All.
// CSI ? Ps K
//   Erase in Line (DECSEL).
//     Ps = 0  -> Selective Erase to Right (default).
//     Ps = 1  -> Selective Erase to Left.
//     Ps = 2  -> Selective Erase All.
Terminal.prototype.eraseInLine = function(params) {
	switch (params[0]) {
		case 0:
			this.eraseRight(this.x, this.y);
			break;
		case 1:
			this.eraseLeft(this.x, this.y);
			break;
		case 2:
			this.eraseLine(this.y);
			break;
	}
};

// CSI Pm m  Character Attributes (SGR).
//     Ps = 0  -> Normal (default).
//     Ps = 1  -> Bold.
//     Ps = 4  -> Underlined.
//     Ps = 5  -> Blink (appears as Bold).
//     Ps = 7  -> Inverse.
//     Ps = 8  -> Invisible, i.e., hidden (VT300).
//     Ps = 2 2  -> Normal (neither bold nor faint).
//     Ps = 2 4  -> Not underlined.
//     Ps = 2 5  -> Steady (not blinking).
//     Ps = 2 7  -> Positive (not inverse).
//     Ps = 2 8  -> Visible, i.e., not hidden (VT300).
//     Ps = 3 0  -> Set foreground color to Black.
//     Ps = 3 1  -> Set foreground color to Red.
//     Ps = 3 2  -> Set foreground color to Green.
//     Ps = 3 3  -> Set foreground color to Yellow.
//     Ps = 3 4  -> Set foreground color to Blue.
//     Ps = 3 5  -> Set foreground color to Magenta.
//     Ps = 3 6  -> Set foreground color to Cyan.
//     Ps = 3 7  -> Set foreground color to White.
//     Ps = 3 9  -> Set foreground color to default (original).
//     Ps = 4 0  -> Set background color to Black.
//     Ps = 4 1  -> Set background color to Red.
//     Ps = 4 2  -> Set background color to Green.
//     Ps = 4 3  -> Set background color to Yellow.
//     Ps = 4 4  -> Set background color to Blue.
//     Ps = 4 5  -> Set background color to Magenta.
//     Ps = 4 6  -> Set background color to Cyan.
//     Ps = 4 7  -> Set background color to White.
//     Ps = 4 9  -> Set background color to default (original).

//   If 16-color support is compiled, the following apply.  Assume
//   that xterm's resources are set so that the ISO color codes are
//   the first 8 of a set of 16.  Then the aixterm colors are the
//   bright versions of the ISO colors:
//     Ps = 9 0  -> Set foreground color to Black.
//     Ps = 9 1  -> Set foreground color to Red.
//     Ps = 9 2  -> Set foreground color to Green.
//     Ps = 9 3  -> Set foreground color to Yellow.
//     Ps = 9 4  -> Set foreground color to Blue.
//     Ps = 9 5  -> Set foreground color to Magenta.
//     Ps = 9 6  -> Set foreground color to Cyan.
//     Ps = 9 7  -> Set foreground color to White.
//     Ps = 1 0 0  -> Set background color to Black.
//     Ps = 1 0 1  -> Set background color to Red.
//     Ps = 1 0 2  -> Set background color to Green.
//     Ps = 1 0 3  -> Set background color to Yellow.
//     Ps = 1 0 4  -> Set background color to Blue.
//     Ps = 1 0 5  -> Set background color to Magenta.
//     Ps = 1 0 6  -> Set background color to Cyan.
//     Ps = 1 0 7  -> Set background color to White.

//   If xterm is compiled with the 16-color support disabled, it
//   supports the following, from rxvt:
//     Ps = 1 0 0  -> Set foreground and background color to
//     default.

//   If 88- or 256-color support is compiled, the following apply.
//     Ps = 3 8  ; 5  ; Ps -> Set foreground color to the second
//     Ps.
//     Ps = 4 8  ; 5  ; Ps -> Set background color to the second
//     Ps.
Terminal.prototype.charAttributes = function(params) {
	// Optimize a single SGR0.
	if (params.length === 1 && params[0] === 0) {
		this.curAttr = this.defAttr;
		return;
	}
	
	var l = params.length
		, i = 0
		, flags = this.curAttr >> 18
		, fg = (this.curAttr >> 9) & 0x1ff
		, bg = this.curAttr & 0x1ff
		, p;
	
	for (; i < l; i++) {
		p = params[i];
		if (p >= 30 && p <= 37) {
			// fg color 8
			fg = p - 30;
		} else if (p >= 40 && p <= 47) {
			// bg color 8
			bg = p - 40;
		} else if (p >= 90 && p <= 97) {
			// fg color 16
			p += 8;
			fg = p - 90;
		} else if (p >= 100 && p <= 107) {
			// bg color 16
			p += 8;
			bg = p - 100;
		} else if (p === 0) {
			// default
			flags = this.defAttr >> 18;
			fg = (this.defAttr >> 9) & 0x1ff;
			bg = this.defAttr & 0x1ff;
			// flags = 0;
			// fg = 0x1ff;
			// bg = 0x1ff;
		} else if (p === 1) {
			// bold text
			flags |= 1;
		} else if (p === 4) {
			// underlined text
			flags |= 2;
		} else if (p === 5) {
			// blink
			flags |= 4;
		} else if (p === 7) {
			// inverse and positive
			// test with: echo -e '\e[31m\e[42mhello\e[7mworld\e[27mhi\e[m'
			flags |= 8;
		} else if (p === 8) {
			// invisible
			flags |= 16;
		} else if (p === 22) {
			// not bold
			flags &= ~1;
		} else if (p === 24) {
			// not underlined
			flags &= ~2;
		} else if (p === 25) {
			// not blink
			flags &= ~4;
		} else if (p === 27) {
			// not inverse
			flags &= ~8;
		} else if (p === 28) {
			// not invisible
			flags &= ~16;
		} else if (p === 39) {
			// reset fg
			fg = (this.defAttr >> 9) & 0x1ff;
		} else if (p === 49) {
			// reset bg
			bg = this.defAttr & 0x1ff;
		} else if (p === 38) {
			// fg color 256
			if (params[i + 1] === 2) {
				i += 2;
				fg = matchColor(
					params[i] & 0xff,
					params[i + 1] & 0xff,
					params[i + 2] & 0xff);
				if (fg === -1) fg = 0x1ff;
				i += 2;
			} else if (params[i + 1] === 5) {
				i += 2;
				p = params[i] & 0xff;
				fg = p;
			}
		} else if (p === 48) {
			// bg color 256
			if (params[i + 1] === 2) {
				i += 2;
				bg = matchColor(
					params[i] & 0xff,
					params[i + 1] & 0xff,
					params[i + 2] & 0xff);
				if (bg === -1) bg = 0x1ff;
				i += 2;
			} else if (params[i + 1] === 5) {
				i += 2;
				p = params[i] & 0xff;
				bg = p;
			}
		} else if (p === 100) {
			// reset fg/bg
			fg = (this.defAttr >> 9) & 0x1ff;
			bg = this.defAttr & 0x1ff;
		} else {
			this.error('Unknown SGR attribute: %d.', p);
		}
	}
	
	this.curAttr = (flags << 18) | (fg << 9) | bg;
};

// CSI Ps n  Device Status Report (DSR).
//     Ps = 5  -> Status Report.  Result (``OK'') is
//   CSI 0 n
//     Ps = 6  -> Report Cursor Position (CPR) [row;column].
//   Result is
//   CSI r ; c R
// CSI ? Ps n
//   Device Status Report (DSR, DEC-specific).
//     Ps = 6  -> Report Cursor Position (CPR) [row;column] as CSI
//     ? r ; c R (assumes page is zero).
//     Ps = 1 5  -> Report Printer status as CSI ? 1 0  n  (ready).
//     or CSI ? 1 1  n  (not ready).
//     Ps = 2 5  -> Report UDK status as CSI ? 2 0  n  (unlocked)
//     or CSI ? 2 1  n  (locked).
//     Ps = 2 6  -> Report Keyboard status as
//   CSI ? 2 7  ;  1  ;  0  ;  0  n  (North American).
//   The last two parameters apply to VT400 & up, and denote key-
//   board ready and LK01 respectively.
//     Ps = 5 3  -> Report Locator status as
//   CSI ? 5 3  n  Locator available, if compiled-in, or
//   CSI ? 5 0  n  No Locator, if not.
Terminal.prototype.deviceStatus = function(params) {
	if (!this.prefix) {
		switch (params[0]) {
			case 5:
				// status report
				this.send('\x1b[0n');
				break;
			case 6:
				// cursor position
				this.send('\x1b['
					+ (this.y + 1)
					+ ';'
					+ (this.x + 1)
					+ 'R');
				break;
		}
	} else if (this.prefix === '?') {
		// modern xterm doesnt seem to
		// respond to any of these except ?6, 6, and 5
		switch (params[0]) {
			case 6:
				// cursor position
				this.send('\x1b[?'
					+ (this.y + 1)
					+ ';'
					+ (this.x + 1)
					+ 'R');
				break;
			case 15:
				// no printer
				// this.send('\x1b[?11n');
				break;
			case 25:
				// dont support user defined keys
				// this.send('\x1b[?21n');
				break;
			case 26:
				// north american keyboard
				// this.send('\x1b[?27;1;0;0n');
				break;
			case 53:
				// no dec locator/mouse
				// this.send('\x1b[?50n');
				break;
		}
	}
};

/**
 * Additions
 */

// CSI Ps @
// Insert Ps (Blank) Character(s) (default = 1) (ICH).
Terminal.prototype.insertChars = function(params) {
	var param, row, j, ch;
	
	param = params[0];
	if (param < 1) param = 1;
	
	row = this.y + this.ybase;
	j = this.x;
	ch = [this.eraseAttr(), ' ']; // xterm
	
	while (param-- && j < this.cols) {
		this.lines[row].splice(j++, 0, ch);
		this.lines[row].pop();
	}
};

// CSI Ps E
// Cursor Next Line Ps Times (default = 1) (CNL).
// same as CSI Ps B ?
Terminal.prototype.cursorNextLine = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y += param;
	if (this.y >= this.rows) {
		this.y = this.rows - 1;
	}
	this.x = 0;
};

// CSI Ps F
// Cursor Preceding Line Ps Times (default = 1) (CNL).
// reuse CSI Ps A ?
Terminal.prototype.cursorPrecedingLine = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y -= param;
	if (this.y < 0) this.y = 0;
	this.x = 0;
};

// CSI Ps G
// Cursor Character Absolute  [column] (default = [row,1]) (CHA).
Terminal.prototype.cursorCharAbsolute = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.x = param - 1;
};

// CSI Ps L
// Insert Ps Line(s) (default = 1) (IL).
Terminal.prototype.insertLines = function(params) {
	var param, row, j;
	
	param = params[0];
	if (param < 1) param = 1;
	row = this.y + this.ybase;
	
	j = this.rows - 1 - this.scrollBottom;
	j = this.rows - 1 + this.ybase - j + 1;
	
	while (param--) {
		// test: echo -e '\e[44m\e[1L\e[0m'
		// blankLine(true) - xterm/linux behavior
		this.lines.splice(row, 0, this.blankLine(true));
		this.lines.splice(j, 1);
	}
	
	// this.maxRange();
	this.updateRange(this.y);
	this.updateRange(this.scrollBottom);
};

// CSI Ps M
// Delete Ps Line(s) (default = 1) (DL).
Terminal.prototype.deleteLines = function(params) {
	var param, row, j;
	
	param = params[0];
	if (param < 1) param = 1;
	row = this.y + this.ybase;
	
	j = this.rows - 1 - this.scrollBottom;
	j = this.rows - 1 + this.ybase - j;
	
	while (param--) {
		// test: echo -e '\e[44m\e[1M\e[0m'
		// blankLine(true) - xterm/linux behavior
		this.lines.splice(j + 1, 0, this.blankLine(true));
		this.lines.splice(row, 1);
	}
	
	// this.maxRange();
	this.updateRange(this.y);
	this.updateRange(this.scrollBottom);
};

// CSI Ps P
// Delete Ps Character(s) (default = 1) (DCH).
Terminal.prototype.deleteChars = function(params) {
	var param, row, ch;
	
	param = params[0];
	if (param < 1) param = 1;
	
	row = this.y + this.ybase;
	ch = [this.eraseAttr(), ' ']; // xterm
	
	while (param--) {
		this.lines[row].splice(this.x, 1);
		this.lines[row].push(ch);
	}
};

// CSI Ps X
// Erase Ps Character(s) (default = 1) (ECH).
Terminal.prototype.eraseChars = function(params) {
	var param, row, j, ch;
	
	param = params[0];
	if (param < 1) param = 1;
	
	row = this.y + this.ybase;
	j = this.x;
	ch = [this.eraseAttr(), ' ']; // xterm
	
	while (param-- && j < this.cols) {
		this.lines[row][j++] = ch;
	}
};

// CSI Pm `  Character Position Absolute
//   [column] (default = [row,1]) (HPA).
Terminal.prototype.charPosAbsolute = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.x = param - 1;
	if (this.x >= this.cols) {
		this.x = this.cols - 1;
	}
};

// 141 61 a * HPR -
// Horizontal Position Relative
// reuse CSI Ps C ?
Terminal.prototype.HPositionRelative = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.x += param;
	if (this.x >= this.cols) {
		this.x = this.cols - 1;
	}
};

// CSI Ps c  Send Device Attributes (Primary DA).
//     Ps = 0  or omitted -> request attributes from terminal.  The
//     response depends on the decTerminalID resource setting.
//     -> CSI ? 1 ; 2 c  (``VT100 with Advanced Video Option'')
//     -> CSI ? 1 ; 0 c  (``VT101 with No Options'')
//     -> CSI ? 6 c  (``VT102'')
//     -> CSI ? 6 0 ; 1 ; 2 ; 6 ; 8 ; 9 ; 1 5 ; c  (``VT220'')
//   The VT100-style response parameters do not mean anything by
//   themselves.  VT220 parameters do, telling the host what fea-
//   tures the terminal supports:
//     Ps = 1  -> 132-columns.
//     Ps = 2  -> Printer.
//     Ps = 6  -> Selective erase.
//     Ps = 8  -> User-defined keys.
//     Ps = 9  -> National replacement character sets.
//     Ps = 1 5  -> Technical characters.
//     Ps = 2 2  -> ANSI color, e.g., VT525.
//     Ps = 2 9  -> ANSI text locator (i.e., DEC Locator mode).
// CSI > Ps c
//   Send Device Attributes (Secondary DA).
//     Ps = 0  or omitted -> request the terminal's identification
//     code.  The response depends on the decTerminalID resource set-
//     ting.  It should apply only to VT220 and up, but xterm extends
//     this to VT100.
//     -> CSI  > Pp ; Pv ; Pc c
//   where Pp denotes the terminal type
//     Pp = 0  -> ``VT100''.
//     Pp = 1  -> ``VT220''.
//   and Pv is the firmware version (for xterm, this was originally
//   the XFree86 patch number, starting with 95).  In a DEC termi-
//   nal, Pc indicates the ROM cartridge registration number and is
//   always zero.
// More information:
//   xterm/charproc.c - line 2012, for more information.
//   vim responds with ^[[?0c or ^[[?1c after the terminal's response (?)
Terminal.prototype.sendDeviceAttributes = function(params) {
	if (params[0] > 0) return;
	
	if (!this.prefix) {
		if (this.is('xterm')
			|| this.is('rxvt-unicode')
			|| this.is('screen')) {
			this.send('\x1b[?1;2c');
		} else if (this.is('linux')) {
			this.send('\x1b[?6c');
		}
	} else if (this.prefix === '>') {
		// xterm and urxvt
		// seem to spit this
		// out around ~370 times (?).
		if (this.is('xterm')) {
			this.send('\x1b[>0;276;0c');
		} else if (this.is('rxvt-unicode')) {
			this.send('\x1b[>85;95;0c');
		} else if (this.is('linux')) {
			// not supported by linux console.
			// linux console echoes parameters.
			this.send(params[0] + 'c');
		} else if (this.is('screen')) {
			this.send('\x1b[>83;40003;0c');
		}
	}
};

// CSI Pm d
// Line Position Absolute  [row] (default = [1,column]) (VPA).
Terminal.prototype.linePosAbsolute = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y = param - 1;
	if (this.y >= this.rows) {
		this.y = this.rows - 1;
	}
};

// 145 65 e * VPR - Vertical Position Relative
// reuse CSI Ps B ?
Terminal.prototype.VPositionRelative = function(params) {
	var param = params[0];
	if (param < 1) param = 1;
	this.y += param;
	if (this.y >= this.rows) {
		this.y = this.rows - 1;
	}
};

// CSI Ps ; Ps f
//   Horizontal and Vertical Position [row;column] (default =
//   [1,1]) (HVP).
Terminal.prototype.HVPosition = function(params) {
	if (params[0] < 1) params[0] = 1;
	if (params[1] < 1) params[1] = 1;
	
	this.y = params[0] - 1;
	if (this.y >= this.rows) {
		this.y = this.rows - 1;
	}
	
	this.x = params[1] - 1;
	if (this.x >= this.cols) {
		this.x = this.cols - 1;
	}
};

// CSI Pm h  Set Mode (SM).
//     Ps = 2  -> Keyboard Action Mode (AM).
//     Ps = 4  -> Insert Mode (IRM).
//     Ps = 1 2  -> Send/receive (SRM).
//     Ps = 2 0  -> Automatic Newline (LNM).
// CSI ? Pm h
//   DEC Private Mode Set (DECSET).
//     Ps = 1  -> Application Cursor Keys (DECCKM).
//     Ps = 2  -> Designate USASCII for character sets G0-G3
//     (DECANM), and set VT100 mode.
//     Ps = 3  -> 132 Column Mode (DECCOLM).
//     Ps = 4  -> Smooth (Slow) Scroll (DECSCLM).
//     Ps = 5  -> Reverse Video (DECSCNM).
//     Ps = 6  -> Origin Mode (DECOM).
//     Ps = 7  -> Wraparound Mode (DECAWM).
//     Ps = 8  -> Auto-repeat Keys (DECARM).
//     Ps = 9  -> Send Mouse X & Y on button press.  See the sec-
//     tion Mouse Tracking.
//     Ps = 1 0  -> Show toolbar (rxvt).
//     Ps = 1 2  -> Start Blinking Cursor (att610).
//     Ps = 1 8  -> Print form feed (DECPFF).
//     Ps = 1 9  -> Set print extent to full screen (DECPEX).
//     Ps = 2 5  -> Show Cursor (DECTCEM).
//     Ps = 3 0  -> Show scrollbar (rxvt).
//     Ps = 3 5  -> Enable font-shifting functions (rxvt).
//     Ps = 3 8  -> Enter Tektronix Mode (DECTEK).
//     Ps = 4 0  -> Allow 80 -> 132 Mode.
//     Ps = 4 1  -> more(1) fix (see curses resource).
//     Ps = 4 2  -> Enable Nation Replacement Character sets (DECN-
//     RCM).
//     Ps = 4 4  -> Turn On Margin Bell.
//     Ps = 4 5  -> Reverse-wraparound Mode.
//     Ps = 4 6  -> Start Logging.  This is normally disabled by a
//     compile-time option.
//     Ps = 4 7  -> Use Alternate Screen Buffer.  (This may be dis-
//     abled by the titeInhibit resource).
//     Ps = 6 6  -> Application keypad (DECNKM).
//     Ps = 6 7  -> Backarrow key sends backspace (DECBKM).
//     Ps = 1 0 0 0  -> Send Mouse X & Y on button press and
//     release.  See the section Mouse Tracking.
//     Ps = 1 0 0 1  -> Use Hilite Mouse Tracking.
//     Ps = 1 0 0 2  -> Use Cell Motion Mouse Tracking.
//     Ps = 1 0 0 3  -> Use All Motion Mouse Tracking.
//     Ps = 1 0 0 4  -> Send FocusIn/FocusOut events.
//     Ps = 1 0 0 5  -> Enable Extended Mouse Mode.
//     Ps = 1 0 1 0  -> Scroll to bottom on tty output (rxvt).
//     Ps = 1 0 1 1  -> Scroll to bottom on key press (rxvt).
//     Ps = 1 0 3 4  -> Interpret "meta" key, sets eighth bit.
//     (enables the eightBitInput resource).
//     Ps = 1 0 3 5  -> Enable special modifiers for Alt and Num-
//     Lock keys.  (This enables the numLock resource).
//     Ps = 1 0 3 6  -> Send ESC   when Meta modifies a key.  (This
//     enables the metaSendsEscape resource).
//     Ps = 1 0 3 7  -> Send DEL from the editing-keypad Delete
//     key.
//     Ps = 1 0 3 9  -> Send ESC  when Alt modifies a key.  (This
//     enables the altSendsEscape resource).
//     Ps = 1 0 4 0  -> Keep selection even if not highlighted.
//     (This enables the keepSelection resource).
//     Ps = 1 0 4 1  -> Use the CLIPBOARD selection.  (This enables
//     the selectToClipboard resource).
//     Ps = 1 0 4 2  -> Enable Urgency window manager hint when
//     Control-G is received.  (This enables the bellIsUrgent
//     resource).
//     Ps = 1 0 4 3  -> Enable raising of the window when Control-G
//     is received.  (enables the popOnBell resource).
//     Ps = 1 0 4 7  -> Use Alternate Screen Buffer.  (This may be
//     disabled by the titeInhibit resource).
//     Ps = 1 0 4 8  -> Save cursor as in DECSC.  (This may be dis-
//     abled by the titeInhibit resource).
//     Ps = 1 0 4 9  -> Save cursor as in DECSC and use Alternate
//     Screen Buffer, clearing it first.  (This may be disabled by
//     the titeInhibit resource).  This combines the effects of the 1
//     0 4 7  and 1 0 4 8  modes.  Use this with terminfo-based
//     applications rather than the 4 7  mode.
//     Ps = 1 0 5 0  -> Set terminfo/termcap function-key mode.
//     Ps = 1 0 5 1  -> Set Sun function-key mode.
//     Ps = 1 0 5 2  -> Set HP function-key mode.
//     Ps = 1 0 5 3  -> Set SCO function-key mode.
//     Ps = 1 0 6 0  -> Set legacy keyboard emulation (X11R6).
//     Ps = 1 0 6 1  -> Set VT220 keyboard emulation.
//     Ps = 2 0 0 4  -> Set bracketed paste mode.
// Modes:
//   http://vt100.net/docs/vt220-rm/chapter4.html
Terminal.prototype.setMode = function(params) {
	if (typeof params === 'object') {
		var l = params.length
			, i = 0;
		
		for (; i < l; i++) {
			this.setMode(params[i]);
		}
		
		return;
	}
	
	if (!this.prefix) {
		switch (params) {
			case 4:
				this.insertMode = true;
				break;
			case 20:
				//this.convertEol = true;
				break;
		}
	} else if (this.prefix === '?') {
		switch (params) {
			case 1:
				this.applicationCursor = true;
				break;
			case 2:
				this.setgCharset(0, Terminal.charsets.US);
				this.setgCharset(1, Terminal.charsets.US);
				this.setgCharset(2, Terminal.charsets.US);
				this.setgCharset(3, Terminal.charsets.US);
				// set VT100 mode here
				break;
			case 3: // 132 col mode
				this.savedCols = this.cols;
				this.resize(132, this.rows);
				break;
			case 6:
				this.originMode = true;
				break;
			case 7:
				this.wraparoundMode = true;
				break;
			case 12:
				// this.cursorBlink = true;
				break;
			case 66:
				this.log('Serial port requested application keypad.');
				this.applicationKeypad = true;
				break;
			case 9: // X10 Mouse
			// no release, no motion, no wheel, no modifiers.
			case 1000: // vt200 mouse
			// no motion.
			// no modifiers, except control on the wheel.
			case 1002: // button event mouse
			case 1003: // any event mouse
				// any event - sends motion events,
				// even if there is no button held down.
				this.x10Mouse = params === 9;
				this.vt200Mouse = params === 1000;
				this.normalMouse = params > 1000;
				this.mouseEvents = true;
				this.log('Binding to mouse events.');
				break;
			case 1004: // send focusin/focusout events
				// focusin: ^[[I
				// focusout: ^[[O
				this.sendFocus = true;
				break;
			case 1005: // utf8 ext mode mouse
				this.utfMouse = true;
				// for wide terminals
				// simply encodes large values as utf8 characters
				break;
			case 1006: // sgr ext mode mouse
				this.sgrMouse = true;
				// for wide terminals
				// does not add 32 to fields
				// press: ^[[<b;x;yM
				// release: ^[[<b;x;ym
				break;
			case 1015: // urxvt ext mode mouse
				this.urxvtMouse = true;
				// for wide terminals
				// numbers for fields
				// press: ^[[b;x;yM
				// motion: ^[[b;x;yT
				break;
			case 25: // show cursor
				this.cursorHidden = false;
				break;
			case 1049: // alt screen buffer cursor
				//this.saveCursor();
				// FALL-THROUGH
			case 47: // alt screen buffer
			case 1047: // alt screen buffer
				if (!this.normal) {
					var normal = {
						lines: this.lines,
						ybase: this.ybase,
						ydisp: this.ydisp,
						x: this.x,
						y: this.y,
						scrollTop: this.scrollTop,
						scrollBottom: this.scrollBottom,
						tabs: this.tabs
						// XXX save charset(s) here?
						// charset: this.charset,
						// glevel: this.glevel,
						// charsets: this.charsets
					};
					this.reset();
					this.normal = normal;
					this.showCursor();
				}
				break;
		}
	}
};

// CSI Pm l  Reset Mode (RM).
//     Ps = 2  -> Keyboard Action Mode (AM).
//     Ps = 4  -> Replace Mode (IRM).
//     Ps = 1 2  -> Send/receive (SRM).
//     Ps = 2 0  -> Normal Linefeed (LNM).
// CSI ? Pm l
//   DEC Private Mode Reset (DECRST).
//     Ps = 1  -> Normal Cursor Keys (DECCKM).
//     Ps = 2  -> Designate VT52 mode (DECANM).
//     Ps = 3  -> 80 Column Mode (DECCOLM).
//     Ps = 4  -> Jump (Fast) Scroll (DECSCLM).
//     Ps = 5  -> Normal Video (DECSCNM).
//     Ps = 6  -> Normal Cursor Mode (DECOM).
//     Ps = 7  -> No Wraparound Mode (DECAWM).
//     Ps = 8  -> No Auto-repeat Keys (DECARM).
//     Ps = 9  -> Don't send Mouse X & Y on button press.
//     Ps = 1 0  -> Hide toolbar (rxvt).
//     Ps = 1 2  -> Stop Blinking Cursor (att610).
//     Ps = 1 8  -> Don't print form feed (DECPFF).
//     Ps = 1 9  -> Limit print to scrolling region (DECPEX).
//     Ps = 2 5  -> Hide Cursor (DECTCEM).
//     Ps = 3 0  -> Don't show scrollbar (rxvt).
//     Ps = 3 5  -> Disable font-shifting functions (rxvt).
//     Ps = 4 0  -> Disallow 80 -> 132 Mode.
//     Ps = 4 1  -> No more(1) fix (see curses resource).
//     Ps = 4 2  -> Disable Nation Replacement Character sets (DEC-
//     NRCM).
//     Ps = 4 4  -> Turn Off Margin Bell.
//     Ps = 4 5  -> No Reverse-wraparound Mode.
//     Ps = 4 6  -> Stop Logging.  (This is normally disabled by a
//     compile-time option).
//     Ps = 4 7  -> Use Normal Screen Buffer.
//     Ps = 6 6  -> Numeric keypad (DECNKM).
//     Ps = 6 7  -> Backarrow key sends delete (DECBKM).
//     Ps = 1 0 0 0  -> Don't send Mouse X & Y on button press and
//     release.  See the section Mouse Tracking.
//     Ps = 1 0 0 1  -> Don't use Hilite Mouse Tracking.
//     Ps = 1 0 0 2  -> Don't use Cell Motion Mouse Tracking.
//     Ps = 1 0 0 3  -> Don't use All Motion Mouse Tracking.
//     Ps = 1 0 0 4  -> Don't send FocusIn/FocusOut events.
//     Ps = 1 0 0 5  -> Disable Extended Mouse Mode.
//     Ps = 1 0 1 0  -> Don't scroll to bottom on tty output
//     (rxvt).
//     Ps = 1 0 1 1  -> Don't scroll to bottom on key press (rxvt).
//     Ps = 1 0 3 4  -> Don't interpret "meta" key.  (This disables
//     the eightBitInput resource).
//     Ps = 1 0 3 5  -> Disable special modifiers for Alt and Num-
//     Lock keys.  (This disables the numLock resource).
//     Ps = 1 0 3 6  -> Don't send ESC  when Meta modifies a key.
//     (This disables the metaSendsEscape resource).
//     Ps = 1 0 3 7  -> Send VT220 Remove from the editing-keypad
//     Delete key.
//     Ps = 1 0 3 9  -> Don't send ESC  when Alt modifies a key.
//     (This disables the altSendsEscape resource).
//     Ps = 1 0 4 0  -> Do not keep selection when not highlighted.
//     (This disables the keepSelection resource).
//     Ps = 1 0 4 1  -> Use the PRIMARY selection.  (This disables
//     the selectToClipboard resource).
//     Ps = 1 0 4 2  -> Disable Urgency window manager hint when
//     Control-G is received.  (This disables the bellIsUrgent
//     resource).
//     Ps = 1 0 4 3  -> Disable raising of the window when Control-
//     G is received.  (This disables the popOnBell resource).
//     Ps = 1 0 4 7  -> Use Normal Screen Buffer, clearing screen
//     first if in the Alternate Screen.  (This may be disabled by
//     the titeInhibit resource).
//     Ps = 1 0 4 8  -> Restore cursor as in DECRC.  (This may be
//     disabled by the titeInhibit resource).
//     Ps = 1 0 4 9  -> Use Normal Screen Buffer and restore cursor
//     as in DECRC.  (This may be disabled by the titeInhibit
//     resource).  This combines the effects of the 1 0 4 7  and 1 0
//     4 8  modes.  Use this with terminfo-based applications rather
//     than the 4 7  mode.
//     Ps = 1 0 5 0  -> Reset terminfo/termcap function-key mode.
//     Ps = 1 0 5 1  -> Reset Sun function-key mode.
//     Ps = 1 0 5 2  -> Reset HP function-key mode.
//     Ps = 1 0 5 3  -> Reset SCO function-key mode.
//     Ps = 1 0 6 0  -> Reset legacy keyboard emulation (X11R6).
//     Ps = 1 0 6 1  -> Reset keyboard emulation to Sun/PC style.
//     Ps = 2 0 0 4  -> Reset bracketed paste mode.
Terminal.prototype.resetMode = function(params) {
	if (typeof params === 'object') {
		var l = params.length
			, i = 0;
		
		for (; i < l; i++) {
			this.resetMode(params[i]);
		}
		
		return;
	}
	
	if (!this.prefix) {
		switch (params) {
			case 4:
				this.insertMode = false;
				break;
			case 20:
				//this.convertEol = false;
				break;
		}
	} else if (this.prefix === '?') {
		switch (params) {
			case 1:
				this.applicationCursor = false;
				break;
			case 3:
				if (this.cols === 132 && this.savedCols) {
					this.resize(this.savedCols, this.rows);
				}
				delete this.savedCols;
				break;
			case 6:
				this.originMode = false;
				break;
			case 7:
				this.wraparoundMode = false;
				break;
			case 12:
				// this.cursorBlink = false;
				break;
			case 66:
				this.log('Switching back to normal keypad.');
				this.applicationKeypad = false;
				break;
			case 9: // X10 Mouse
			case 1000: // vt200 mouse
			case 1002: // button event mouse
			case 1003: // any event mouse
				this.x10Mouse = false;
				this.vt200Mouse = false;
				this.normalMouse = false;
				this.mouseEvents = false;
				break;
			case 1004: // send focusin/focusout events
				this.sendFocus = false;
				break;
			case 1005: // utf8 ext mode mouse
				this.utfMouse = false;
				break;
			case 1006: // sgr ext mode mouse
				this.sgrMouse = false;
				break;
			case 1015: // urxvt ext mode mouse
				this.urxvtMouse = false;
				break;
			case 25: // hide cursor
				this.cursorHidden = true;
				break;
			case 1049: // alt screen buffer cursor
				// FALL-THROUGH
			case 47: // normal screen buffer
			case 1047: // normal screen buffer - clearing it first
				if (this.normal) {
					this.lines = this.normal.lines;
					this.ybase = this.normal.ybase;
					this.ydisp = this.normal.ydisp;
					this.x = this.normal.x;
					this.y = this.normal.y;
					this.scrollTop = this.normal.scrollTop;
					this.scrollBottom = this.normal.scrollBottom;
					this.tabs = this.normal.tabs;
					this.normal = null;
					// if (params === 1049) {
					//   this.x = this.savedX;
					//   this.y = this.savedY;
					// }
					this.refresh(0, this.rows - 1);
					this.showCursor();
				}
				break;
		}
	}
};

// CSI Ps ; Ps r
//   Set Scrolling Region [top;bottom] (default = full size of win-
//   dow) (DECSTBM).
// CSI ? Pm r
Terminal.prototype.setScrollRegion = function(params) {
	if (this.prefix) return;
	this.scrollTop = (params[0] || 1) - 1;
	this.scrollBottom = (params[1] || this.rows) - 1;
	this.x = 0;
	this.y = 0;
};

// CSI s
//   Save cursor (ANSI.SYS).
Terminal.prototype.saveCursor = function(params) {
	this.savedX = this.x;
	this.savedY = this.y;
};

// CSI u
//   Restore cursor (ANSI.SYS).
Terminal.prototype.restoreCursor = function(params) {
	this.x = this.savedX || 0;
	this.y = this.savedY || 0;
};

/**
 * Lesser Used
 */

// CSI Ps I
//   Cursor Forward Tabulation Ps tab stops (default = 1) (CHT).
Terminal.prototype.cursorForwardTab = function(params) {
	var param = params[0] || 1;
	while (param--) {
		this.x = this.nextStop();
	}
};

// CSI Ps S  Scroll up Ps lines (default = 1) (SU).
Terminal.prototype.scrollUp = function(params) {
	var param = params[0] || 1;
	while (param--) {
		this.lines.splice(this.ybase + this.scrollTop, 1);
		this.lines.splice(this.ybase + this.scrollBottom, 0, this.blankLine());
	}
	// this.maxRange();
	this.updateRange(this.scrollTop);
	this.updateRange(this.scrollBottom);
};

// CSI Ps T  Scroll down Ps lines (default = 1) (SD).
Terminal.prototype.scrollDown = function(params) {
	var param = params[0] || 1;
	while (param--) {
		this.lines.splice(this.ybase + this.scrollBottom, 1);
		this.lines.splice(this.ybase + this.scrollTop, 0, this.blankLine());
	}
	// this.maxRange();
	this.updateRange(this.scrollTop);
	this.updateRange(this.scrollBottom);
};

// CSI Ps Z  Cursor Backward Tabulation Ps tab stops (default = 1) (CBT).
Terminal.prototype.cursorBackwardTab = function(params) {
	var param = params[0] || 1;
	while (param--) {
		this.x = this.prevStop();
	}
};

// CSI Ps b  Repeat the preceding graphic character Ps times (REP).
Terminal.prototype.repeatPrecedingCharacter = function(params) {
	var param = params[0] || 1
		, line = this.lines[this.ybase + this.y]
		, ch = line[this.x - 1] || [this.defAttr, ' '];
	
	while (param--) line[this.x++] = ch;
};

// CSI Ps g  Tab Clear (TBC).
//     Ps = 0  -> Clear Current Column (default).
//     Ps = 3  -> Clear All.
// Potentially:
//   Ps = 2  -> Clear Stops on Line.
//   http://vt100.net/annarbor/aaa-ug/section6.html
Terminal.prototype.tabClear = function(params) {
	var param = params[0];
	if (param <= 0) {
		delete this.tabs[this.x];
	} else if (param === 3) {
		this.tabs = {};
	}
};

// CSI ! p   Soft terminal reset (DECSTR).
// http://vt100.net/docs/vt220-rm/table4-10.html
Terminal.prototype.softReset = function(params) {
	this.cursorHidden = false;
	this.insertMode = false;
	this.originMode = false;
	this.wraparoundMode = false; // autowrap
	this.applicationKeypad = false; // ?
	this.applicationCursor = false;
	this.scrollTop = 0;
	this.scrollBottom = this.rows - 1;
	this.curAttr = this.defAttr;
	this.x = this.y = 0; // ?
	this.charset = null;
	this.glevel = 0; // ??
	this.charsets = [null]; // ??
};

/**
 * Prefix/Select/Visual/Search Modes
 */

Terminal.prototype.copyBuffer = function(lines) {
	let out = [];
	lines = lines || this.lines;
	
	for (var y = 0; y < lines.length; y++) {
		out[y] = [];
		for (var x = 0; x < lines[y].length; x++) {
			out[y][x] = [lines[y][x][0], lines[y][x][1]];
		}
	}
	
	return out;
};

Terminal.prototype.getContent = function(){
	let lines,h,line;
	let out = '', buf = '', ch, x, y, xl, tmp;
	
	lines=this.lines;
	h=lines.length;
	for (y = 0; y < h; y++) {
		line=lines[y];
		xl = line.length - 1;
		for (x=0; x <= xl; x++) {
			ch = line[x][1];
			if (ch === ' ') {
				buf += ch;
				continue;
			}
			if (buf) {
				out += buf;
				buf = '';
			}
			out += ch;
			if (isWide(ch)) x++;
		}
		buf = '';
		out += '\n';
	}
	out=out.trim();
	return out;
};

Terminal.prototype.clear = function(text){
	let i;
	this.lines.splice(0);
	i=this.rows;
	while(i--) {
		this.lines.push(this.blankLine());
	}
	if(text) {
		this.write(text);
	}
};

Terminal.prototype.grabText = function(x1, x2, y1, y2) {
	var out = ''
		, buf = ''
		, ch
		, x
		, y
		, xl
		, tmp;
	
	if (y2 < y1) {
		tmp = x2;
		x2 = x1;
		x1 = tmp;
		tmp = y2;
		y2 = y1;
		y1 = tmp;
	}
	
	if (x2 < x1 && y1 === y2) {
		tmp = x2;
		x2 = x1;
		x1 = tmp;
	}
	
	for (y = y1; y <= y2; y++) {
		x = 0;
		xl = this.cols - 1;
		if (y === y1) {
			x = x1;
		}
		if (y === y2) {
			xl = x2;
		}
		for (; x <= xl; x++) {
			ch = this.lines[y][x][1];
			if (ch === ' ') {
				buf += ch;
				continue;
			}
			if (buf) {
				out += buf;
				buf = '';
			}
			out += ch;
			if (isWide(ch)) x++;
		}
		buf = '';
		out += '\n';
	}
	
	// If we're not at the end of the
	// line, don't add a newline.
	for (x = x2, y = y2; x < this.cols; x++) {
		if (this.lines[y][x][1] !== ' ') {
			out = out.slice(0, -1);
			break;
		}
	}
	
	return out;
};

/**
 * Character Sets
 */

Terminal.charsets = {};

// DEC Special Character and Line Drawing Set.
// http://vt100.net/docs/vt102-ug/table5-13.html
// A lot of curses apps use this if they see TERM=xterm.
// testing: echo -e '\e(0a\e(B'
// The xterm output sometimes seems to conflict with the
// reference above. xterm seems in line with the reference
// when running vttest however.
// The table below now uses xterm's output from vttest.
Terminal.charsets.SCLD = { // (0
	'`': '\u25c6', // '◆'
	'a': '\u2592', // '▒'
	'b': '\u0009', // '\t'
	'c': '\u000c', // '\f'
	'd': '\u000d', // '\r'
	'e': '\u000a', // '\n'
	'f': '\u00b0', // '°'
	'g': '\u00b1', // '±'
	'h': '\u2424', // '\u2424' (NL)
	'i': '\u000b', // '\v'
	'j': '\u2518', // '┘'
	'k': '\u2510', // '┐'
	'l': '\u250c', // '┌'
	'm': '\u2514', // '└'
	'n': '\u253c', // '┼'
	'o': '\u23ba', // '⎺'
	'p': '\u23bb', // '⎻'
	'q': '\u2500', // '─'
	'r': '\u23bc', // '⎼'
	's': '\u23bd', // '⎽'
	't': '\u251c', // '├'
	'u': '\u2524', // '┤'
	'v': '\u2534', // '┴'
	'w': '\u252c', // '┬'
	'x': '\u2502', // '│'
	'y': '\u2264', // '≤'
	'z': '\u2265', // '≥'
	'{': '\u03c0', // 'π'
	'|': '\u2260', // '≠'
	'}': '\u00a3', // '£'
	'~': '\u00b7'  // '·'
};

Terminal.charsets.UK = null; // (A
Terminal.charsets.US = null; // (B (USASCII)
Terminal.charsets.Dutch = null; // (4
Terminal.charsets.Finnish = null; // (C or (5
Terminal.charsets.French = null; // (R
Terminal.charsets.FrenchCanadian = null; // (Q
Terminal.charsets.German = null; // (K
Terminal.charsets.Italian = null; // (Y
Terminal.charsets.NorwegianDanish = null; // (E or (6
Terminal.charsets.Spanish = null; // (Z
Terminal.charsets.Swedish = null; // (H or (7
Terminal.charsets.Swiss = null; // (=
Terminal.charsets.ISOLatin = null; // /A

/**
 * Helpers
 */

function on(el, type, handler, capture) {
	el.addEventListener(type, handler, capture || false);
}

function off(el, type, handler, capture) {
	el.removeEventListener(type, handler, capture || false);
}

function cancel(ev) {
	if (ev.preventDefault) ev.preventDefault();
	ev.returnValue = false;
	if (ev.stopPropagation) ev.stopPropagation();
	ev.cancelBubble = true;
	return false;
}

function inherits(child, parent) {
	function F() {
		this.constructor = child;
	}
	F.prototype = parent.prototype;
	child.prototype = new F;
}

var String = this.String;
var setTimeout = this.setTimeout;
var setInterval = this.setInterval;

function indexOf(obj, el) {
	var i = obj.length;
	while (i--) {
		if (obj[i] === el) return i;
	}
	return -1;
}

function isWide(ch) {
	if (ch <= '\uff00') return false;
	return (ch >= '\uff01' && ch <= '\uffbe')
		|| (ch >= '\uffc2' && ch <= '\uffc7')
		|| (ch >= '\uffca' && ch <= '\uffcf')
		|| (ch >= '\uffd2' && ch <= '\uffd7')
		|| (ch >= '\uffda' && ch <= '\uffdc')
		|| (ch >= '\uffe0' && ch <= '\uffe6')
		|| (ch >= '\uffe8' && ch <= '\uffee');
}

function matchColor(r1, g1, b1) {
	var hash = (r1 << 16) | (g1 << 8) | b1;
	
	if (matchColor._cache[hash] != null) {
		return matchColor._cache[hash];
	}
	
	var ldiff = Infinity
		, li = -1
		, i = 0
		, c
		, r2
		, g2
		, b2
		, diff;
	
	for (; i < Terminal.vcolors.length; i++) {
		c = Terminal.vcolors[i];
		r2 = c[0];
		g2 = c[1];
		b2 = c[2];
		
		diff = matchColor.distance(r1, g1, b1, r2, g2, b2);
		
		if (diff === 0) {
			li = i;
			break;
		}
		
		if (diff < ldiff) {
			ldiff = diff;
			li = i;
		}
	}
	
	return matchColor._cache[hash] = li;
}

matchColor._cache = {};

// http://stackoverflow.com/questions/1633828
matchColor.distance = function(r1, g1, b1, r2, g2, b2) {
	return Math.pow(30 * (r1 - r2), 2)
		+ Math.pow(59 * (g1 - g2), 2)
		+ Math.pow(11 * (b1 - b2), 2);
};

function each(obj, iter, con) {
	if (obj.forEach) return obj.forEach(iter, con);
	for (var i = 0; i < obj.length; i++) {
		iter.call(con, obj[i], i, obj);
	}
}

function keys(obj) {
	return Object.keys(obj);
}

/**
 * Expose
 */

Terminal.EventEmitter = EventEmitter;
Terminal.Stream = Stream;
Terminal.inherits = inherits;
Terminal.on = on;
Terminal.off = off;
Terminal.cancel = cancel;

module.exports = Terminal;
