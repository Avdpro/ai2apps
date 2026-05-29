// MirrorSelector.mjs
//
// 为 conda, pip, npm, brew 等包管理器自动选择最快的镜像源。
// 核心测速逻辑参考 chsrc (https://github.com/RubyMetric/chsrc) 的 auto_select_mirror，
// 通过 curl 对每个候选镜像做模糊测速，选出速度最快的一个。
//
// 与 chsrc 的区别：
//   - chsrc 直接写入配置文件（.condarc, .npmrc 等）
//   - 本模块返回最佳 URL + 生成 export 命令，由调用方通过环境变量设置（参考 ModelDeploy.js 的 SetMirror）

import { execSync } from 'child_process';

// ═══════════════════════════════════════════════════════════════
// 镜像站定义（含模糊测速 URL）
// ═══════════════════════════════════════════════════════════════
const MIRRORS = {
	aa: {
		abbr: 'AI2APPS',
		name: { cn: 'AI2APPS', en: 'AI2APPS' },
		speedUrl: 'https://update-cn.continue-ai.com/pip/torch/2.12.0/torch-2.12.0-cp311-cp311-macosx_14_0_arm64.whl',
	},
	tsinghua: {
		abbr: 'Tsinghua',
		name: { cn: '清华大学', en: 'Tsinghua University' },
		speedUrl: 'https://mirrors.tuna.tsinghua.edu.cn/speedtest/1000mb.bin',
	},
	bfsu: {
		abbr: 'BFSU',
		name: { cn: '北京外国语大学', en: 'Beijing Foreign Studies University' },
		speedUrl: 'https://mirrors.bfsu.edu.cn/speedtest/1000mb.bin',
	},
	ustc: {
		abbr: 'USTC',
		name: { cn: '中国科学技术大学', en: 'University of Science and Technology of China' },
		speedUrl: 'https://mirrors.ustc.edu.cn/speedtest/1000mb.bin',
	},
	aliyun: {
		abbr: 'Aliyun',
		name: { cn: '阿里巴巴开源镜像站', en: 'Alibaba Cloud Mirror' },
		speedUrl: 'https://mirrors.aliyun.com/ubuntu/ls-lR.gz', // ~31MB
	},
	tencent: {
		abbr: 'Tencent',
		name: { cn: '腾讯软件源', en: 'Tencent Software Source' },
		speedUrl: 'https://mirrors.cloud.tencent.com/mariadb/mariadb-12.1.0/winx64-packages/mariadb-12.1.0-winx64-debugsymbols.zip', // ~110MB
	},
	sjtug: {
		abbr: 'SJTUG',
		name: { cn: '上海交通大学 (SJTUG)', en: 'Shanghai Jiao Tong University (SJTUG)' },
		speedUrl: 'https://mirrors.sjtug.sjtu.edu.cn/ctan/systems/texlive/Images/texlive.iso',
	},
	nju: {
		abbr: 'NJU',
		name: { cn: '南京大学', en: 'Nanjing University' },
		speedUrl: 'https://mirrors.nju.edu.cn/archlinux/iso/latest/archlinux-x86_64.iso',
	},
	pku: {
		abbr: 'PKU',
		name: { cn: '北京大学', en: 'Peking University' },
		speedUrl: 'https://mirrors.pku.edu.cn/ubuntu-releases/18.04/ubuntu-18.04.6-desktop-amd64.iso',
	},
	bjtu: {
		abbr: 'BJTU',
		name: { cn: '北京交通大学', en: 'Beijing Jiaotong University' },
		speedUrl: 'https://mirror.bjtu.edu.cn/archlinux/iso/latest/archlinux-x86_64.iso',
	},
	zju: {
		abbr: 'ZJU',
		name: { cn: '浙江大学', en: 'Zhejiang University' },
		speedUrl: 'https://mirrors.zju.edu.cn/ubuntu-releases/18.04/ubuntu-18.04.6-desktop-amd64.iso',
	},
	jlu: {
		abbr: 'JLU',
		name: { cn: '吉林大学', en: 'Jilin University' },
		speedUrl: 'https://mirrors.jlu.edu.cn/_static/speedtest.bin',
	},
	njtech: {
		abbr: 'NJTech',
		name: { cn: '南京工业大学', en: 'Nanjing Tech University' },
		speedUrl: 'https://mirrors.njtech.edu.cn/ubuntu-releases/18.04/ubuntu-18.04.6-desktop-amd64.iso',
	},
	nyist: {
		abbr: 'NYIST',
		name: { cn: '南阳理工学院', en: 'Nanyang Institute of Technology' },
		speedUrl: 'https://mirror.nyist.edu.cn/ubuntu-releases/18.04/ubuntu-18.04.6-desktop-amd64.iso',
	},
	npmmirror: {
		abbr: 'npmmirror',
		name: { cn: 'npmmirror (阿里云赞助)', en: 'npmmirror (Sponsored by Alibaba)' },
		speedUrl: 'https://registry.npmmirror.com/@tensorflow/tfjs/-/tfjs-4.22.0.tgz', // ~29MB
	},
	// 各工具的上游默认源
	pypi_upstream: {
		abbr: 'PyPI',
		name: { cn: 'PyPI 官方源', en: 'PyPI Official' },
		speedUrl: 'https://files.pythonhosted.org/packages/fa/80/eb88edc2e2b11cd2dd2e56f1c80b5784d11d6e6b7f04a1145df64df40065/opencv_python-4.12.0.88-cp37-abi3-win_amd64.whl',
	},
	npmjs_upstream: {
		abbr: 'npmjs',
		name: { cn: 'npm 官方源', en: 'npm Official' },
		speedUrl: 'https://registry.npmjs.org/@tensorflow/tfjs/-/tfjs-4.22.0.tgz',
	},
	anaconda_upstream: {
		abbr: 'Anaconda',
		name: { cn: 'Anaconda 官方源', en: 'Anaconda Official' },
		speedUrl: 'https://repo.anaconda.com/pkgs/main/linux-64/python-3.12.0-h996f2a0_0.conda',
	},
	brew_upstream: {
		abbr: 'GitHub',
		name: { cn: 'Homebrew', en: 'Homebrew Official' },
		speedUrl: 'https://codeload.github.com/Homebrew/brew/zip/refs/heads/master',
	},
	github_upstream: {
		abbr: 'GitHub',
		name: { cn: 'GitHub 官方', en: 'Github Official' },
		speedUrl: 'https://github.com/stilleshan/dockerfiles/archive/master.zip',
	},
	ghfast: {
		abbr: 'ghfast',
		name: { cn: 'ghfast.top', en: 'ghfast.top' },
		speedUrl: 'https://ghfast.top/https://github.com/stilleshan/dockerfiles/archive/master.zip',
	},
};


