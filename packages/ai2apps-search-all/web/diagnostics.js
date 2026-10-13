(function(global){'use strict';
const lt=globalThis.MiniAppI18n?.text||(s=>s),it=globalThis.MiniAppI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
 const hints={
 search_network_protocol_error:[lt('The browser network protocol failed while opening the search page. One retry was attempted. Try again, or select Bing or another source.'),lt('打开搜索页时浏览器网络协议出错，已重试一次。请稍后重试，或选择 Bing 等其它来源。')],
 custom_search_results_unavailable:[lt("The custom website did not yield verified search result cards. Check its search page and sign-in in the selected browser profile, or try a more specific query."),lt("自定义网站未提取到经过校验的搜索结果。请检查该网站搜索页及所选分身的登录状态，或使用更具体的关键词。")],
 custom_search_consequential_target:[lt("The website action was not a read-only search and was stopped. Check the search entry or try its search page URL."),lt("网站操作不属于只读搜索，已停止。请检查搜索入口，或重新添加该网站的搜索页 URL。")],
 search_api_failed:[lt('Search API failed. Check the configured API key, provider access, quota and network.'),lt('搜索 API 失败。请检查配置的密钥、服务访问权限、额度和网络。')],
 xiaohongshu_sort_not_verified:[lt('The requested sort order could not be confirmed on Xiaohongshu. Try Custom mode with Recommended order, or another source.'),lt('未能确认小红书已切换到指定排序。可在自定义模式尝试“综合”，或使用其它来源。')],
 xiaohongshu_sort_wrong_page:[lt('Xiaohongshu redirected away from search. Check sign-in in the selected browser profile.'),lt('小红书跳离搜索页，请检查所选浏览器分身中的登录状态。')],
 authentication:[lt('Sign in using the selected browser Profile, then retry this source.'),lt('请在所选浏览器分身中登录该网站，再重试此来源。')],
 captcha:[lt('Complete verification in the task panel. Do not keep retrying while verification is pending.'),lt('请在任务栏打开页面完成验证码，验证期间不要反复重试。')],
 search_navigation_failed:[lt('The search page could not load. Check connectivity and retry this source.'),lt('搜索页未能加载。请检查网络连接后重试此来源。')],
 search_page_not_loaded:[lt('The search page is still empty. Open the retained page, check connectivity or sign-in, then retry.'),lt('搜索页仍为空白。可打开保留页面检查网络或登录状态，再重试。')],
 search_markup_unavailable:[lt('The page loaded but no readable result cards were found. Inspect the search page; try again after loading, or use another source if its layout changed.'),lt('页面已加载，但没有识别到可读取的结果卡片。请检查搜索页是否加载完整；重试后仍失败，可换一个源，或反馈页面结构变化。')],
 provider_unavailable:[lt('The website reported a service or rate-limit error. Wait before retrying, or choose another source.'),lt('网站报告服务错误或请求频率限制。请稍后重试，或切换其他来源。')],
 custom_search_planner_timeout:[lt('Planning this website search timed out. Retry or use another source.'),lt('规划此网站搜索已超时，请重试或使用其它来源。')],
 custom_search_planner_invalid_action:[lt('The search plan could not be validated. No invalid browser action was executed. Retry or use another source.'),lt('搜索规划未通过校验，未执行无效网页操作。请重试或使用其它来源。')],
 unexpected_search_page:[lt('The website redirected away from its search page. Check sign-in and the retained page before retrying.'),lt('网站跳转到了其他页面。请检查登录状态和保留的搜索页，再重试。')],
 no_valid_search_results:[lt('No usable article links were extracted. Check the search page or adjust your query.'),lt('未提取到有效文章链接。请检查搜索页，或调整关键词。')],
 task_failed:[lt('The task failed. Check its record in the task panel and retry after resolving the reported issue.'),lt('任务执行失败。请在任务栏查看运行记录，处理具体问题后重试。')]};
 global.SearchAllDiagnostics=Object.freeze({explain:(code,en)=>(hints[code]||hints.task_failed)[en?0:1]});
})(typeof window==='undefined'?globalThis:window);
