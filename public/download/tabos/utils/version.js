//This file is based on https://github.com/alphaeadevelopment/parse-version-string.git

/*
In coke, disk verison is must be like: [major.minor.patch].
Package version can be extended like [major.minor.path-tag.versionIdx].
*/

const pattern = /([0-9]+)\.([0-9]+)\.([0-9]+)(-(([a-z]+)([.-]([0-9]+))?)?)?/;

Version=function(version){
	if (!version){
		return null;
	}

	let match = version.match(pattern);
	if (!match){
		return null;
	}

	let rv = {
		major: Number(match[1]),
		minor: Number(match[2]),
		patch: Number(match[3]),
	};
	if (match[5]) {
		rv.tag=match[6];
		rv.versionIdx=Number(match[8]);
	}
	return rv;
};

//----------------------------------------------------------------------------
//Check if text is valid version string
let valid=Version.valid=function(text){
	return !!Version(text);
};

//----------------------------------------------------------------------------
//Clean text to pure version-string.
let clean=Version.valid=function(text){
	let v=Version(text);
	if(!v){
		return null;
	}
	return `${v.major}.${v.minor}.${v.patch}`;
};

//----------------------------------------------------------------------------
//Compare two version
let compare=Version.compare=function(v1,v2)
{
	if(!v1 || !v2){
		return NaN;
	}
	if(v1.major>v2.major){
		return 1;
	}else if(v1.major<v2.major){
		return -1;
	}else if(v1.minor>v2.minor){
		return 1;
	}else if(v1.minor<v2.minor){
		return -1
	}else if(v1.patch>v2.patch){
		return 1;
	}else if(v1.patch<v2.patch){
		return -1;
	}else{
		return 0;
	}
};

//----------------------------------------------------------------------------
//Compare two version
let compareR=Version.compareR=function(v1,v2)
{
	return compare(v2,v1);
};

//----------------------------------------------------------------------------
//Compare two version-text
let compareText=Version.compareText=function(text1,text2)
{
	let v1,v2;
	v1=Version(text1);
	v2=Version(text2);
	return compare(v1,v2);
};

//----------------------------------------------------------------------------
//Compare two version-text
let compareTextR=Version.compareTextR=function(text1,text2){
	return Version.compareText(text2,text1);
};

let version=Version;
export default version;
export {version,valid,clean,compare,compareR,compareText,compareTextR};