// ═══════════════════════════════════════════════════════════════
// 工具定义：每个包管理器在各镜像上的源 URL
// ═══════════════════════════════════════════════════════════════

const TOOLS = {
	pip: {
		mirrors: {
			aa:       'https://aa-mirror.continue-ai.com/simple',
			tuna:     'https://pypi.tuna.tsinghua.edu.cn/simple',
			bfsu:     'https://mirrors.bfsu.edu.cn/pypi/web/simple',
			aliyun:   'https://mirrors.aliyun.com/pypi/simple',
			sjtug:    'https://mirror.sjtu.edu.cn/pypi-packages',
			nju:      'https://mirror.nju.edu.cn/pypi/web/simple',
			pku:      'https://mirrors.pku.edu.cn/pypi/web/simple',
			pypi_upstream: 'https://pypi.org/simple',
		},
	},

	npm: {
		mirrors: {
			npmmirror: 'https://registry.npmmirror.com',
			huawei:    'https://mirrors.huaweicloud.com/repository/npm/',
			npmjs_upstream:  'https://registry.npmjs.org/',
		},
	},

	conda: {
		mirrors: {
			tuna:     'https://mirrors.tuna.tsinghua.edu.cn/anaconda',
			bfsu:     'https://mirrors.bfsu.edu.cn/anaconda',
			nju:      'https://mirror.nju.edu.cn/anaconda',
			sjtug:    'https://mirror.sjtu.edu.cn/anaconda',
			pku:      'https://mirrors.pku.edu.cn/anaconda',
			zju:      'https://mirrors.zju.edu.cn/anaconda',
			njtech:   'https://mirrors.njtech.edu.cn/anaconda',
			anaconda_upstream: 'https://repo.anaconda.com',
		},
	},

	brew: {
		mirrors: {
			tuna:     'https://mirrors.tuna.tsinghua.edu.cn/',
			bfsu:     'https://mirrors.bfsu.edu.cn/',
			nju:      'https://mirror.nju.edu.cn/',
			nyist:    'https://mirror.nyist.edu.cn/',
			brew_upstream: 'https://github.com/Homebrew/brew.git',
		},
	},

	github: {
		mirrors: {
			github_upstream: 'https://github.com',
			ghfast:          'https://ghfast.top',
		},
	},
};

