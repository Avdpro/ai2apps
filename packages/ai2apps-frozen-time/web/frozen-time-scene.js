/* Offline perspective scene. The camera convention matches orbit_pose. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id);
 const panel=document.createElement('details');panel.id='scene-preview';
 panel.innerHTML='<summary id="scene-title"></summary><canvas id="scene-canvas" width="720" height="360" aria-label="3D camera motion preview"></canvas><div class="scene-controls"><button id="scene-play" type="button"></button><input id="scene-position" type="range" min="0" max="1000" value="0"><span id="scene-time"></span></div><p id="scene-note"></p>';
 $('curve-editor').before(panel);
 let locale='en',playing=false,handle=0,start=0,position=0;
 const strings={en:{title:'3D movement sketch · no generation needed',play:'Play',pause:'Pause',timeline:'Camera timeline',note:'A box represents the subject; distant pillars represent the background. This uses the actual camera path and return sequence, not AI image quality.'},zh:{title:'3D 运镜示意 · 无需生成',play:'播放',pause:'暂停',timeline:'镜头时间线',note:'盒子代表主体，远处柱体代表背景。使用实际镜头轨迹及返回顺序，仅示意运镜，不代表 AI 成品画质。'}};
 const text=k=>strings[/^zh/i.test(locale)?'zh':'en'][k];
 const sub=(a,b)=>a.map((v,i)=>v-b[i]),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm=a=>a.map(v=>v/Math.hypot(...a));
 function camera(key){const a=key.yaw*Math.PI/180,b=key.pitch*Math.PI/180,pivot=[0,0,5],eye=[5*key.radius*Math.sin(a)*Math.cos(b),-5*key.radius*Math.sin(b),5-5*key.radius*Math.cos(a)*Math.cos(b)],forward=norm(sub(pivot,eye)),right=norm(cross([0,1,0],forward)),down=cross(forward,right),r=key.roll*Math.PI/180;return {eye,forward,right:right.map((v,i)=>Math.cos(r)*v-Math.sin(r)*down[i]),down:down.map((v,i)=>Math.sin(r)*right[i]+Math.cos(r)*v)};}
 function project(point,pose){const p=sub(point,pose.eye),z=dot(p,pose.forward);if(z<=.05)return null;return [360+dot(p,pose.right)*440/z,180+dot(p,pose.down)*440/z,z];}
 function box(cx,cy,cz,w,h,d,color){const vertices=[];for(const z of [-1,1])for(const y of [-1,1])for(const x of [-1,1])vertices.push([cx+x*w/2,cy+y*h/2,cz+z*d/2]);return [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]].map((indices,i)=>({points:indices.map(n=>vertices[n]),color,light:[.9,.75,.65,1,.8,.85][i]}));}
 function plan(){try{const data=JSON.parse(window.frozenEditor.renderPlan());return {...data,order:$('output').value==='html'?data.frames.map((_,i)=>i):data.playback};}catch{return null;}}
 function draw(data=plan()){if(!data)return;const frame=Math.round(position*(data.order.length-1)),key=data.frames[data.order[frame]],pose=camera(key),ctx=$('scene-canvas').getContext('2d');ctx.clearRect(0,0,720,360);ctx.fillStyle='#eef0f7';ctx.fillRect(0,0,720,360);
  const line=(a,b)=>{const p=project(a,pose),q=project(b,pose);if(!p||!q)return;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke();};ctx.strokeStyle='#ccd1df';ctx.lineWidth=1;for(let x=-10;x<=10;x++)line([x,1.35,2],[x,1.35,22]);for(let z=2;z<=22;z++)line([-10,1.35,z],[10,1.35,z]);
  const faces=[...box(0,.15,5,1.4,2.4,1,'#a78bfa'),...box(-3,.15,10,1,2.4,1,'#7db9ba'),...box(3,-.35,12,1.2,3.4,1.2,'#e5b56a'),...box(-1.5,-.85,17,1.5,4.4,1.5,'#8faccb')];const visible=faces.map(f=>({...f,projected:f.points.map(p=>project(p,pose))})).filter(f=>f.projected.every(Boolean));visible.sort((a,b)=>b.projected.reduce((s,p)=>s+p[2],0)-a.projected.reduce((s,p)=>s+p[2],0));
  for(const face of visible){ctx.beginPath();face.projected.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=face.color;ctx.fill();ctx.fillStyle=`rgba(0,0,0,${1-face.light})`;ctx.fill();ctx.strokeStyle='#ffffff80';ctx.stroke();}
  $('scene-canvas').style.filter=`blur(${Math.min(key.blur,4)}px) saturate(${key.saturation}) brightness(${2**key.exposure*key.brightness})`;
  $('scene-position').value=Math.round(position*1000);$('scene-time').textContent=(frame/24).toFixed(2)+' / '+(data.order.length/24).toFixed(2)+'s';
 }
 function stop(){playing=false;cancelAnimationFrame(handle);$('scene-play').textContent=text('play');}
 function tick(now){const data=plan();if(!playing||!panel.open||document.hidden||!data)return stop();const duration=data.order.length/24*1000;position=Math.min(1,(now-start)/duration);draw(data);if(position>=1)return stop();handle=requestAnimationFrame(tick);}
 $('scene-play').onclick=()=>{if(playing)return stop();const data=plan();if(!data)return;if(position>=1)position=0;playing=true;start=performance.now()-position*data.order.length/24*1000;$('scene-play').textContent=text('pause');handle=requestAnimationFrame(tick);};
 $('scene-position').oninput=()=>{stop();position=Number($('scene-position').value)/1000;draw();};
 panel.ontoggle=()=>{if(!panel.open)stop();else draw();};
 function reset(){stop();position=0;if(panel.open)draw();}
 window.addEventListener('frozen-curve-change',reset);window.addEventListener('frozen-curve-change-view',reset);$('output').addEventListener('change',reset);document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});window.addEventListener('pagehide',stop);
 window.frozenScene={translate(value){locale=value;$('scene-title').textContent=text('title');$('scene-play').textContent=text(playing?'pause':'play');$('scene-note').textContent=text('note');$('scene-position').setAttribute('aria-label',text('timeline'));$('scene-canvas').setAttribute('aria-label',text('title'));}};window.frozenScene.translate(document.documentElement.lang);
})();
