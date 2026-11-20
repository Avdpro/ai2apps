/* Shared Gallery identities; this editor owns appearance-specific image prompts. */
(() => {
 const api='/v1/platform/gallery/characters';
 async function request(url,body,method='GET',headers={}) {
  const response=await fetch(url,{method,credentials:'same-origin',cache:'no-store',headers:{...headers,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const result=await response.json();if(!response.ok)throw Error(result.error?.message||result.detail?.message||'Character request failed');return result;
 }
 const appearance=()=>({id:crypto.randomUUID(),name:'',style:'',style_id:'',proportions:'',outfit:'',description:'',summary:'',definition_image_id:'',reference_ids:[],approved:false});
 window.ImagineCharacters=()=>({
  characterArchiveFile:null,characterArchivePreview:null,characterArchiveBusy:false,
  characterSlotCache:{},characterSlotSwitching:false,characterItems:[],characterLoaded:false,characterBusy:false,characterId:'',appearanceId:'',characterDraft:null,characterReference:null,characterDesignTarget:null,characterTextBusy:false,characterDeriving:false,characterCollecting:false,characterCollectedRuns:{},characterCollectError:'',
  characterSharedItems:[],characterSharedLoaded:false,characterSharedBusy:false,sharedCharacterId:'',sharedAppearanceId:'',
  get sharedCharacter(){return this.characterSharedItems.find(c=>c.id===this.sharedCharacterId)||null;},
  get sharedAppearance(){return this.sharedCharacter?.appearances.find(a=>a.id===this.sharedAppearanceId)||null;},
  selectSharedCharacter(){this.sharedAppearanceId=this.sharedCharacter?.appearances.find(a=>a.id===this.sharedCharacter.default_appearance_id)?.id||this.sharedCharacter?.appearances[0]?.id||'';},
  async loadSharedCharacterDefinitions(){if(this.characterSharedBusy)return;this.characterSharedBusy=true;try{
   this.characterSharedItems=(await request('/v1/platform/gallery/characters/definitions')).items;this.characterSharedLoaded=true;
   if(!this.sharedCharacter)this.sharedCharacterId=this.characterSharedItems[0]?.id||'';
   if(!this.sharedAppearance)this.selectSharedCharacter();return true;
  }catch(e){this.fail(e);return false;}finally{this.characterSharedBusy=false;}},
  async useSharedCharacterDefinition(){const cid=this.sharedCharacterId,aid=this.sharedAppearanceId;if(!await this.loadSharedCharacterDefinitions())return;
   const c=this.characterSharedItems.find(c=>c.id===cid),a=c?.appearances.find(a=>a.id===aid);
   if(!a){this.fail(Error(this.characterText('此形象已变更或未定稿，请重新选择。','Appearance changed or is not finalized. Select again.')));return;}
   try{await this.materializeAssetReference({assetId:a.definition_image_id},0);for(let i=1;i<this.referenceSlotCount;i++)this.clearReference(i);
    this.characterReference={characterId:c.id,revision:c.revision,appearanceId:a.id,appearanceRevision:a.revision,definitionImageId:a.definition_image_id,summary:a.summary};this.scheduleDraftSave();
    this.success(this.characterText('已使用形象定义图与说明。','Definition image and guide selected.'));
   }catch(e){this.fail(e);}
  },
  characterReuseGuide(){const ref=this.characterReference;return !this.isCharacterMode&&ref?.definitionImageId===this.referenceAssets?.[0]?.assetId?ref.summary||'':'';},
  characterText(zh,en){return this.locale==='zh'?zh:en;},
  get isCharacterMode(){return this.currentMiniApp?.adapter==='character-design';},
  get characterAppearance(){return this.characterDraft?.appearances.find(a=>a.id===this.appearanceId)||null;},
  get characterProportionPresets(){return [
   ['超萌 Q 版 · 2 头身','Super chibi · 2 heads tall'],
   ['经典 Q 版 · 3 头身','Classic chibi · 3 heads tall'],
   ['大头卡通 · 4 头身','Big-head cartoon · 4 heads tall'],
   ['可爱卡通 · 5 头身','Cute cartoon · 5 heads tall'],
   ['漫画少年 · 6 头身','Manga youth · 6 heads tall'],
   ['日系动漫 · 7 头身','Anime · 7 heads tall'],
   ['写实成人 · 7.5 头身','Realistic adult · 7.5 heads tall'],
   ['理想化写实 · 8 头身','Idealized realistic · 8 heads tall'],
   ['漫威式超级英雄 · 8.5 头身，宽肩、健壮体型','Marvel-style superhero · 8.5 heads tall, broad shoulders, muscular build'],
   ['修长时装 · 9 头身','Fashion illustration · 9 heads tall'],
   ['夸张英雄 · 9 头身，宽肩窄腰','Exaggerated hero · 9 heads tall, broad shoulders and narrow waist'],
   ['圆润玩偶 · 2.5 头身，短四肢','Rounded toy · 2.5 heads tall, short limbs'],
   ['保留参考图原有比例','Preserve proportions from the reference image']
  ].map(([zh,en])=>this.characterText(zh,en));},
  get characterStyleLabel(){const a=this.characterAppearance;const preset=this.allStyles?.find(s=>s.id===a?.style_id);return preset?this.localizedName(preset):(a?.style||'');},
  async loadCharacters(){if(this.characterBusy)return;this.characterBusy=true;try{this.characterItems=(await request(api)).items;this.characterLoaded=true;}catch(e){this.fail(e);}finally{this.characterBusy=false;}},
  async chooseCharacter(){this.captureCharacterSlots();const c=this.characterItems.find(c=>c.id===this.characterId);this.characterDraft=c?JSON.parse(JSON.stringify(c)):null;this.appearanceId=c?.default_appearance_id||c?.appearances[0]?.id||'';await this.restoreCharacterSlots();},
  newCharacter(){this.captureCharacterSlots();this.characterId='';const a=appearance();a.name=this.characterText('默认形象','Default appearance');this.characterDraft={name:'',description:'',aliases:[],revision:0,default_appearance_id:a.id,appearances:[a]};this.appearanceId=a.id;this.clearCharacterSlots();},
  newAppearance(){if(!this.characterDraft||this.characterDraft.appearances.length>=50)return;this.captureCharacterSlots();const a=appearance();this.characterDraft.appearances.push(a);this.appearanceId=a.id;this.characterReference=null;this.characterDesignTarget=null;for(let i=0;i<(this.referenceSlotCount||0);i++)this.clearReference(i);this.scheduleDraftSave();},
  async selectCharacterAppearance(value){if(this.characterDeriving||this.characterSlotSwitching)return;if(value==='__new__')this.newAppearance();else{this.captureCharacterSlots();this.appearanceId=value;await this.restoreCharacterSlots();}},
  characterSlotKey(){return this.characterDraft&&this.appearanceId?(this.characterDraft.id||'new')+':'+this.appearanceId:'';},
  captureCharacterSlots(){if(!this.isCharacterMode||this.characterSlotSwitching||!this.characterSlotKey()||!this.referenceFiles)return;this.characterSlotCache[this.characterSlotKey()]={files:[...this.referenceFiles],assets:[...(this.referenceAssets||[])]};},
  clearCharacterSlots(){if(!this.isCharacterMode)return;for(let i=0;i<(this.referenceSlotCount||0);i++)this.clearReference(i);this.characterReference=null;this.characterDesignTarget=null;},
  async restoreCharacterSlots(){if(!this.isCharacterMode)return;this.characterSlotSwitching=true;try{
   this.clearCharacterSlots();const cached=this.characterSlotCache[this.characterSlotKey()];
   if(cached){for(let i=0;i<Math.min(cached.files.length,this.referenceSlotCount||0);i++)if(cached.files[i])await this.setReference(i,cached.files[i],cached.assets[i]||null);}
   else for(const [i,id] of (this.characterAppearance?.reference_ids||[]).entries())if(i<(this.referenceSlotCount||0))await this.materializeAssetReference({assetId:id},i);
  }catch(e){this.fail(e);}finally{this.characterSlotSwitching=false;}},
  async persistCharacterSlots(){if(!this.isCharacterMode||!this.referenceFiles||!this.characterAppearance)return;
   const a=this.characterAppearance,ids=[];
   for(const [i,file] of this.referenceFiles.entries()){if(!file)continue;let id=this.referenceAssets?.[i]?.assetId;
    if(!id){const form=new FormData();form.append('file',file);const response=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',body:form});const value=await response.json();if(!response.ok)throw Error(value.error?.message||'Reference import failed');id=value.asset?.id||value.id;if(!id)throw Error('Reference import failed');const assets=[...(this.referenceAssets||[])];assets[i]={assetId:id};this.referenceAssets=assets;}
    ids.push(id);
   }
   if(JSON.stringify(a.reference_ids)!==JSON.stringify(ids)){a.reference_ids=ids;a.approved=false;}
   this.captureCharacterSlots();
  },
  get characterDerivationImage(){if(this.characterAppearance?.definition_image_id)return {asset_id:this.characterAppearance.definition_image_id};const images=this.characterAppearance?.generated_images||[];const selected=this.activeArtifact;
   return images.find(i=>selected?.kind==='image'&&(i.artifact_id===selected.id||i.artifact_id===selected.metadata?.workspaceArtifactId))||images[images.length-1]||null;},
  async deriveCharacterAppearance(){
   this.captureCharacterSlots();const source=this.characterAppearance,c=this.characterDraft,image=this.characterDerivationImage;
   if(!source||!c||c.appearances.length>=50||this.characterDeriving)return;
   if(!image?.asset_id){this.fail(Error(this.characterText('请先为当前形象生成设定图，再派生形象。','Generate a reference sheet for this appearance before deriving it.')));return;}
   this.characterDeriving=true;
   try{
    const a={...appearance(),...Object.fromEntries(['style','style_id','proportions','outfit','description','summary'].map(k=>[k,source[k]||'']))};
    const base=(source.name||this.characterText('形象','Appearance')).slice(0,80)+this.characterText(' · 派生',' · Derived');let name=base,n=2;
    while(c.appearances.some(x=>x.name===name))name=base+' '+n++;
    a.name=name.slice(0,100);a.reference_ids=[image.asset_id];
    await this.materializeAssetReference({assetId:image.asset_id},0);
    if(this.characterDraft!==c||this.characterAppearance!==source)throw Error(this.characterText('当前形象已切换，请重新派生。','Appearance changed. Try deriving again.'));
    for(let i=1;i<(this.referenceSlotCount||0);i++)this.clearReference(i);
    c.appearances.push(a);this.appearanceId=a.id;this.characterReference=null;this.characterDesignTarget=null;this.scheduleDraftSave();
   }catch(e){this.fail(e);}finally{this.characterDeriving=false;}
  },
  async saveCharacter(){if(!this.characterDraft||this.characterBusy)return;await this.collectCharacterRuns();if(this.characterBusy)return;this.characterBusy=true;try{
   await this.persistCharacterSlots();const c=this.characterDraft;const body={name:c.name,description:c.description,aliases:c.aliases,revision:c.revision,default_appearance_id:c.default_appearance_id,appearances:c.appearances.map(({revision,generated_images,...a})=>a)};
   const saved=await request(api+(this.characterId?'/'+encodeURIComponent(this.characterId):''),body,this.characterId?'PUT':'POST');
   this.characterId=saved.id;this.characterDraft=saved;this.captureCharacterSlots();this.characterItems=[JSON.parse(JSON.stringify(saved)),...this.characterItems.filter(c=>c.id!==saved.id)];this.success(this.characterText('角色已保存','Character saved'));return saved;
  }catch(e){this.fail(e);}finally{this.characterBusy=false;}},
  async rememberCharacterReferences(){const a=this.characterAppearance;if(!a)return;try{
   const ids=[];for(const file of this.referenceFiles.filter(Boolean).slice(0,4)){const form=new FormData();form.append('file',file);const r=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',body:form});const v=await r.json();if(!r.ok)throw Error(v.error?.message||'Reference import failed');ids.push(v.asset?.id||v.id);}
   if(!ids.length)throw Error(this.characterText('请先在下方素材槽选择图片','Choose reference images below first'));a.reference_ids=[...new Set(ids)];a.approved=false;await this.saveCharacter();
  }catch(e){this.fail(e);}},
  async useCharacterAppearance(){const a=this.characterAppearance;const refs=this.isCharacterMode?(a?.reference_ids||[]):(a?.definition_image_id?[a.definition_image_id]:[]);if(!refs.length)return;try{if(!this.isCharacterMode){const saved=this.characterItems.find(c=>c.id===this.characterId);if(!a.approved||!saved||JSON.stringify(saved.appearances)!==JSON.stringify(this.characterDraft.appearances)||saved.description!==this.characterDraft.description)throw Error(this.characterText('请先保存并定稿此形象，再引用定义图和说明','Save and confirm this appearance before reuse'));}for(let i=0;i<this.referenceSlotCount;i++)this.clearReference(i);for(let i=0;i<Math.min(refs.length,this.referenceSlotCount);i++)await this.materializeAssetReference({assetId:refs[i]},i);this.characterReference={characterId:this.characterId,revision:this.characterDraft.revision,appearanceId:a.id,appearanceRevision:a.revision};if(!this.isCharacterMode)this.prompt=[this.prompt.trim(),a.summary].filter(Boolean).join('\n\n');this.scheduleDraftSave();}catch(e){this.fail(e);}},
  async saveCharacterOutput(){const a=this.characterAppearance,artifact=this.activeArtifact;if(!a||artifact?.kind!=='image')return;try{if(!artifact.galleryAssetId)await this.addArtifactToGallery(artifact);if(!artifact.galleryAssetId)return;a.definition_image_id=artifact.galleryAssetId;a.approved=false;await this.saveCharacter();}catch(e){this.fail(e);}},
  async prepareCharacterRender(){if(this.characterSlotSwitching)return false;if(!this.characterAppearance?.summary?.trim()){await this.generateCharacterDescription();if(!this.characterAppearance?.summary?.trim())return false;}const saved=await this.saveCharacter();if(!saved)return false;const a=this.characterAppearance;this.characterDesignTarget={character_id:saved.id,appearance_id:a.id,appearance_revision:a.revision};return true;},
  async generateCharacterDescription(){const c=this.characterDraft,a=this.characterAppearance;if(!c||!a||this.characterTextBusy)return;this.characterTextBusy=true;const before=a.summary||'';
   const {revision,generated_images,...parameters}=a;const snapshot=JSON.stringify(parameters);
   try{const result=await request('/v1/platform/imagine-studio/characters/describe',{name:c.name,identity:c.description,appearance:parameters,language:this.locale==='zh'?'zh':'en'},'POST',this.historyHeaders());
    const {revision:_,generated_images:__,...current}=a;
    if(c!==this.characterDraft||a!==this.characterAppearance||snapshot!==JSON.stringify(current)||before!==(a.summary||''))throw Error(this.characterText('参数或说明已修改，保留当前内容；请重新生成说明。','Parameters or description changed; current text was preserved. Generate again.'));
    a.summary=result.summary;
   }catch(e){this.fail(e);}finally{this.characterTextBusy=false;}
  },
  mergeCharacterCollection(saved,base){
   const draft=this.characterDraft;if(this.characterId!==saved.id||!draft||saved.revision<draft.revision)return;
   const equal=(a,b)=>{const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;return JSON.stringify(canonical(a))===JSON.stringify(canonical(b));};
   const copy=x=>x===undefined?undefined:JSON.parse(JSON.stringify(x));let conflict=!base;const changes=[];
   const reconcile=(target,old,fresh,fields)=>{for(const key of fields){const fallback=key==='aliases'||key==='reference_ids'?[]:key==='approved'?false:'';const before=old?.[key]??fallback,next=fresh[key]??fallback,current=target[key]??fallback;
    if(equal(before,next))continue;if(equal(current,before)||equal(current,next))changes.push(()=>{target[key]=copy(next)});else conflict=true;
   }};
   if(base){reconcile(draft,base,saved,['name','description','aliases','default_appearance_id']);
    if(!equal(base.appearances.map(a=>a.id).sort(),saved.appearances.map(a=>a.id).sort()))conflict=true;
    for(const a of draft.appearances){const fresh=saved.appearances.find(x=>x.id===a.id),old=base.appearances.find(x=>x.id===a.id);if(fresh&&old)reconcile(a,old,fresh,['name','style','style_id','proportions','outfit','description','summary','reference_ids','definition_image_id','approved']);}
   }
   // Generated files belong to the server and can be shown even with a real edit conflict.
   for(const a of draft.appearances){const fresh=saved.appearances.find(x=>x.id===a.id);if(fresh)a.generated_images=copy(fresh.generated_images||[]);}
   if(conflict){this.characterCollectError=this.characterText('形象设定有其它修改；当前编辑已保留，请核对后重新加载。','Appearance settings changed elsewhere; your edits are preserved. Review before reloading.');return;}
   for(const apply of changes)apply();for(const a of draft.appearances){const fresh=saved.appearances.find(x=>x.id===a.id);if(fresh)a.revision=fresh.revision;}
   draft.revision=saved.revision;
  },
  collectCharacterRuns(){
   if(this.characterCollectionPromise)return this.characterCollectionPromise;
   if(this.characterBusy)return Promise.resolve();
   const pending=this.performCharacterCollection();this.characterCollectionPromise=pending;
   return pending.finally(()=>{if(this.characterCollectionPromise===pending)this.characterCollectionPromise=null;});
  },
  async performCharacterCollection(){this.characterCollecting=true;try{
   for(const run of this.runs||[]){if(run.miniAppId!=='ai2apps.imagine.character-design'||run.status!=='succeeded'||!run.input?.characterDesignTarget||this.characterCollectedRuns[run.id])continue;
    const base=this.characterItems.find(c=>c.id===run.input.characterDesignTarget.character_id);
    const baseline=base?JSON.parse(JSON.stringify(base)):null;
    try{const saved=await request('/v1/platform/imagine-studio/characters/runs/'+encodeURIComponent(run.id)+'/collect',{},'POST',this.historyHeaders());
     this.characterCollectError='';this.mergeCharacterCollection(saved,baseline);
     const current=this.characterItems.find(c=>c.id===saved.id);if(!current||saved.revision>=current.revision)this.characterItems=[JSON.parse(JSON.stringify(saved)),...this.characterItems.filter(c=>c.id!==saved.id)];
     this.characterCollectedRuns[run.id]=true;
    }catch(e){this.characterCollectedRuns[run.id]='error';this.characterCollectError=e.message;}
   }
  }finally{this.characterCollecting=false;}},
  async retryCharacterCollection(){for(const id of Object.keys(this.characterCollectedRuns))if(this.characterCollectedRuns[id]==='error')delete this.characterCollectedRuns[id];await this.collectCharacterRuns();},
  async removeGeneratedCharacterImage(image){
   const c=this.characterDraft,a=this.characterAppearance,id=this.characterId;
   if(!c||!a||!id||this.characterBusy)return;
   this.characterBusy=true;
   try{
    const saved=await request('/v1/platform/imagine-studio/characters/'+encodeURIComponent(id)+'/appearances/'+encodeURIComponent(a.id)+'/images/'+encodeURIComponent(image.artifact_id),{revision:c.revision},'DELETE',this.historyHeaders());
    this.characterItems=[JSON.parse(JSON.stringify(saved)),...this.characterItems.filter(x=>x.id!==saved.id)];
    if(this.characterDraft===c){const fresh=saved.appearances.find(x=>x.id===a.id);a.generated_images=fresh?.generated_images||[];c.revision=saved.revision;}
    this.success(this.characterText('已移除形象图关联，Output 和 Gallery 原文件保留。','Image unlinked; original files remain in Output and Gallery.'));
   }catch(e){this.fail(e);}finally{this.characterBusy=false;}
  },
  async setCharacterDefinitionFile(file){
   const a=this.characterAppearance;if(!a||!file)return;
   if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error(this.characterText('请选择 PNG、JPEG 或 WebP 图片','Choose a PNG, JPEG or WebP image'));
   const form=new FormData();form.append('file',file);
   const response=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',body:form});const value=await response.json();
   if(!response.ok)throw Error(value.error?.message||'Image import failed');
   if(a!==this.characterAppearance)return;
   a.definition_image_id=value.asset?.id||value.id;a.approved=false;
  },
  async dropCharacterDefinition(event){
   const assetId=event.dataTransfer?.getData('application/x-ai2apps-gallery-asset');
   if(assetId){this.characterAppearance.definition_image_id=assetId;this.characterAppearance.approved=false;return;}
   const file=await this.droppedOutputFile(event.dataTransfer);if(file)await this.setCharacterDefinitionFile(file);
  },
  async useGeneratedCharacterImage(image){if(!this.characterAppearance)return;this.characterAppearance.definition_image_id=image.asset_id;this.characterAppearance.approved=false;await this.saveCharacter();},
  async exportCharacterArchive(currentOnly=false){if(this.characterArchiveBusy)return;const saved=await this.saveCharacter();if(!saved)return;this.characterArchiveBusy=true;try{
   const path=api+'/'+encodeURIComponent(saved.id)+'/archive'+(currentOnly?'?appearance_id='+encodeURIComponent(this.appearanceId):'');const response=await fetch(path,{credentials:'same-origin',cache:'no-store'});
   if(!response.ok){const v=await response.json();throw Error(v.error?.message||'Export failed');}
   const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download=(saved.name+(currentOnly?'-'+this.characterAppearance.name:'')).replace(/[\\/\x00-\x1f]/g,'_')+'.character.zip';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(e){this.fail(e);}finally{this.characterArchiveBusy=false;}},
  async inspectCharacterArchive(file){if(!file||this.characterArchiveBusy)return;this.characterArchiveBusy=true;try{if(file.size>512*1024*1024)throw Error(this.characterText('ZIP 不能超过512 MiB','ZIP exceeds 512 MiB'));const data=new FormData();data.append('file',file);const r=await fetch(api+'/archive/inspect',{method:'POST',credentials:'same-origin',body:data});const v=await r.json();if(!r.ok)throw Error(v.error?.message||'Invalid character ZIP');this.characterArchiveFile=file;this.characterArchivePreview=v;await this.$nextTick();this.$refs.characterImportDialog.showModal();}catch(e){this.fail(e);}finally{this.characterArchiveBusy=false;}},
  cancelCharacterImport(){this.$refs.characterImportDialog.close();this.characterArchiveFile=null;this.characterArchivePreview=null;},
  async importCharacterArchive(){if(!this.characterArchiveFile||this.characterArchiveBusy)return;this.characterArchiveBusy=true;try{const data=new FormData();data.append('file',this.characterArchiveFile);const r=await fetch(api+'/archive/import',{method:'POST',credentials:'same-origin',body:data});const v=await r.json();if(!r.ok)throw Error(v.error?.message||'Import failed');this.captureCharacterSlots();this.characterId=v.id;this.characterDraft=v;this.appearanceId=v.default_appearance_id||v.appearances[0]?.id||'';this.characterItems=[v,...this.characterItems];await this.restoreCharacterSlots();this.cancelCharacterImport();this.success(this.characterText('角色已导入为副本。','Character imported as a copy.'));}catch(e){this.fail(e);}finally{this.characterArchiveBusy=false;}},
  async exportCharacterSettings(){if(!this.characterAppearance?.definition_image_id){this.fail(Error(this.characterText('请先选择一张形象定义图。','Choose one appearance definition image first.')));return;}if(!this.characterAppearance?.summary?.trim()){await this.generateCharacterDescription();if(!this.characterAppearance?.summary?.trim())return;}const saved=await this.saveCharacter();if(!saved)return;try{await request('/v1/platform/imagine-studio/characters/'+encodeURIComponent(saved.id)+'/export',{appearance_id:this.appearanceId,revision:saved.revision},'POST',this.historyHeaders());await this.refreshRuns(true);this.success(this.characterText('形象设定 JSON 已输出，包含说明及内嵌图片。','Appearance JSON exported with description and embedded images.'));}catch(e){this.fail(e);}},
  characterInstruction(){const c=this.characterDraft,a=this.characterAppearance;if(!c||!a)return '';return `Character identity: ${c.name}. ${c.description}\nAppearance: ${a.name}. Visual style: ${a.style}. Body proportions: ${a.proportions||''}. Outfit and equipment: ${a.outfit}. ${a.description}\nAppearance guide: ${a.summary||''}`;},
  characterDesignPrompt(){if(!this.characterDraft?.name.trim()||!this.characterAppearance?.name.trim())return '';return ['Create a consistent character design reference sheet on a plain background. Include full-body front, three-quarter, side and back views and matching face closeups. Keep identity, proportions, costume and colors identical across all views. Reference images define identity; apply the requested appearance. No unrelated characters. Structured appearance parameters take precedence over any conflicting prose guide.',this.characterInstruction()].filter(Boolean).join('\n\n');}
 });
})();