// ═══════════════════════════════════════════════════════════════
// 测速
// ═══════════════════════════════════════════════════════════════

/**
 * 对单个 URL 执行 curl 测速，返回下载速度（Byte/s）。
 * 参考 chsrc 的 measure_speed_for_url() + parse_and_say_curl_result()。
 *
 * @param {string} url  测速 URL
 * @param {number} timeoutSec  超时秒数（默认 5）
 * @returns {number}  速度 Byte/s；失败或超时返回 -1
 */
function measureSpeed(url, timeoutSec = 5) {
	try {
		const cmd = `curl -qsL -o /dev/null -w "%{http_code} %{speed_download}" -m${timeoutSec} -A "MirrorSelector/1.0" "${url}"`;
		const stdout = execSync(cmd, { encoding: 'utf-8', timeout: (timeoutSec + 2) * 1000, stdio: ['ignore', 'pipe', 'pipe'] });

		return parseCurlOutput(stdout);
	} catch (e) {
		// 当使用 -m 限制时间下载大文件时，curl 必然因为超时退出(通常是 exit code 28)
		// 此时 execSync 会抛出异常，但 e.stdout 中依然存有中止前打印的测速结果
		if (e.stdout) {
			const result = parseCurlOutput(e.stdout.toString());
			if (result.speed !== -1) {
				return result; // 成功抢救出速度数据
			}
		}
		
		const stderr = (e.stderr || "").toString().trim();
		return { speed: -1, error: stderr || e.message || "unknown" };
	}
}

// 提取一个解析输出的辅助函数，复用逻辑
function parseCurlOutput(stdout) {
	const trimmed = stdout.trim();
	const spaceIdx = trimmed.indexOf(' ');
	if (spaceIdx === -1) return { speed: -1, error: `unexpected: ${trimmed}` };

	const httpCode = parseInt(trimmed.substring(0, spaceIdx), 10);
	const speedBytes = parseFloat(trimmed.substring(spaceIdx + 1));

	// httpCode 为 0 表示可能彻底没连上，或者刚连上就被掐断了
	if (httpCode !== 200 && httpCode !== 0) return { speed: -1, error: `HTTP ${httpCode}` };
	if (isNaN(speedBytes) || speedBytes <= 0) return { speed: -1, error: `zero speed` };
	
	// 转换为 MB/s (1 MB = 1024 * 1024 Bytes)，并保留两位小数
	const speedMBps = Number((speedBytes / (1024 * 1024)).toFixed(2));
	
	return { speed: speedMBps };
}
/**
 * 对一组镜像做顺序测速，返回按速度降序排列的结果。
 * 并且在测速时实时在终端输出每个源的速度 (MB/s)。
 */
function rankMirrors(mirrorKeys, timeoutSec = 5) {
	const results = [];

	console.log(`\n[MirrorSelector] 开始对 ${mirrorKeys.length} 个镜像站进行测速 (超时: ${timeoutSec}s)...`);

	for (const key of mirrorKeys) {
		const mirror = MIRRORS[key];
		if (!mirror || !mirror.speedUrl) {
			results.push({ key, speed: -1 });
			continue;
		}
		
		const { speed, error } = measureSpeed(mirror.speedUrl, timeoutSec);
		
		// 实时输出测速结果
		if (speed === -1) {
			console.warn(`[MirrorSelector] ❌ ${mirror.name.en}: 测速失败 (${error})`);
		} else {
			console.log(`[MirrorSelector] ✅ ${mirror.name.en}: ${speed} MB/s`);
		}
		
		results.push({ key, speed });
	}

	// 按速度降序排；失败的（speed === -1）排到末尾
	results.sort((a, b) => {
		if (a.speed === -1 && b.speed === -1) return 0;
		if (a.speed === -1) return 1;
		if (b.speed === -1) return -1;
		return b.speed - a.speed;
	});

	console.log(`[MirrorSelector] 测速完成！\n`);

	return results;
}

// ═══════════════════════════════════════════════════════════════
// 主入口
// ═══════════════════════════════════════════════════════════════

/**
 * 为指定的包管理器选择最快的镜像源。
 *
 * 流程：
 *   1. 收集所有候选工具的镜像站，去重
 *   2. 对每个唯一镜像站做 curl 模糊测速
 *   3. 按速度降序排列
 *   4. 为每个工具，从其候选镜像中选速度最快的那一个
 *   5. 返回结果
 *
 * @param {Object} opts
 * @param {string[]} opts.tools  需要配置的包管理器列表，默认 ['pip', 'conda', 'npm', 'brew']
 * @param {number}  opts.timeoutSec  每个镜像测速超时秒数，默认 5
 * @returns {Object}  { pip: {url, mirror, speed}, npm: {...}, ... }
 */
