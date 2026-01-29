//Auto genterated by Cody
import pathLib from "path";
import Base64 from "../../agenthub/base64.mjs";
import {trimJSON} from "../../agenthub/ChatSession.mjs";
import {URL} from "url";
/*#{1HDBOSUN90MoreImports*/
import {WebRpa,sleep} from "../../rpa/WebRpa.mjs";
/*}#1HDBOSUN90MoreImports*/
const agentURL=decodeURIComponent((new URL(import.meta.url)).pathname);
const baseURL=pathLib.dirname(agentURL);
const basePath=baseURL.startsWith("file://")?pathLib.fileURLToPath(baseURL):baseURL;
const VFACT=null;
/*#{1HDBOSUN90StartDoc*/
/*}#1HDBOSUN90StartDoc*/
//----------------------------------------------------------------------------
let twitterSearch=async function(session){
	let execInput;
	const $ln=session.language||"EN";
	let context,globalContext=session.globalContext;
	let self;
	let OpenPage,AccountBranch,ParseSearch,DeepSearch,DeepOpenPage,DeepParse,ClosePage,Return,Error,WaitFlag,TypeKeyword,ReadRes,CheckNumber,Scroll,ReadMore,Back2App,TipResult,ShowRes,ShowPage,ScrollDown,CheckRounds;
	let readRounds=0;
	
	/*#{1HDBOSUN90LocalVals*/
	/*}#1HDBOSUN90LocalVals*/
	
	function parseAgentArgs(input){
		execInput=input;
		/*#{1HDBOSUN90ParseArgs*/
		/*}#1HDBOSUN90ParseArgs*/
	}
	
	/*#{1HDBOSUN90PreContext*/
	/*}#1HDBOSUN90PreContext*/
	context={};
	/*#{1HDBOSUN90PostContext*/
	/*}#1HDBOSUN90PostContext*/
	let $agent,agent,segs={};
	segs["OpenPage"]=OpenPage=async function(input){//:1J9P7UIKE0
		let pageVal="aaPage";
		let $url="https://www.google.com";
		let $waitBefore=0;
		let $waitAfter=1000;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1J9P7UIKE0PreCodes*/
		// 构造一个url链接，为：https://x.com/{search}
		// 如果search以@开头，去掉@
		if(search.startsWith('@')){
			search = search.substring(1);
		}
		$url = `https://x.com/${search}`;
		/*}#1J9P7UIKE0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1J9P7UIKE0PostCodes*/
		/*}#1J9P7UIKE0PostCodes*/
		return {result:true};
	};
	OpenPage.jaxId="1J9P7UIKE0"
	OpenPage.url="OpenPage@"+agentURL
	
	segs["AccountBranch"]=AccountBranch=async function(input){//:1J9P8I5D20
		let result=true;
		let pageVal="aaPage";
		let $node=undefined;
		let $query="(//div[@data-testid=\"empty_state_header_text\"])";
		let $multi=false;
		let $options=undefined;
		let $waitBefore=1000;
		let $waitAfter=0;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1J9P8I5D20PreCodes*/
		page = globalContext.aaPage;
		context.webRpa = globalContext.webRpa;
		context[pageVal] = page;
		context.search = input.search;
		context.searchNum = input.searchNum;
		/*}#1J9P8I5D20PreCodes*/
		if($multi){
			result=await context.webRpa.queryNodes(page,$node,$query,$options);
		}else{
			result=await context.webRpa.queryNode(page,$node,$query,$options);
		}
		if((!result)||($multi && !result.length)){
			$waitAfter && (await sleep($waitAfter))
			/*#{1J9P8I5D20MissingCodes*/
			/*}#1J9P8I5D20MissingCodes*/
			return {seg:ParseSearch,result:(result),preSeg:"1J9P8I5D20",outlet:"1J9P8I5CD0"};
		}else{
			$waitAfter && (await sleep($waitAfter))
			/*#{1J9P8I5D20PostCodes*/
			/*}#1J9P8I5D20PostCodes*/
			return {seg:Error,result:(result),preSeg:"1J9P8I5D20",outlet:"1J9P8IDF00"};
		}
	};
	AccountBranch.jaxId="1J9P8I5D20"
	AccountBranch.url="AccountBranch@"+agentURL
	
	segs["ParseSearch"]=ParseSearch=async function(input){//:1J9P82PNB0
		let result=input
		try{
			/*#{1J9P82PNB0Code*/
			try {
					let $waitBefore = 1500;
					$waitBefore && (await sleep($waitBefore));
			
					// 使用WebRPA的页面实例进行DOM查询
					const page = context.aaPage;
			
					// 提取用户信息的函数
					// searchNum 和 search 变量是从外部作用域（agent函数）中获取的
					const {
						userInfo,
						posts
					} = await page.callFunction(async (searchNum, search) => {
			
						// 1. 提取用户信息 (与之前相同)
						let userInfo = {};
						try {
							// 提取显示名
							const displayNameElement = document.querySelector('[data-testid="UserName"] .css-146c3p1 .css-1jxf684 .css-1jxf684');
							if (displayNameElement) {
								userInfo.displayName = displayNameElement.textContent.trim();
							}
			
							// 提取用户名 @
							const usernameElement = document.querySelector('[data-testid="UserName"] .css-146c3p1[style*="color: rgb(113, 118, 123)"] .css-1jxf684');
							if (usernameElement) {
								userInfo.username = usernameElement.textContent.trim();
							} else {
								// 备用方案：从URL提取 (因为 search 变量就是我们要的)
								userInfo.username = search.startsWith('@') ? search : '@' + search;
							}
			
							// 提取用户简介
							const descElement = document.querySelector('[data-testid="UserDescription"] .css-1jxf684');
							if (descElement) {
								userInfo.description = descElement.textContent.trim();
							}
			
							// 提取关注数
							const followingLink = document.querySelector('a[href$="/following"]');
							if (followingLink) {
								const followingSpan = followingLink.querySelector('.css-1jxf684[style*="color: rgb(231, 233, 234)"] .css-1jxf684');
								if (followingSpan) {
									userInfo.following = followingSpan.textContent.trim();
								}
							}
			
							// 提取粉丝数
							const followersLink = document.querySelector('a[href$="/verified_followers"], a[href$="/followers"]');
							if (followersLink) {
								const followersSpan = followersLink.querySelector('.css-1jxf684[style*="color: rgb(231, 233, 234)"] .css-1jxf684');
								if (followersSpan) {
									userInfo.followers = followersSpan.textContent.trim();
								}
							}
			
							// 提取订阅数
							const subscriptionLink = document.querySelector('a[href*="/subscriptions"]');
							if (subscriptionLink) {
								const subscriptionSpan = subscriptionLink.querySelector('.css-1jxf684[style*="color: rgb(231, 233, 234)"] .css-1jxf684');
								if (subscriptionSpan) {
									userInfo.subscription = subscriptionSpan.textContent.trim();
								}
							}
			
							// 提取加入时间
							const joinDateElement = document.querySelector('[data-testid="UserJoinDate"] .css-1jxf684');
							if (joinDateElement) {
								userInfo.joinDate = joinDateElement.textContent.trim();
							}
			
							// 提取专业分类
							const categoryElement = document.querySelector('[data-testid="UserProfessionalCategory"] button .css-1jxf684');
							if (categoryElement) {
								userInfo.category = categoryElement.textContent.trim();
							}
			
							// 提取网站链接
							const websiteElement = document.querySelector('[data-testid="UserUrl"] .css-1jxf684:last-child');
							if (websiteElement) {
								userInfo.website = websiteElement.textContent.trim();
							}
			
							// 提取头像URL
							const avatarImg = document.querySelector('[data-testid*="UserAvatar-Container"] img');
							if (avatarImg) {
								userInfo.avatarUrl = avatarImg.src;
							}
			
						} catch (error) {
							console.error('提取用户信息时出错:', error);
						}
			
						// 2. 提取帖子 URL (新逻辑)
						let posts = [];
						let seenUrls = new Set();
						let scrollAttempts = 0;
						const maxScrollAttempts = 10; // 最大连续失败滚动次数
						const scrollWait = 2500; // 每次滚动后等待加载的时间
						const username = search; // 确保使用传入的 search 变量
						const urlPattern = `/${username}/status/`; // 过滤模式
			
						// 初始滚动两次
						window.scrollTo(0, document.body.scrollHeight);
						await new Promise(resolve => setTimeout(resolve, scrollWait));
						window.scrollTo(0, document.body.scrollHeight);
						await new Promise(resolve => setTimeout(resolve, scrollWait));
			
						// 开始循环提取
						while (posts.length < searchNum && scrollAttempts < maxScrollAttempts) {
							let lastHeight = document.body.scrollHeight;
			
							// 查找页面上所有的推文 <article>
							const articles = document.querySelectorAll('article[data-testid="tweet"]');
			
							articles.forEach(article => {
								if (posts.length >= searchNum) return; // 如果已达标，停止添加
			
								// 查找包含 <time> 标签的链接，这是指向推文状态的规范链接
								const timeLink = article.querySelector('a[href*="/status/"] time');
								if (timeLink) {
									const linkElement = timeLink.closest('a');
									if (linkElement) {
										let href = linkElement.getAttribute('href'); // 示例: /aigclink/status/123456
			
										// 1. 过滤：必须包含 /${username}/status/
										if (href && href.includes(urlPattern)) {
			
											// 2. 规范化 URL
											const url = `https://x.com${href}`;
			
											// 3. 去重
											if (!seenUrls.has(url)) {
												seenUrls.add(url);
												posts.push({
													url: url
												});
											}
										}
									}
								}
							});
			
							// 如果数量还不够，则继续滚动
							if (posts.length < searchNum) {
								window.scrollTo(0, document.body.scrollHeight);
								await new Promise(resolve => setTimeout(resolve, scrollWait));
			
								// 检查是否滚动到了底部（没有新内容加载）
								if (document.body.scrollHeight === lastHeight) {
									scrollAttempts++;
									console.log(`滚动到底部，尝试次数 ${scrollAttempts}/${maxScrollAttempts}`);
								} else {
									scrollAttempts = 0; // 加载了新内容，重置尝试次数
								}
							}
						} // 结束 while 循环
			
						// 返回 userInfo 和 posts
						return {
							userInfo,
							posts
						};
			
					}, [searchNum, search]); // 将外部变量 searchNum 和 search 传入 page.callFunction
			
					// 3. 构建最终返回结果
					result = {
						res: 'Finish',
						userInfo: userInfo,
						posts: posts
					};
			
				} catch (e) {
					// 错误处理
					result = {
						res: 'Fail',
						info: e.message,
						error: e.toString()
					};
				}
			/*}#1J9P82PNB0Code*/
		}catch(error){
			/*#{1J9P82PNB0ErrorCode*/
			/*}#1J9P82PNB0ErrorCode*/
		}
		return {result:result};
	};
	ParseSearch.jaxId="1J9P82PNB0"
	ParseSearch.url="ParseSearch@"+agentURL
	
	segs["DeepSearch"]=DeepSearch=async function(input){//:1J9PAU9900
		let result=input;
		let list=input;
		let i,n,item,loopR;
		/*#{1J9PAU9900PreLoop*/
		const userInfo = input.userInfo;
		const search_results = [];
		list = input.posts;
		/*}#1J9PAU9900PreLoop*/
		n=list.length;
		for(i=0;i<n;i++){
			item=list[i];
			/*#{1J9PAU9900InLoopPre*/
			/*}#1J9PAU9900InLoopPre*/
			loopR=await session.runAISeg(agent,DeepOpenPage,item,"1J9PAU9900","1J9PAUFCI2")
			if(loopR==="break"){
				break;
			}
			/*#{1J9PAU9900InLoopPost*/
			if (loopR) {
			search_results.push(loopR);
			}
			/*}#1J9PAU9900InLoopPost*/
		}
		/*#{1J9PAU9900PostCodes*/
		result = {
		userInfo: userInfo,
		search_results: search_results
		};
		/*}#1J9PAU9900PostCodes*/
		return {result:result};
	};
	DeepSearch.jaxId="1J9PAU9900"
	DeepSearch.url="DeepSearch@"+agentURL
	
	segs["DeepOpenPage"]=DeepOpenPage=async function(input){//:1J9PAUP6D0
		let pageVal="aaPage";
		let $url=input;
		let $waitBefore=0;
		let $waitAfter=0;
		let $width=800;
		let $height=600;
		let $userAgent="";
		let $timeout=(undefined)||0;
		let page=null;
		let $openOpts={timeout:$timeout};
		$waitBefore && (await sleep($waitBefore));
		/*#{1J9PAUP6D0PreCodes*/
		$url = $url.url;
		/*}#1J9PAUP6D0PreCodes*/
		context[pageVal]=page=await context.rpaBrowser.newPage();
		($width && $height) && (await page.setViewport({width:$width,height:$height}));
		$userAgent && (await page.setUserAgent($userAgent));
		await page.goto($url,$openOpts);
		$waitAfter && (await sleep($waitAfter));
		/*#{1J9PAUP6D0PostCodes*/
		return {seg:DeepParse,result:(input),preSeg:"1J9PAUP6D0",outlet:"1J9PAV14T0"};
		/*}#1J9PAUP6D0PostCodes*/
		return {seg:DeepParse,result:(true),preSeg:"1J9PAUP6D0",outlet:"1J9PAV14T0"};
	};
	DeepOpenPage.jaxId="1J9PAUP6D0"
	DeepOpenPage.url="DeepOpenPage@"+agentURL
	
	segs["DeepParse"]=DeepParse=async function(input){//:1J9PB7AP70
		let result=input
		try{
			/*#{1J9PB7AP70Code*/
			// 'input' from DeepOpenPage is the loop item, e.g., { url: "..." }
			try {
			// let $waitBefore = 1500;
			// $waitBefore && (await sleep($waitBefore));
			const page = context.aaPage;
			const currentUrl = input.url; // Get URL from the loop item
			await page.waitForSelector('div[data-testid="tweetText"]', { timeout: 10000 }); // 最多等待10秒
			
			
			const extractedData = await page.callFunction(async (url) => {
			let metadata = {
			Reply: "0",
			Repost: "0",
			Like: "0",
			BookMark: "0",
			publishTime: ""
			};
			let full_content = "";
			
			// Helper function to get count from metadata bar
			// We must find the main article container
			const getCount = (articleEl, testId) => {
			if (!articleEl) return "0";
			const el = articleEl.querySelector(`button[data-testid="${testId}"] span[data-testid="app-text-transition-container"]`);
			return (el ? el.textContent.trim() : "0") || "0";
			};
			
			try {
			// Find the main tweet article on the page
			// This query targets the main article, not replies in a thread
			const article = document.querySelector('article[data-testid="tweet"]');
			if (!article) {
			throw new Error("Could not find main tweet article.");
			}
			
			// 1. Extract Full Content
			const contentEl = article.querySelector('div[data-testid="tweetText"]');
			if (contentEl) {
			const spans = contentEl.querySelectorAll('span');
			let texts = [];
			spans.forEach(span => {
			// Exclude buttons like "Show translation"
			if (!span.closest('button')) {
			texts.push(span.textContent);
			}
			});
			// Join text and filter out empty strings
			full_content = texts.filter(Boolean).join('').trim();
			}
			
			// 2. Extract Metadata Counts
			metadata.Reply = getCount(article, "reply");
			metadata.Repost = getCount(article, "retweet");
			metadata.Like = getCount(article, "like");
			metadata.BookMark = getCount(article, "bookmark");
			
			// 3. Extract Publish Time
			// The time is in an 'a' tag containing a 'time' element
			const timeEl = article.querySelector('a[href*="/status/"] > time[datetime]');
			if (timeEl) {
			metadata.publishTime = timeEl.textContent.trim();
			}
			
			} catch (e) {
			console.error("Error during DeepParse execution in browser:", e.message);
			}
			
			return {
			url: url, // Pass the original URL through
			metadata: metadata,
			full_content: full_content
			};
			}, [currentUrl]); // Pass the URL into the browser context
			
			result = extractedData; // This is the object { url, metadata, full_content }
			
			} catch (e) {
			console.error("Error in DeepParse seg:", e.message);
			// Return a partial object on error to avoid breaking the loop
			result = { 
			url: input.url, 
			metadata: {
			Reply: "E", Repost: "E", Like: "E", BookMark: "E", publishTime: "E"
			}, 
			full_content: `Error: Could not parse. ${e.message}`
			};
			}
			/*}#1J9PB7AP70Code*/
		}catch(error){
			/*#{1J9PB7AP70ErrorCode*/
			/*}#1J9PB7AP70ErrorCode*/
		}
		return {result:result};
	};
	DeepParse.jaxId="1J9PB7AP70"
	DeepParse.url="DeepParse@"+agentURL
	
	segs["ClosePage"]=ClosePage=async function(input){//:1J9PBM8TH0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.close();
		context[pageVal]=null;
		waitAfter && (await sleep(waitAfter))
		return {result:result};
	};
	ClosePage.jaxId="1J9PBM8TH0"
	ClosePage.url="ClosePage@"+agentURL
	
	segs["Return"]=Return=async function(input){//:1J9PSIP8M0
		let result=input
		try{
			/*#{1J9PSIP8M0Code*/
			result = result.search_results
			/*}#1J9PSIP8M0Code*/
		}catch(error){
			/*#{1J9PSIP8M0ErrorCode*/
			/*}#1J9PSIP8M0ErrorCode*/
		}
		return {result:result};
	};
	Return.jaxId="1J9PSIP8M0"
	Return.url="Return@"+agentURL
	
	segs["Error"]=Error=async function(input){//:1J9PSK5AR0
		let result=input
		try{
			/*#{1J9PSK5AR0Code*/
			result ={
				"search_results":[]
			}
			/*}#1J9PSK5AR0Code*/
		}catch(error){
			/*#{1J9PSK5AR0ErrorCode*/
			/*}#1J9PSK5AR0ErrorCode*/
		}
		return {seg:Return,result:(result),preSeg:"1J9PSK5AR0",outlet:"1J9PSKCAM0"};
	};
	Error.jaxId="1J9PSK5AR0"
	Error.url="Error@"+agentURL
	
	segs["WaitFlag"]=WaitFlag=async function(input){//:1JBHHCNF50
		let result=true;
		let pageVal="aaPage";
		let $flag="$WaitFlag";
		let $waitBefore=0;
		let $waitAfter=200;
		let page=context[pageVal];
		$waitBefore && (await sleep($waitBefore));
		/*#{1JBHHCNF50PreCodes*/
		page = globalContext.aaPage;
		context[pageVal] = page;
		context.webRpa = globalContext.webRpa;
		context.search = input.search;
		context.searchNum = input.searchNum;
		context.comments = input.comments;
		console.log("input.comments",input.comments);
		/*}#1JBHHCNF50PreCodes*/
		try{
			result=await context[$flag];
		}catch(error){
			return {result:error};
		}
		$waitAfter && (await sleep($waitAfter))
		/*#{1JBHHCNF50PostCodes*/
		/*}#1JBHHCNF50PostCodes*/
		return {seg:TypeKeyword,result:(result),preSeg:"1JBHHCNF50",outlet:"1JBHHD4CE1"};
	};
	WaitFlag.jaxId="1JBHHCNF50"
	WaitFlag.url="WaitFlag@"+agentURL
	
	segs["TypeKeyword"]=TypeKeyword=async function(input){//:1JB45QRSC0
		let result=true;
		let pageVal="aaPage";
		let $action="Type";
		let $query="(//input[@data-testid='SearchBox_Search_Input'])";
		let $queryHint="";
		let $key=context.search;
		let $options={};
		let $waitBefore=200;
		let $waitAfter=500;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		/*#{1JB45QRSC0PreCodes*/
		//page = globalContext.aaPage;
		//context[pageVal] = page;
		//context.webRpa = globalContext.webRpa;
		//context.search = input.search;
		//context.searchNum = input.searchNum;
		/*}#1JB45QRSC0PreCodes*/
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JB45QRSC0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.type($query,$key,$options||{});
		}else{
			$pms=page.keyboard.type($key,$options||{});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		/*#{1JB45QRSC0PostCodes*/
		await page.keyboard.press('Enter');
		/*}#1JB45QRSC0PostCodes*/
		return {seg:ReadRes,result:(result),preSeg:"1JB45QRSC0",outlet:"1JB45TP9I0"};
	};
	TypeKeyword.jaxId="1JB45QRSC0"
	TypeKeyword.url="TypeKeyword@"+agentURL
	
	segs["ReadRes"]=ReadRes=async function(input){//:1JB47O9T70
		let result=input
		try{
			/*#{1JB47O9T70Code*/
			let page = context['aaPage'];
			//const timeline = await page.waitForSelector('div[aria-label="Timeline: Search timeline"]');
			const searchResults = await page.callFunction((searchNumber) => {
				const elements = document.querySelectorAll('div[data-testid="cellInnerDiv"]');
				console.log(elements,"elements");
				const results = [];
				
				if(elements){
					for (let el of elements) {
					const title = el.querySelector('div[data-testid="tweetText"]') ? el.querySelector('div[data-testid="tweetText"]').textContent.trim() : '';
					
					const author = el.querySelector('div[data-testid="User-Name"] a') ? el.querySelector('div[data-testid="User-Name"] a').textContent.trim() : '';
					
					const timeElements = el.querySelector('time');
					const time = timeElements ? timeElements.textContent.trim() : '';
					
					const urlElements = el.querySelector('a[href*="/status/"]');
					const url = urlElements ? 'https://twitter.com' + urlElements.getAttribute('href') : '';
					
					const replyElements = el.querySelector('span[data-testid="app-text-transition-container"]');
					const reply = replyElements ? replyElements.textContent.trim() : '';
					
					const allNumElements = el.querySelector('[aria-label*="replies,"]'); 
					const label = allNumElements ? allNumElements.getAttribute('aria-label') : ''; // "19 replies, 7 reposts, 68 likes, 18 bookmarks, 37236 views"
					const obj = {};
					if(label){
						label.match(/(\d+)\s+(\w+)/g).forEach(pair => {
							const [num, key] = pair.split(' '); 
							obj[key] = Number(num);
						});
					};
					
					const user = url.match(/^https?:\/\/twitter\.com\/([^\/]+)/)?.[1];
					const avatarImg =  document.querySelector(`a[href="/${user}"] img[src*="profile_images"]`);
					const avatarUrl = avatarImg ? avatarImg.src : '';
						
					console.log("obj ReadRes",obj)
					
					if(title && url){
						results.push({
							title,
							author,
							time,
							url,
							replies:obj.replies,
							reposts:obj.reposts,
							likes:obj.likes,
							bookmarks:obj.bookmarks,
							views:obj.views,
							avatarUrl,
						});
					};
				}
				}
				return results;
			},[context.searchNum]);
			console.log("searchResults",searchResults);
			//console.log("input",input);
			const prevResults = Array.isArray(input) ? input : [];                       
			const newPage = searchResults;                     
			const merged = prevResults.concat(newPage);
			context.finds= merged.length ? merged.slice(0,context.searchNum) : [];
			console.log("merged length", merged.length);
			result = context.finds;
			/*}#1JB47O9T70Code*/
		}catch(error){
			/*#{1JB47O9T70ErrorCode*/
			/*}#1JB47O9T70ErrorCode*/
		}
		return {seg:CheckNumber,result:(result),preSeg:"1JB47O9T70",outlet:"1JB47P5OF0"};
	};
	ReadRes.jaxId="1JB47O9T70"
	ReadRes.url="ReadRes@"+agentURL
	
	segs["CheckNumber"]=CheckNumber=async function(input){//:1JB4GD74L0
		let result=input;
		if(readRounds===0 && context.finds.length<context.searchNum && readRounds<10){
			return {seg:ShowPage,result:(input),preSeg:"1JB4GD74L0",outlet:"1JCFTQH2N0"};
		}
		if(context.finds.length<context.searchNum && readRounds<10){
			return {seg:ScrollDown,result:(input),preSeg:"1JB4GD74L0",outlet:"1JCIGU4JL0"};
		}
		return {seg:CheckRounds,result:(result),preSeg:"1JB4GD74L0",outlet:"1JB4GFCSK1"};
	};
	CheckNumber.jaxId="1JB4GD74L0"
	CheckNumber.url="CheckNumber@"+agentURL
	
	segs["Scroll"]=Scroll=async function(input){//:1JB4GFHVR0
		let result=input
		try{
			/*#{1JB4GFHVR0Code*/
			const page = context['aaPage'];
			await page.callFunction((searchNum) => {
				window.scrollTo(0, document.body.scrollHeight);
			},[context.searchNum]);
			/*}#1JB4GFHVR0Code*/
		}catch(error){
			/*#{1JB4GFHVR0ErrorCode*/
			/*}#1JB4GFHVR0ErrorCode*/
		}
		return {result:result};
	};
	Scroll.jaxId="1JB4GFHVR0"
	Scroll.url="Scroll@"+agentURL
	
	segs["ReadMore"]=ReadMore=async function(input){//:1JB4GJ65S0
		let result=input;
		/*#{1JB4GJ65S0PreCodes*/
		readRounds+=1;
		/*}#1JB4GJ65S0PreCodes*/
		return {seg:ReadRes,result:result,preSeg:"1JB47O9T70",outlet:"1JB4GKJ220"};
	
	};
	ReadMore.jaxId="1JB47O9T70"
	ReadMore.url="ReadMore@"+agentURL
	
	segs["Back2App"]=Back2App=async function(input){//:1JB4GL3J30
		let result=input;
		let waitBefore=0;
		let waitAfter=0;
		let browser=context.rpaBrowser;
		waitBefore && (await sleep(waitBefore));
		/*#{1JB4GL3J30PreCodes*/
		/*}#1JB4GL3J30PreCodes*/
		if(browser){
			await browser.backToApp();
		}
		waitAfter && (await sleep(waitAfter))
		/*#{1JB4GL3J30PostCodes*/
		context.finds = result;
		/*}#1JB4GL3J30PostCodes*/
		return {seg:TipResult,result:(result),preSeg:"1JB4GL3J30",outlet:"1JB4GLKHG0"};
	};
	Back2App.jaxId="1JB4GL3J30"
	Back2App.url="Back2App@"+agentURL
	
	segs["TipResult"]=TipResult=async function(input){//:1JB4JA1RS0
		let result=input;
		let $channel="Process";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=input;
		/*#{1JB4JA1RS0PreCodes*/
		content=`共找到：${context.finds.length}条笔记。`;
		/*}#1JB4JA1RS0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JB4JA1RS0PostCodes*/
		const markdown = context.finds
  			.map((d, i) => `${i + 1}. [${d.title.slice(0, 20)}${d.title.length > 20 ? '…' : ''}](${d.url})`)
  			.filter(line => line !== '')   
  			.join('\n');
		
		result = {
			markdown,
			finds: context.finds
		};
		/*}#1JB4JA1RS0PostCodes*/
		return {seg:ShowRes,result:(result),preSeg:"1JB4JA1RS0",outlet:"1JB4JB1AP0"};
	};
	TipResult.jaxId="1JB4JA1RS0"
	TipResult.url="TipResult@"+agentURL
	
	segs["ShowRes"]=ShowRes=async function(input){//:1JB4JCSAK0
		let result=input;
		let $channel="Chat";
		let opts={txtHeader:($agent.showName||$agent.name||null),channel:$channel};
		let role="assistant";
		let content=(($ln==="CN")?(input.markdown ? input.markdown : '未搜索到数据'):(input.markdown ? input.markdown : 'No data found'));
		/*#{1JB4JCSAK0PreCodes*/
		/*}#1JB4JCSAK0PreCodes*/
		session.addChatText(role,content,opts);
		/*#{1JB4JCSAK0PostCodes*/
		result = {
			...input,
			comments: context.comments
		}
		/*}#1JB4JCSAK0PostCodes*/
		return {seg:ClosePage,result:(result),preSeg:"1JB4JCSAK0",outlet:"1JB4JE3VI0"};
	};
	ShowRes.jaxId="1JB4JCSAK0"
	ShowRes.url="ShowRes@"+agentURL
	
	segs["ShowPage"]=ShowPage=async function(input){//:1JCIH72IO0
		let result=input;
		let pageVal="aaPage";
		let waitBefore=0;
		let waitAfter=0;
		let $options={"focusBrowser":true};
		let page=context[pageVal];
		waitBefore && (await sleep(waitBefore));
		await page.bringToFront($options);
		waitAfter && (await sleep(waitAfter))
		return {seg:ScrollDown,result:(result),preSeg:"1JCIH72IO0",outlet:"1JCIHAK0V0"};
	};
	ShowPage.jaxId="1JCIH72IO0"
	ShowPage.url="ShowPage@"+agentURL
	
	segs["ScrollDown"]=ScrollDown=async function(input){//:1JCIH8BBJ0
		let result=true;
		let pageVal="aaPage";
		let $query="";
		let $queryHint="";
		let $deltaX=0;
		let $deltaY=500;
		let $options={"steps":10};
		let $waitBefore=500;
		let $waitAfter=0;
		let page=context[pageVal];
		let $async=false;
		let $pms=null;
		$waitBefore && (await sleep($waitBefore));
		if($query||$queryHint){
			$query=$queryHint?(await context.webRpa.confirmQuery(page,$query,$queryHint,"1JCIH8BBJ0")):$query;
			if(!$query) throw Error("Missing query. Query hint: "+$queryHint);
			$pms=page.mouseWheel($query,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}else{
			$pms=page.mouseWheel(null,{...$options,deltaX:$deltaX||0,deltaY:$deltaY||100});
		}
		if($pms && (!$async)){await $pms;}$waitAfter && (await sleep($waitAfter))
		return {seg:ReadMore,result:(result),preSeg:"1JCIH8BBJ0",outlet:"1JCIHAK100"};
	};
	ScrollDown.jaxId="1JCIH8BBJ0"
	ScrollDown.url="ScrollDown@"+agentURL
	
	segs["CheckRounds"]=CheckRounds=async function(input){//:1JCIHD9RO0
		let result=input;
		if(readRounds===0){
			return {seg:TipResult,result:(input),preSeg:"1JCIHD9RO0",outlet:"1JCIHFEGP0"};
		}
		return {seg:Back2App,result:(result),preSeg:"1JCIHD9RO0",outlet:"1JCIHFEGP1"};
	};
	CheckRounds.jaxId="1JCIHD9RO0"
	CheckRounds.url="CheckRounds@"+agentURL
	
	agent=$agent={
		isAIAgent:true,
		session:session,
		name:"twitterSearch",
		url:agentURL,
		autoStart:true,
		jaxId:"1HDBOSUN90",
		context:context,
		livingSeg:null,
		execChat:async function(input){
			let result;
			parseAgentArgs(input);
			/*#{1HDBOSUN90PreEntry*/
			/*}#1HDBOSUN90PreEntry*/
			result={seg:WaitFlag,"input":input};
			/*#{1HDBOSUN90PostEntry*/
			/*}#1HDBOSUN90PostEntry*/
			return result;
		},
		/*#{1HDBOSUN90MoreAgentAttrs*/
		/*}#1HDBOSUN90MoreAgentAttrs*/
	};
	/*#{1HDBOSUN90PostAgent*/
	/*}#1HDBOSUN90PostAgent*/
	return agent;
};
/*#{1HDBOSUN90ExCodes*/
/*}#1HDBOSUN90ExCodes*/

//#CodyExport>>>
//#CodyExport<<<
/*#{1HDBOSUN90PostDoc*/
/*}#1HDBOSUN90PostDoc*/


export default twitterSearch;
export{twitterSearch};
/*Cody Project Doc*/
//{
//	"type": "docfile",
//	"def": "DocAIAgent",
//	"jaxId": "1HDBOSUN90",
//	"attrs": {
//		"editObjs": {
//			"jaxId": "1HDBOSUNA0",
//			"attrs": {
//				"agent": {
//					"type": "objclass",
//					"def": "ObjClass",
//					"jaxId": "1HDBOSUNA4",
//					"attrs": {
//						"constructArgs": {
//							"jaxId": "1HDBOSUNB0",
//							"attrs": {}
//						},
//						"properties": {
//							"jaxId": "1HDBOSUNB1",
//							"attrs": {}
//						},
//						"functions": {
//							"jaxId": "1HDBOSUNB2",
//							"attrs": {}
//						},
//						"mockupOnly": "false",
//						"nullMockup": "false",
//						"exportType": "UI Data Template",
//						"exportClass": "false",
//						"superClass": ""
//					},
//					"mockups": {}
//				}
//			}
//		},
//		"agent": {
//			"jaxId": "1HDBOSUNA1",
//			"attrs": {}
//		},
//		"showName": "",
//		"entry": "WaitFlag",
//		"autoStart": "true",
//		"inBrowser": "false",
//		"debug": "true",
//		"apiArgs": {
//			"jaxId": "1IH2869AD0",
//			"attrs": {}
//		},
//		"localVars": {
//			"jaxId": "1HDBOSUNA2",
//			"attrs": {
//				"readRounds": {
//					"type": "number",
//					"valText": "0"
//				}
//			}
//		},
//		"context": {
//			"jaxId": "1HDBOSUNA3",
//			"attrs": {}
//		},
//		"globalMockup": {
//			"jaxId": "1HDIJB7SK6",
//			"attrs": {}
//		},
//		"segs": {
//			"attrs": [
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1J9P7UIKE0",
//					"attrs": {
//						"id": "OpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "100",
//						"y": "675",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P7UU560",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P7UU561",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "https://www.google.com",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "1000",
//						"outlet": {
//							"jaxId": "1J9P7UU550",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaQuery",
//					"jaxId": "1J9P8I5D20",
//					"attrs": {
//						"id": "AccountBranch",
//						"viewName": "",
//						"label": "",
//						"x": "110",
//						"y": "760",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P8IDF20",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P8IDF21",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"node": "",
//						"query": "(//div[@data-testid=\"empty_state_header_text\"])",
//						"queryHint": "",
//						"multi": "false",
//						"options": "",
//						"waitBefore": "1000",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J9P8IDF00",
//							"attrs": {
//								"id": "Found",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PSK5AR0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AISegOutlet",
//									"jaxId": "1J9P8I5CD0",
//									"attrs": {
//										"id": "Missing",
//										"desc": "输出节点。"
//									},
//									"linkedSeg": "1J9P82PNB0"
//								}
//							]
//						}
//					},
//					"icon": "/@aae/assets/wait_find.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J9P82PNB0",
//					"attrs": {
//						"id": "ParseSearch",
//						"viewName": "",
//						"label": "",
//						"x": "390",
//						"y": "800",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9P832511",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9P832512",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9P832510",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "loopArray",
//					"jaxId": "1J9PAU9900",
//					"attrs": {
//						"id": "DeepSearch",
//						"viewName": "",
//						"label": "",
//						"x": "870",
//						"y": "795",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PAUFCI0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PAUFCI1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"loopArray": "#input",
//						"method": "forEach",
//						"outlet": {
//							"jaxId": "1J9PAUFCI2",
//							"attrs": {
//								"id": "Looper",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PAUP6D0"
//						},
//						"catchlet": {
//							"jaxId": "1J9PAUFCH0",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "loop_array.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaOpenPage",
//					"jaxId": "1J9PAUP6D0",
//					"attrs": {
//						"id": "DeepOpenPage",
//						"viewName": "",
//						"label": "",
//						"x": "1125",
//						"y": "780",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PAV1510",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PAV1511",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"valName": "aaPage",
//						"url": "#input",
//						"vpWidth": "800",
//						"vpHeight": "600",
//						"userAgent": "",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J9PAV14T0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PB7AP70"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_add.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J9PB7AP70",
//					"attrs": {
//						"id": "DeepParse",
//						"viewName": "",
//						"label": "",
//						"x": "1385",
//						"y": "780",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PBK7JO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PBK7JO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9PBK7JL0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaClosePage",
//					"jaxId": "1J9PBM8TH0",
//					"attrs": {
//						"id": "ClosePage",
//						"viewName": "",
//						"label": "",
//						"x": "1855",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PBMF3R0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PBMF3R1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1J9PBMF3Q0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_close.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J9PSIP8M0",
//					"attrs": {
//						"id": "Return",
//						"viewName": "",
//						"label": "",
//						"x": "580",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PSJ71Q0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PSJ71Q1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9PSJ71J0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1J9PSK5AR0",
//					"attrs": {
//						"id": "Error",
//						"viewName": "",
//						"label": "",
//						"x": "390",
//						"y": "720",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1J9PSKCAO0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1J9PSKCAO1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1J9PSKCAM0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PSIP8M0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaWaitFor",
//					"jaxId": "1JBHHCNF50",
//					"attrs": {
//						"id": "WaitFlag",
//						"viewName": "",
//						"label": "",
//						"x": "80",
//						"y": "135",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JBHHD4CM0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JBHHD4CM1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"flag": "$WaitFlag",
//						"waitBefore": "0",
//						"waitAfter": "200",
//						"outlet": {
//							"jaxId": "1JBHHD4CE1",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB45QRSC0"
//						},
//						"catchlet": {
//							"jaxId": "1JBHHD4CE0",
//							"attrs": {
//								"id": "Error",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "/@aae/assets/wait_await.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "AAFKeyboardAction",
//					"jaxId": "1JB45QRSC0",
//					"attrs": {
//						"id": "TypeKeyword",
//						"viewName": "",
//						"label": "",
//						"x": "300",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB45TP9O0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB45TP9O1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Type",
//						"query": "(//input[@data-testid='SearchBox_Search_Input'])",
//						"queryHint": "",
//						"key": "#context.search",
//						"async": "false",
//						"options": "null",
//						"waitBefore": "200",
//						"waitAfter": "500",
//						"outlet": {
//							"jaxId": "1JB45TP9I0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB47O9T70"
//						},
//						"run": ""
//					},
//					"icon": "keybtn.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JB47O9T70",
//					"attrs": {
//						"id": "ReadRes",
//						"viewName": "",
//						"label": "",
//						"x": "530",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB47P5ON0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB47P5ON1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB47P5OF0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4GD74L0"
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JB4GD74L0",
//					"attrs": {
//						"id": "CheckNumber",
//						"viewName": "",
//						"label": "",
//						"x": "745",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4GFCSS0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4GFCSS1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB4GFCSK1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JCIHD9RO0"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCFTQH2N0",
//									"attrs": {
//										"id": "ShowPage",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCFTRRRV0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCFTRRRV1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0 && context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JCIH72IO0"
//								},
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIGU4JL0",
//									"attrs": {
//										"id": "More",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIGU4JR0",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIGU4JR1",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#context.finds.length<context.searchNum && readRounds<10"
//									},
//									"linkedSeg": "1JCIH8BBJ0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				},
//				{
//					"type": "aiseg",
//					"def": "code",
//					"jaxId": "1JB4GFHVR0",
//					"attrs": {
//						"id": "Scroll",
//						"viewName": "",
//						"label": "",
//						"x": "1250",
//						"y": "515",
//						"desc": "这是一个AISeg。",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4GFT2I0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4GFT2I1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JB4GFT290",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							}
//						},
//						"outlets": {
//							"attrs": []
//						},
//						"result": "#input",
//						"errorSeg": ""
//					},
//					"icon": "tab_css.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "jumper",
//					"jaxId": "1JB4GJ65S0",
//					"attrs": {
//						"id": "ReadMore",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"seg": "1JB47O9T70",
//						"outlet": {
//							"jaxId": "1JB4GKJ220",
//							"attrs": {
//								"id": "Next",
//								"desc": "输出节点。"
//							}
//						}
//					},
//					"icon": "arrowupright.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaBackToApp",
//					"jaxId": "1JB4GL3J30",
//					"attrs": {
//						"id": "Back2App",
//						"viewName": "",
//						"label": "",
//						"x": "1245",
//						"y": "205",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4GLKHN0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4GLKHN1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JB4GLKHG0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4JA1RS0"
//						}
//					},
//					"icon": "/@tabos/shared/assets/aalogo.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JB4JA1RS0",
//					"attrs": {
//						"id": "TipResult",
//						"viewName": "",
//						"label": "",
//						"x": "1465",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4JCN3H0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4JCN3H1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Process",
//						"text": "#input",
//						"outlet": {
//							"jaxId": "1JB4JB1AP0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4JCSAK0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "output",
//					"jaxId": "1JB4JCSAK0",
//					"attrs": {
//						"id": "ShowRes",
//						"viewName": "",
//						"label": "",
//						"x": "1685",
//						"y": "175",
//						"desc": "这是一个AISeg。",
//						"codes": "true",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JB4JGA8V0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JB4JGA8V1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"role": "Assistant",
//						"channel": "Chat",
//						"text": {
//							"type": "string",
//							"valText": "#input.markdown ? input.markdown : 'No data found'",
//							"localize": {
//								"EN": "#input.markdown ? input.markdown : 'No data found'",
//								"CN": "#input.markdown ? input.markdown : '未搜索到数据'"
//							},
//							"localizable": true
//						},
//						"outlet": {
//							"jaxId": "1JB4JE3VI0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1J9PBM8TH0"
//						}
//					},
//					"icon": "hudtxt.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaActivePage",
//					"jaxId": "1JCIH72IO0",
//					"attrs": {
//						"id": "ShowPage",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "70",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHAK1C0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHAK1C1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"options": "{\"focusBrowser\":true}",
//						"waitBefore": "0",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JCIHAK0V0",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JCIH8BBJ0"
//						},
//						"run": ""
//					},
//					"icon": "/@aae/assets/tab_tap.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "WebRpaMouseAction",
//					"jaxId": "1JCIH8BBJ0",
//					"attrs": {
//						"id": "ScrollDown",
//						"viewName": "",
//						"label": "",
//						"x": "1240",
//						"y": "120",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHAK1C2",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHAK1C3",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"page": "aaPage",
//						"action": "Mouse Wheel",
//						"query": "",
//						"queryHint": "",
//						"dx": "0",
//						"dy": "0",
//						"deltaX": "0",
//						"deltaY": "500",
//						"async": "false",
//						"options": "{\"steps\":10}",
//						"waitBefore": "500",
//						"waitAfter": "0",
//						"outlet": {
//							"jaxId": "1JCIHAK100",
//							"attrs": {
//								"id": "Result",
//								"desc": "输出节点。"
//							},
//							"linkedSeg": "1JB4GJ65S0"
//						},
//						"run": ""
//					},
//					"icon": "mouse.svg"
//				},
//				{
//					"type": "aiseg",
//					"def": "brunch",
//					"jaxId": "1JCIHD9RO0",
//					"attrs": {
//						"id": "CheckRounds",
//						"viewName": "",
//						"label": "",
//						"x": "1010",
//						"y": "190",
//						"desc": "这是一个AISeg。",
//						"codes": "false",
//						"mkpInput": "$$input$$",
//						"segMark": "None",
//						"context": {
//							"jaxId": "1JCIHFEGV0",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"global": {
//							"jaxId": "1JCIHFEGV1",
//							"attrs": {
//								"cast": ""
//							}
//						},
//						"outlet": {
//							"jaxId": "1JCIHFEGP1",
//							"attrs": {
//								"id": "Default",
//								"desc": "输出节点。",
//								"output": ""
//							},
//							"linkedSeg": "1JB4GL3J30"
//						},
//						"outlets": {
//							"attrs": [
//								{
//									"type": "aioutlet",
//									"def": "AIConditionOutlet",
//									"jaxId": "1JCIHFEGP0",
//									"attrs": {
//										"id": "Zero",
//										"desc": "输出节点。",
//										"output": "",
//										"codes": "false",
//										"context": {
//											"jaxId": "1JCIHFEGV2",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"global": {
//											"jaxId": "1JCIHFEGV3",
//											"attrs": {
//												"cast": ""
//											}
//										},
//										"condition": "#readRounds===0"
//									},
//									"linkedSeg": "1JB4JA1RS0"
//								}
//							]
//						}
//					},
//					"icon": "condition.svg",
//					"reverseOutlets": true
//				}
//			]
//		},
//		"desc": "这是一个AI代理。",
//		"exportAPI": "false",
//		"exportAddOn": "false",
//		"addOnOpts": ""
//	}
//}