"""Harness-owned artifact transport, bounded ZIPs and document ingestion."""
import asyncio
from pathlib import Path
import stat
import tempfile
import zipfile

from ai2apps.api.ownership import authorize_session
from ai2apps.services import ServiceInstanceStatus, ServiceRuntimeMode, ToolProviderError
from ai2apps.services.aaat import principal_for
from .local_directories import relative

TOOLS = ('artifact.materialize', 'artifact.pack', 'artifact.unpack', 'document.import_artifact')
MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 64


class Materials:
    def __init__(self, runtime):
        self.runtime = runtime

    def artifact(self, context, identifier):
        return self.runtime.workspace.get_artifact(context.session_id, identifier)

    def pack(self, args, context):
        ids = args['artifact_ids']
        if not 1 <= len(ids) <= MAX_FILES or len(set(ids)) != len(ids):
            raise ValueError('Choose 1–64 distinct artifacts')
        artifacts = [self.artifact(context, identifier) for identifier in ids]
        if sum(a.size_bytes for a in artifacts) > MAX_BYTES: raise ValueError('ZIP inputs exceed 256 MiB')
        with tempfile.TemporaryDirectory(prefix='harness-zip-') as temp:
            target = Path(temp)/'archive.zip'; names = set()
            with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for artifact in artifacts:
                    name = artifact.name
                    relative(name)
                    if name in names:
                        p = Path(name); i = 1
                        while f'{p.stem} ({i}){p.suffix}' in names: i += 1
                        name = f'{p.stem} ({i}){p.suffix}'
                    names.add(name)
                    archive.write(self.runtime.workspace.artifact_path(artifact), name)
            if target.stat().st_size > MAX_BYTES: raise ValueError('ZIP output exceeds 256 MiB')
            output = self.runtime.workspace.import_artifact(context.session_id, target,
                name=args.get('name','archive.zip'), run_id=context.trace_id, media_type='application/zip')
        return {'status':'completed','artifact_id':output.id,'name':output.name,'size_bytes':output.size_bytes,
                'file_count':len(artifacts),'sha256':output.content_hash}

    def unpack(self, args, context):
        artifact = self.artifact(context, args['artifact_id'])
        if artifact.size_bytes > MAX_BYTES: raise ValueError('ZIP exceeds 256 MiB')
        with zipfile.ZipFile(self.runtime.workspace.artifact_path(artifact)) as archive, tempfile.TemporaryDirectory(prefix='harness-unzip-') as temp:
            entries = archive.infolist()
            if len(entries) > MAX_FILES: raise ValueError('ZIP has more than 64 entries')
            if sum(i.file_size for i in entries) > MAX_BYTES: raise ValueError('ZIP expands beyond 256 MiB')
            names = set(); staged = []
            for i, entry in enumerate(entries):
                parts = relative(entry.filename)
                mode = entry.external_attr >> 16
                if not parts or ':' in entry.filename or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):
                    raise ValueError('Unsafe ZIP entry')
                canonical = '/'.join(parts)
                if canonical in names: raise ValueError('Duplicate ZIP entry')
                names.add(canonical)
                if entry.is_dir(): continue
                if entry.flag_bits & 1: raise ValueError('Encrypted ZIP is unsupported')
                target = Path(temp)/str(i)
                count = 0
                with archive.open(entry) as src, target.open('wb') as dst:
                    while chunk := src.read(1024 * 1024):
                        count += len(chunk)
                        if count > entry.file_size or count > MAX_BYTES: raise ValueError('ZIP size mismatch')
                        dst.write(chunk)
                staged.append((entry.filename, target))
            # Validate the entire archive before exposing any extracted artifacts.
            outputs = []
            for original, target in staged:
                result = self.runtime.workspace.import_artifact(context.session_id, target,
                    name=Path(original).name, run_id=context.trace_id, metadata={'archive_path':original,'source_artifact':artifact.id})
                outputs.append({'artifact_id':result.id,'path':original,'name':result.name,'size_bytes':result.size_bytes,'sha256':result.content_hash})
        return {'status':'completed','files':outputs,'file_count':len(outputs)}

    def document(self, args, context):
        from ai2apps.documents.repository import MAX_ATTACHMENT_BYTES
        artifact = self.artifact(context, args['artifact_id'])
        if artifact.size_bytes > MAX_ATTACHMENT_BYTES: raise ValueError('Document exceeds 25 MiB')
        item = self.runtime.documents.create(context.session_id,filename=artifact.name,media_type=artifact.media_type,
            data=self.runtime.workspace.artifact_path(artifact).read_bytes(),metadata={'source_artifact':artifact.id})
        parsed = self.runtime.documents.parse(context.session_id,item.id)
        return {'attachment_id':item.id,'filename':item.filename,'status':parsed.status.value,'error':parsed.error,
                'next_capability':'document.read', 'note':'Only extracted text is available. Scanned pages may require OCR; no OCR or model generation is started automatically.'}


