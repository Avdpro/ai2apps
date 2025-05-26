function makeButton({ width, height, imageUrl, bgColor, tipText, padding, onClick }) {
	const btn = document.createElement('div');
	btn.style.position = 'relative';
	btn.style.width = width + 'px';
	btn.style.height = height + 'px';
	btn.style.cursor = 'pointer';
	btn.style.display = 'inline-block';
	btn.style.flex = '0 0 auto';
	btn.style['-webkit-app-region'] = 'no-drag';
	
	// 图片元素
	const img = document.createElement('img');
	img.src = imageUrl;
	img.style.position = 'absolute';
	img.style.left = padding + 'px';
	img.style.top = padding + 'px';
	img.style.width = (width - padding * 2) + 'px';
	img.style.height = (height - padding * 2) + 'px';
	img.style.transition = 'opacity 0.2s';
	img.draggable=false;
	
	// 半透明底板
	const overlay = document.createElement('div');
	overlay.style.position = 'absolute';
	overlay.style.left = '0';
	overlay.style.top = '0';
	overlay.style.width = '100%';
	overlay.style.height = '100%';
	overlay.style.borderRadius = '8px';
	overlay.style.backgroundColor = bgColor;
	overlay.style.display = 'none';
	overlay.style.opacity = '0.2';
	
	// tip 气泡
	const tip = document.createElement('div');
	tip.textContent = tipText;
	tip.style.position = 'absolute';
	tip.style.top = height + 4 + 'px';
	tip.style.left = '50%';
	tip.style.transform = 'translateX(-50%)';
	tip.style.background = 'rgba(0,0,0,0.8)';
	tip.style.color = '#fff';
	tip.style.padding = '2px 6px';
	tip.style.borderRadius = '4px';
	tip.style.fontSize = '12px';
	tip.style.whiteSpace = 'nowrap';
	tip.style.display = 'none';
	tip.style.pointerEvents = 'none';
	tip.style.zIndex = '10';
	
	btn.appendChild(overlay);
	btn.appendChild(img);
	btn.appendChild(tip);
	
	let currentState = 'up';
	let isMouseDown = false;
	
	function setState(state) {
		currentState = state;
		
		if (state === 'gray') {
			overlay.style.display = 'none';
			overlay.style.opacity = '0.2';
			tip.style.display = 'none';
			img.style.opacity = '0.2';
			btn.style.cursor = 'default';
		} else {
			overlay.style.display = 'block';
			btn.style.cursor = 'pointer';
			
			if (state === 'up') {
				overlay.style.display = 'none';
				overlay.style.opacity = '0.2';
				tip.style.display = 'none';
			} else if (state === 'hover') {
				overlay.style.display = 'block';
				overlay.style.opacity = '0.2';
				if(tipText) {
					tip.style.display = 'block';
				}
			} else if (state === 'down') {
				overlay.style.display = 'block';
				overlay.style.opacity = '0.5';
				tip.style.display = 'none';
			}
		}
	}
	
	// 事件绑定（仅非 gray 状态）
	btn.addEventListener('mouseenter', () => {
		if (currentState !== 'gray') setState('hover');
	});
	
	btn.addEventListener('mouseleave', () => {
		if (currentState !== 'gray') {
			isMouseDown = false;
			setState('up');
		}
	});
	
	btn.addEventListener('mousedown', () => {
		if (currentState !== 'gray') {
			isMouseDown = true;
			setState('down');
		}
	});
	
	btn.addEventListener('mouseup', (evt) => {
		if (currentState !== 'gray' && isMouseDown) {
			setState('hover');
			if (typeof onClick === 'function') {
				onClick();
			}
			evt.preventDefault();
			evt.stopPropagation();
		}
		isMouseDown = false;
	});
	
	// 返回按钮和状态控制方法
	btn.setState = setState;
	return btn;
}

export default makeButton;
export {makeButton};