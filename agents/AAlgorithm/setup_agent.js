import pathLib from "path";

//----------------------------------------------------------------------------
function install(env,project){
	let $ln=env.$ln||"EN";
	let steps;
	let dirPath,gitPath,gitURL;
	dirPath=project.dirPath;
	gitPath=pathLib.join(dirPath,"prj");
	gitURL=project.gitURL;
	if(env.platform==="darwin" /*&& env.arch==="arm64"*/){
		steps=[
			{
				action:"conda",
				tip:(($ln==="CN")?("配置conda环境。"):/*EN*/("Set up conda environment.")),
				conda:"AIDraw",
				pythonVersion:"3.10",
			},
			{
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`pip install websockets`,
					`pip install openai`,
					`pip install nest_asyncio`,
				]
			}
		];
	}else if(env.platform==="linux" /*&& env.arch==="x64"*/){
		steps=[
			{
				action:"conda",
				tip:(($ln==="CN")?("配置conda环境。"):/*EN*/("Set up conda environment.")),
				conda:"AIDraw",
				pythonVersion:"3.10",
			},
			{
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`pip install websockets`,
					`pip install openai`,
					`pip install nest_asyncio`,
				]
			}
		];
	}else{
		steps=[
			{
				action:"conda",
				tip:(($ln==="CN")?("配置conda环境。"):/*EN*/("Set up conda environment.")),
				conda:"AIDraw",
				pythonVersion:"3.10",
			},
			{
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`pip install websockets`,
					`pip install openai`,
					`pip install nest_asyncio`,
				]
			}
		];
	}
	return steps;
}

//----------------------------------------------------------------------------
function uninstall(env,project){
	let $ln=env.$ln||"EN";
	let steps;
	let dirPath,gitPath,gitURL;
	dirPath=project.dirPath;
	gitPath=pathLib.join(dirPath,"prj");
	gitURL=project.gitURL;
	if(env.platform==="darwin" && env.arch==="arm64"){
		steps=[];
	}
	return steps;
};

export default install;
export {install,uninstall}