def install(runtime):
    service = runtime.services.ensure_service(service_key='ai2apps.harness.materials',package_id='ai2apps.harness.materials',
        package_version='1',display_name='Harness artifact utilities',runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=('artifacts','documents'))
    instance = runtime.services.ensure_instance(service_id=service.id,provider_key='builtin:harness-materials',
        status=ServiceInstanceStatus.RUNNING,endpoint=None,health={'status':'ok'})
    owner = Materials(runtime)
    identifier = {'type':'string','minLength':1,'maxLength':256}
    specs = [
        ('artifact.materialize', {'artifact_id':identifier,'path':{'type':'string','minLength':1,'maxLength':4096}}, ['artifact_id','path'],
         lambda a,c:runtime.workspace.materialize_artifact(c.session_id,a['artifact_id'],a['path']),
         'Copy an owned Session artifact into a new Session workspace file for further processing. Does not write to the host filesystem. Existing destinations are rejected.'),
        ('artifact.pack', {'artifact_ids':{'type':'array','minItems':1,'maxItems':64,'uniqueItems':True,'items':identifier},
                           'name':{'type':'string','minLength':1,'maxLength':255}}, ['artifact_ids'], owner.pack,
         'Pack 1–64 owned Session artifacts into one ZIP artifact, up to 256 MiB. Duplicate filenames are renamed. Use host.directory.export to save the actual output to a named local folder.'),
        ('artifact.unpack', {'artifact_id':identifier}, ['artifact_id'], owner.unpack,
         'Extract a ZIP artifact into owned Session artifacts, up to 64 entries and 256 MiB expanded. Rejects links, traversal, encryption and duplicate paths. Preserves original archive paths as metadata; does not write to a host directory.'),
        ('document.import_artifact', {'artifact_id':identifier}, ['artifact_id'], owner.document,
         'Parse an owned Session artifact as a document (PDF, DOCX, PPTX, XLSX, CSV, TXT, Markdown, JSON or HTML; up to 25 MiB). Returns attachment_id for document.info, document.read and document.search. PDF text extraction does not imply OCR of scanned images. Local files must first use host.directory.import; do not ask for re-upload when the user already named the directory.'),
    ]
    for name, properties, required, action, description in specs:
        runtime.services.ensure_tool(service_id=service.id, qualified_name=name, display_name=name,
            description=description, input_schema={'type':'object','properties':properties,'required':required,'additionalProperties':False},
            output_schema={'type':'object'},effects=('workspace.write',),timeout_ms=120000)
        async def handler(args, context, action=action):
            try:
                if not context.session_id: raise PermissionError('Owned Session required')
                authorize_session(runtime,principal_for(runtime,context),context.session_id)
                return await asyncio.to_thread(action,args,context)
            except (OSError, ValueError, PermissionError, zipfile.BadZipFile) as error:
                raise ToolProviderError(str(error)) from error
        runtime.service_registry.bind_tool(name,provider_key=instance.provider_key,handler=handler)
    return owner
