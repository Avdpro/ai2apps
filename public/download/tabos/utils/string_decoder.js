function StringDecoder(encoding){
	this.decoder=new TextDecoder(encoding);
}
let stringDecoder=StringDecoder.prototype={};

stringDecoder.write=function(buf){
	return this.decoder.decode(buf,{stream:true});
};

stringDecoder.end=function(buf){
	return this.decoder.decode(buf,{stream:false});
};


export default StringDecoder;
export {StringDecoder};