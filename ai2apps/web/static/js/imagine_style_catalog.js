(() => {
	'use strict';
	const catalog = [
	{
		"name":{"EN":"Realism","CN":"写实主义"},
		"styles":[
			{
				"name":{"EN":"Realism","CN":"写实主义"},
				"prompt": "ultra detailed, realistic photo, natural lighting, lifelike textures, cinematic look",
				"image":"Realism_256.png"
			},
			{
				"name":{"EN":"Photorealistic","CN":"照片写实"},
				"prompt": "photorealistic, DSLR quality, high resolution, sharp focus, natural colors",
				"image":"Photorealistic_256.png"
			},
			{
				"name":{"EN":"Hyperrealism","CN":"超写实"},
				"prompt": "hyperrealistic, 8k detail, microscopic texture, cinematic depth of field",
				"image":"Hyperrealism_256.png"
			},
			{
				"name":{"EN":"Documentary Photography","CN":"纪实摄影"},
				"prompt": "candid street photography, documentary style, real life scene, natural light",
				"image":"Documentary_256.png"
			},
			{
				"name":{"EN":"Film Photography","CN":"胶片摄影"},
				"prompt": "film photography, shallow depth of field, soft natural lighting, cinematic tones, 35mm grain, vintage color palette, slight lens flare, background softly blurred (bokeh), subtle imperfections, nostalgic mood, candid moment, realistic skin texture, natural shadows",
				"image":"FilmPhoto_256.png"
			},
			{
				"name":{"EN":"Polaroid","CN":"宝丽来"},
				"prompt": "polaroid photo, instant camera look, retro colors",
				"image":"Polaroid_256.png"
			},
			{
				"name":{"EN":"Black & White","CN":"黑白摄影"},
				"prompt": "dramatic black and white photography, high contrast, deep shadows",
				"image":"BlackWhite_256.png"
			},
			{
				"name":{"EN":"8-bit","CN":"8 位像素"},
				"prompt": "retro 8-bit pixel art, limited color palette, crisp blocky pixels, classic arcade game aesthetic",
				"image":"8bit_256.png"
			},
			{
				"name":{"EN":"Macro Photography","CN":"微距摄影"},
				"prompt": "macro photography, extremely detailed close-up, shallow depth of field, soft natural light, bokeh background",
				"image":"Macro_256.png"
			},
		]
	},
	{
		"name":{"EN":"Art","CN":"艺术绘画"},
		"styles":[
			{
				"name":{"EN":"Oil Painting","CN":"油画"},
				"prompt": "oil painting on canvas, visible brush strokes, classic fine art style",
				"image":"OilPainting_256.png"
			},
			{
				"name":{"EN":"Watercolor","CN":"水彩画"},
				"prompt": "delicate watercolor wash, soft edges, light paper texture",
				"image":"Watercolor_256.png"
			},
			{
				"name":{"EN":"Acrylic Painting","CN":"丙烯画"},
				"prompt": "acrylic painting with vibrant colors and layered texture",
				"image":"Acrylic_256.png"
			},
			{
				"name":{"EN":"Charcoal Drawing","CN":"木炭画"},
				"prompt": "expressive charcoal drawing, rough strokes, deep shadows",
				"image":"Charcoal_256.png"
			},
			{
				"name":{"EN":"Ink Wash Painting","CN":"水墨画"},
				"prompt": "traditional Chinese ink wash, sumi-e brush style, fluid and minimalistic",
				"image":"InkWash_256.png"
			},
			{
				"name":{"EN":"Ukiyo-e","CN":"浮世绘"},
				"prompt": "ukiyo-e Japanese woodblock print, Edo period style, Hokusai",
				"image":"UkiyoE_256.png"
			},
			{
				"name":{"EN":"Rococo","CN":"洛可可"},
				"prompt": "rococo painting, ornate elegance, pastel colors",
				"image":"Rococo_256.png"
			},
			{
				"name":{"EN":"Baroque","CN":"巴洛克"},
				"prompt": "baroque art, dramatic light, ornate decoration",
				"image":"Baroque_256.png"
			},
			{
				"name":{"EN":"Gothic","CN":"哥特风格"},
				"prompt": "gothic architecture, dark fantasy, medieval mood",
				"image":"Gothic_256.png"
			},
			{
				"name":{"EN":"Woodcut Print","CN":"板画"},
				"prompt": "woodcut print style, bold black outlines, vintage print texture",
				"image":"Woodcut_256.png"
			},
			{
				"name":{"EN":"Impressionism","CN":"印象派"},
				"prompt": "impressionist painting with loose brush strokes, vibrant colors, Claude Monet style",
				"image":"Impressionism_256.png"
			},
			{
				"name":{"EN":"Post-Impressionism","CN":"后印象派"},
				"prompt": "post-impressionist painting with bold outlines and expressive colors",
				"image":"PostImpressionism_256.png"
			},
			{
				"name":{"EN":"Cubism","CN":"立体派"},
				"prompt": "cubist abstraction, geometric shapes, Pablo Picasso style",
				"image":"Cubism_256.png"
			},
			{
				"name":{"EN":"Surrealism","CN":"超现实主义"},
				"prompt": "surreal dreamscape, impossible objects, Salvador Dali style",
				"image":"Surrealism_256.png"
			},
			{
				"name":{"EN":"Pop Art","CN":"波普艺术"},
				"prompt": "pop art, bold comic outlines, vibrant flat colors, Roy Lichtenstein style",
				"image":"PopArt_256.png"
			},
			{
				"name":{"EN":"Art Nouveau","CN":"新艺术风格"},
				"prompt": "art nouveau with flowing lines, floral patterns, Alphonse Mucha style",
				"image":"ArtNouveau_256.png"
			},
			{
				"name":{"EN":"Art Deco","CN":"装饰艺术"},
				"prompt": "art deco style, geometric elegance, metallic colors",
				"image":"ArtDeco_256.png"
			},
			{
				"name":{"EN":"Graffiti","CN":"都市涂鸦"},
				"prompt": "street graffiti art, spray paint texture, urban wall",
				"image":"Graffiti_256.png"
			}
		]
	},
	{
		"name":{"EN":"Modern / Digital","CN":"现代视觉"},
		"styles":[
			{
				"name":{"EN":"Vector Art","CN":"矢量插画"},
				"prompt": "flat vector illustration, clean lines, minimal gradient, Adobe Illustrator style",
				"image":"VectorArt_256.png"
			},
			{
				"name":{"EN":"Isometric Illustration","CN":"等距插画"},
				"prompt": "isometric illustration with clean geometry and pastel colors",
				"image":"Isometric_256.png"
			},
			{
				"name":{"EN":"Pixel Art","CN":"像素画"},
				"prompt": "retro pixel art, 16-bit game graphics, vibrant low-res pixels",
				"image":"PixelArt_256.png"
			},
			{
				"name":{"EN":"Low Poly","CN":"低多边形"},
				"prompt": "low poly 3D style, geometric shapes, flat shading",
				"image":"LowPoly_256.png"
			},
			{
				"name":{"EN":"Cyberpunk","CN":"赛博朋克"},
				"prompt": "cyberpunk neon lights, futuristic cityscape, dystopian atmosphere",
				"image":"Cyberpunk_256.png"
			},
			{
				"name":{"EN":"Vaporwave","CN":"蒸汽波"},
				"prompt": "vaporwave style, neon grid, retro computer aesthetic, 80s nostalgia",
				"image":"Vaporwave_256.png"
			},
			{
				"name":{"EN":"Papercut Art","CN":"纸艺剪影"},
				"prompt": "layered papercut art, shadows, handcrafted look",
				"image":"Papercut_256.png"
			},
			{
				"name":{"EN":"Synthwave","CN":"合成波"},
				"prompt": "synthwave neon colors, sunset gradient, retro futuristic",
				"image":"Synthwave_256.png"
			},
			{
				"name":{"EN":"Steampunk","CN":"蒸汽朋克"},
				"prompt": "steampunk style, brass gears, Victorian sci-fi machines",
				"image":"Steampunk_256.png"
			},
			{
				"name":{"EN":"Digital Painting","CN":"数字绘画"},
				"prompt": "highly detailed digital painting, vivid colors, fantasy artstation style",
				"image":"DigitalPainting_256.png"
			},
			{
				"name":{"EN":"Flat Design","CN":"扁平化"},
				"prompt": "minimal flat design, clean vector shapes, bold colors",
				"image":"FlatDesign_256.png"
			},
			{
				"name":{"EN":"Minimalism","CN":"极简主义"},
				"prompt": "minimalism, simple shapes, white space, elegant composition",
				"image":"Minimalism_256.png"
			},
			{
				"name":{"EN":"Glitch Art","CN":"故障艺术"},
				"prompt": "glitch art, digital distortion, VHS static, RGB shift",
				"image":"GlitchArt_256.png"
			}
		]
	},
	{
		"name":{"EN":"Game/Anime","CN":"游戏/动漫"},
		"styles":[
			{
				"name":{"EN":"Anime","CN":"日式动漫"},
				"prompt": "anime style, cel shading, vibrant colors, dynamic action pose",
				"image":"Anime_256.png"
			},
			{
				"name":{"EN":"Manga","CN":"漫画"},
				"prompt": "black and white manga panel, screentone shading, expressive lines",
				"image":"Manga_256.png"
			},
			{
				"name":{"EN":"Comic Book","CN":"美式漫画"},
				"prompt": "american comic book style, bold ink outlines, halftone dots",
				"image":"ComicBook_256.png"
			},
			{
				"name":{"EN":"Pixar","CN":"皮克斯动画"},
				"prompt": "pixar style 3D animated character, expressive big eyes, soft rounded shapes, cinematic lighting, vibrant colors, warm and whimsical atmosphere, detailed textures, rendered in Pixar quality",
				"image":"Pixar_256.png"
			},
			{
				"name":{"EN":"Clash Royale","CN":"皇室冲突"},
				"prompt": "3D cartoon style, vibrant saturated colors, soft rounded characters, stylized medieval fantasy environment, smooth plastic-like materials, dynamic lighting, high contrast shadows, mobile game graphics, cute but epic, clash royale style",
				"image":"ClashRoyale_256.png"
			},
			{
				"name":{"EN":"Disney Style","CN":"迪士尼"},
				"prompt": "disney animation style, cute characters, soft painterly shading",
				"image":"Disney_256.png"
			},
			{
				"name":{"EN":"Ghibli Style","CN":"吉卜力"},
				"prompt": "ghibli studio style, whimsical scenery, soft hand-drawn feel",
				"image":"Ghibli_256.png"
			},
			{
				"name":{"EN":"Cartoon","CN":"卡通"},
				"prompt": "fun cartoon illustration, exaggerated expressions, bright colors",
				"image":"Cartoon_256.png"
			},
			{
				"name":{"EN":"Doodle","CN":"涂鸦"},
				"prompt": "simple hand-drawn doodle style, playful lines, casual sketch, minimal detail",
				"image":"Doodle_256.png"
			},
			{
				"name":{"EN":"3D Render","CN":"3D 渲染"},
				"prompt": "cinematic 3D render, ray tracing, highly detailed CGI",
				"image":"3DRender_256.png"
			},
			{
				"name":{"EN":"Fantasy RPG","CN":"奇幻 RPG"},
				"prompt": "fantasy RPG game illustration, magic, epic scenery",
				"image":"FantasyRPG_256.png"
			}
		]
	}
];

	const slug = value => String(value || '')
		.replace(/_256\.png$/i, '')
		.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
		.replace(/[^a-z0-9]+/gi, '-')
		.replace(/^-|-$/g, '')
		.toLowerCase();
	const assetRoot = typeof document !== 'undefined' && document.currentScript?.src
		? new URL('../images/imagine-studio/styles/', document.currentScript.src).href
		: '';
	window.IMAGINE_STYLE_CATALOG = catalog.map(category => ({
		id: slug(category.name.EN),
		name: category.name,
		styles: category.styles.map(style => ({
			...style,
			id: slug(style.image),
			image: assetRoot
				? new URL(style.image.replace(/\.png$/i, '.webp'), assetRoot).href
				: `/static/images/imagine-studio/styles/${style.image.replace(/\.png$/i, '.webp')}`,
		})),
	}));
})();
