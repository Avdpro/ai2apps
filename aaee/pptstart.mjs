import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

puppeteer.use(StealthPlugin())
async function startPPT(options){
	return puppeteer.launch(options);
}

export default startPPT;
export {startPPT};
