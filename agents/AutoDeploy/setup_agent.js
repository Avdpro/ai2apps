import pathLib from "path";

//----------------------------------------------------------------------------
//Exmaple of deploy/install steps:
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
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`npm install ws`,
				]
			}
		];
	}else if(env.platform==="linux" /*&& env.arch==="x64"*/){
		steps=[
			{
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`npm install ws`,
				]
			}
		];
	}else{
		steps=[
			{
				action:"bash",
				tip: (($ln==="CN")?("安装依赖"):/*EN*/("Install dependencies")),
				commands:[
					`npm install ws`,
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