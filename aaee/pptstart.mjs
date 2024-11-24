import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

puppeteer.use(StealthPlugin())
async function startPPT(options){
	if(options.pipe!==false){
		options.pipe=true;
	}
	return puppeteer.launch(options);
}

export default startPPT;
export {startPPT};
