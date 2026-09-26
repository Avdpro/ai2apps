(function () {
    'use strict';
    let closeCurrent = () => {};
    window.AI2AppsStudioTaskMenu = {
        open(event, { disabled = false, onDelete }) {
            event.preventDefault(); event.stopPropagation(); closeCurrent();
            const chinese = (document.documentElement.lang || '').toLowerCase().startsWith('zh');
            const origin = event.currentTarget;
            const menu = document.createElement('div');
            menu.setAttribute('role', 'menu');
            menu.style.cssText = 'position:fixed;z-index:10000;min-width:180px;max-width:260px;padding:5px;border:1px solid #e7e5e4;border-radius:10px;background:white;box-shadow:0 8px 30px #0002;font:12px system-ui;color:#292524';
            const button = document.createElement('button');
            button.type='button'; button.setAttribute('role','menuitem');
            button.textContent=chinese?'删除任务':'Delete task'; button.disabled=disabled;
            button.style.cssText='display:block;width:100%;border:0;border-radius:6px;background:transparent;text-align:left;padding:9px 12px;font:inherit;color:'+(disabled?'#a8a29e':'#b91c1c')+';cursor:'+(disabled?'default':'pointer');
            button.onmouseenter=()=>{button.style.background='#f5f5f4';};
            button.onmouseleave=()=>{button.style.background='transparent';};
            const note=document.createElement('div'); note.style.cssText='font-size:10px;color:#78716c;padding:4px 12px 8px;line-height:1.4';
            note.textContent=disabled?(chinese?'请先停止正在进行的任务':'Stop the active task first'):(chinese?'已加入 Gallery 的素材会保留':'Copies saved in Gallery are kept');
            menu.append(button,note);document.body.append(menu);
            const rect=origin.getBoundingClientRect();
            const x=event.type==='keydown'?rect.left:event.clientX;
            const y=event.type==='keydown'?rect.bottom:event.clientY;
            menu.style.left=Math.max(4,Math.min(x,window.innerWidth-menu.offsetWidth-4))+'px';
            menu.style.top=Math.max(4,Math.min(y,window.innerHeight-menu.offsetHeight-4))+'px';
            const outside=e=>{if(!menu.contains(e.target))close();};
            const key=e=>{if(['Escape','Tab'].includes(e.key)){close();if(e.key==='Escape'){e.preventDefault();origin.focus();}}};
            const close=()=>{menu.remove();document.removeEventListener('pointerdown',outside,true);document.removeEventListener('keydown',key,true);window.removeEventListener('resize',close);document.removeEventListener('scroll',close,true);closeCurrent=()=>{};};
            closeCurrent=close;document.addEventListener('pointerdown',outside,true);document.addEventListener('keydown',key,true);window.addEventListener('resize',close);document.addEventListener('scroll',close,true);
            button.onclick=()=>{close();onDelete();}; if(!disabled)button.focus();
        }
    };
})();
