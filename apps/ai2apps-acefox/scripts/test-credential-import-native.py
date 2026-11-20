#!/usr/bin/env python3
"""Isolated native transport fixture; never touches installed instance data or real keys."""
from pathlib import Path
import tempfile,threading,json,subprocess,os,socket,time,plistlib,sys,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
root=Path(tempfile.mkdtemp(prefix='ci-native-',dir='/private/tmp')).resolve()
source=(Path(__file__).resolve().parents[1]/'Sources/AI2AppsHelper/CredentialImportBroker.swift').read_text()
old='''directory = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/AI2Apps/credential-import", isDirectory: true)'''
assert old in source
source=source.replace(old,'directory = URL(fileURLWithPath: '+json.dumps(str(root/'sockets'))+')')
(root/'Broker.swift').write_text(source)
identity={'user_id':'synthetic-user','cloud_origin':'https://fixture.invalid','installation_id':'fixture','security_id':'source'}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  assert self.headers.get('Authorization')=='Bearer '+'f'*64
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if body.get('ticket'):
   value={'identity':{**identity,'security_id':'target','user_id':'synthetic-user','cloud_origin':'https://fixture.invalid'},'action':{'action':'list'},'target_versions':{}}
  else:
   value={'identity':identity,'offer_id':'synthetic-offer','providers':[{'key':'video:minimax','id':'minimax','kind':'video','version':'synthetic-version','ownership':'owned','config':{'name':'Synthetic provider','base_url':'https://fixture.invalid'}}]}
  data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
port=server.server_address[1]
main='''import Foundation
import Darwin
let mode=CommandLine.arguments[1]
let broker=CredentialImportBroker(instance:mode,name:mode,token:String(repeating:"f",count:64),port:{PORT})
do {try broker.start()} catch {print("START_FAILED",error);exit(1)}
if mode=="test" {
 Task {do {print(try await broker.perform(ticket:"synthetic-ticket"));fflush(stdout);exit(0)}catch {print("TARGET_FAILED",error);exit(1)}}
}
print("READY",mode);fflush(stdout)
dispatchMain()
'''.replace('PORT',str(port))
(root/'main.swift').write_text(main)
subprocess.run(['swiftc',str(root/'Broker.swift'),str(root/'main.swift'),'-o',str(root/'driver')],check=True)
programs={}
for instance in ['dev','test']:
 app=root/'.build'/f'AI2Apps-{instance}.app';helper=app/'Contents/Library/LoginItems/AI2AppsHelper.app';exe=helper/'Contents/MacOS/AI2AppsHelper';exe.parent.mkdir(parents=True)
 exe.write_bytes((root/'driver').read_bytes());exe.chmod(0o755)
 for bundle,info in [(app,{'CFBundleIdentifier':'com.ai2apps.desktop.'+instance,'AI2AppsInstanceID':instance,'CFBundleDisplayName':'Fixture '+instance}),(helper,{'CFBundleIdentifier':'com.ai2apps.desktop.'+instance+'.helper','CFBundleExecutable':'AI2AppsHelper'})]:
  (bundle/'Contents').mkdir(parents=True,exist_ok=True)
  (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
 subprocess.run(['codesign','--force','--sign','-','--identifier','com.ai2apps.desktop.'+instance+'.helper',str(exe)],check=True,capture_output=True)
 programs[instance]=exe
p=subprocess.Popen([str(programs['dev']),'dev'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
 ready=p.stdout.readline().strip();assert ready=='READY dev',ready
 assert (root/'sockets/dev.sock').stat().st_mode & 0o777 == 0o600
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(8);client.connect(str(root/'sockets/dev.sock'));client.sendall(b'{"op":"list"}\n')
  denied=json.loads(client.recv(4096));assert denied['ok'] is False,denied
 result=subprocess.run([str(programs['test']),'test'],capture_output=True,text=True,timeout=35)
 assert result.returncode==0,(result.stdout,result.stderr)
 data=json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
 assert data['sources'] and data['sources'][0]['id']=='dev',data
 for field,value in [('user_id','other-user'),('cloud_origin','https://other.invalid')]:
  saved=identity[field];identity[field]=value
  again=subprocess.run([str(programs['test']),'test'],capture_output=True,text=True,timeout=35)
  assert again.returncode==0,(again.stdout,again.stderr)
  filtered=json.loads(next(line for line in again.stdout.splitlines() if line.startswith('{')))
  assert filtered['sources']==[],filtered
  identity[field]=saved
 print(json.dumps({'different_account_and_cloud_filtered':'passed','native_socket_start':'passed','untrusted_process_rejected':'passed','signed_helper_same_account_discovery':'passed','count':len(data['sources']),'root':str(root)}))
finally:
 p.terminate();p.wait(timeout=5);server.shutdown();shutil.rmtree(root)