function selectBestMirrors({ tools = ['pip', 'conda', 'npm', 'brew', 'github'], timeoutSec = 5 } = {}) {
	// 1. 收集所有涉及的唯一镜像站
	const uniqueMirrors = new Set();
	for (const tool of tools) {
		const def = TOOLS[tool];
		if (!def) continue;
		for (const mKey of Object.keys(def.mirrors)) {
			uniqueMirrors.add(mKey);
		}
	}

	// 2. 对所有唯一镜像站测速、排序
	const ranked = rankMirrors([...uniqueMirrors], timeoutSec);
	// 3. 为每个工具选择最快且可用的镜像
	const result = {};
	for (const tool of tools) {
		const def = TOOLS[tool];
		if (!def) continue;

		let bestMirror = null;
		let bestUrl = null;
		let bestSpeed = -1;

		// 第一轮：按速度从快到慢，找第一个测速成功的镜像
		for (const { key, speed } of ranked) {
			if (speed <= 0) continue;
			if (def.mirrors[key]) {
				bestMirror = key;
				bestUrl = def.mirrors[key];
				bestSpeed = speed;
				break;
			}

		}

		// 第二轮：全部测速失败时，取列表第一个可用的（兜底）
		if (!bestUrl) {
			for (const { key } of ranked) {
				if (def.mirrors[key]) {
					bestMirror = key;
					bestUrl = def.mirrors[key];
					bestSpeed = 0;
					break;
				}

			}
		}

		result[tool] = {
			url: bestUrl,
			mirror: bestMirror,
			mirrorName: MIRRORS[bestMirror]?.name || bestMirror,
			speed: bestSpeed,
		};
	}

	return result;
}

// ═══════════════════════════════════════════════════════════════
// 导出命令生成
// ═══════════════════════════════════════════════════════════════

/**
 * 根据 selectBestMirrors() 的返回结果，生成 export 命令数组。
 *
 * pip   -> export PIP_INDEX_URL=<url>
 * npm   -> export npm_config_registry=<url>
 * conda -> export CONDA_CHANNELS=<url>  （注意：conda 原生不支持此环境变量，
 *          这里仅为保持兼容性；实际换源建议用 conda config --set channels）
 * brew  -> export HOMEBREW_BREW_GIT_REMOTE=<url>/git/homebrew/brew.git
 *          export HOMEBREW_CORE_GIT_REMOTE=<url>/git/homebrew/homebrew-core.git
 *          export HOMEBREW_INSTALL_FROM_API=1
 *
 * @param {Object} selected  selectBestMirrors() 的返回结果
 * @returns {string[]}  export 命令数组
 */
function toExportCommands(selected) {
	const commands = [];

	for (const [tool, info] of Object.entries(selected)) {
		const url = info.url;

		switch (tool) {
		case 'pip':
			commands.push(`export PIP_INDEX_URL=${url}`);
			break;
		case 'npm':
			commands.push(`export npm_config_registry=${url}`);
			break;
		case 'conda':
			commands.push(`export CONDA_CHANNELS=${url}/pkgs/main/`);
			break;
		case 'brew':
			if (info.mirror === 'github_upstream') {
				commands.push('unset HOMEBREW_BREW_GIT_REMOTE');
				commands.push('unset HOMEBREW_CORE_GIT_REMOTE');
			} else {
				commands.push(`export HOMEBREW_BREW_GIT_REMOTE=${url}git/homebrew/brew.git`);
				commands.push(`export HOMEBREW_CORE_GIT_REMOTE=${url}git/homebrew/homebrew-core.git`);
			}
			commands.push('export HOMEBREW_INSTALL_FROM_API=1');
			break;
		case 'github':
			if (info.mirror !== 'github_upstream') {
				commands.push(`GITHUB_PREFIX="${url}"`);
			}
			break;
		}
	}

	return commands;
}
function listMirrors(tool) {
	const def = TOOLS[tool];
	if (!def) return [];

	return Object.entries(def.mirrors).map(([key, url]) => ({
		mirror: key,
		name: MIRRORS[key]?.name || key,
		url,
	}));
}

export {
	MIRRORS,
	TOOLS,
	selectBestMirrors,
	toExportCommands,
	listMirrors,
	measureSpeed,
	rankMirrors,
};
