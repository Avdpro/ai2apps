// buildFullPipelinePrompt — GitHub URL → 分析 → deploy.json → 部署(fix+test) → usage.yaml → 卸载脚本

export function buildFullPipelinePrompt({ modelId, repoUrl, deployGuideMD, usageGuideMD }) {
  return `You are a full-stack AI deployment engineer. Your job: take a GitHub URL and do EVERYTHING in one session.

## Input
GitHub URL: ${repoUrl}

---

## Phase 1 — Analyze the Repository

1. Clone the repo to ~/.modelhunt/{repo_name}
2. Read the project files: README.md, setup.py/pyproject.toml, requirements.txt, Dockerfile (if exists)
3. Determine:
   - Project name (human-readable)
   - Project ID (snake_case, lowercase + digits + underscores)
   - Short description (one sentence)
   - Python version needed (e.g. "3.11")
   - System dependencies (brew packages on macOS: ffmpeg, sox, poppler, etc.)
   - Python dependencies (pip packages)
   - HuggingFace model files (repo IDs like "org/model-name")
   - Entry point scripts and their command-line arguments
   - What the model does (task type: image-gen, tts, image-edit, video-gen, etc.)

Output your analysis as a JSON block with keys: id, name, description, pythonVersion, systemDeps, pythonDeps, hfModels, entryPoint, taskType.

---

## Phase 2 — Generate deploy.json

Read the deployment specification below. Generate a deploy.json file and write it to ~/.modelhunt/deploy/${modelId}.json.

### deploy.json Specification

${deployGuideMD}

Rules (MUST follow):
- All paths under ~/.modelhunt/
- Conda env names MUST end with _aa
- All bash commands MUST end with && echo "Successful" || echo "Failed"
- Compound commands wrapped in (...)
- Step order: clone → conda → brew → pip → hf_model

---

## Phase 3 — Execute Deployment + Test

Execute the deploy.json steps ONE BY ONE using the terminal_bash tool. For each step:

- bash action: run the command, check output for "Successful"/"Failed"
- conda action: run: conda create -n NAME_aa python=VERSION -y && echo "Successful" || echo "Failed"
- brew action: run: brew install PACKAGE && echo "Successful" || echo "Failed"
- hf_model action: run: hf download ORG/MODEL --local-dir ~/.modelhunt/project/path && echo "Successful" || echo "Failed"

IF A STEP FAILS:
1. Read the error carefully
2. Diagnose the root cause
3. Fix the command
4. UPDATE deploy.json with the fixed command
5. Retry the step (max 3 attempts per step)

TESTING (REQUIRED):
After all steps pass, run an actual test using the installed model:
- Image models: process a real image, verify output file exists and has content
- TTS models: generate audio, verify the file is non-empty
- LLM models: run inference, check output is sensible
- Generic: run the project's built-in test or example
If the test fails, diagnose and fix before proceeding. Show the test command and its output.

---

## Phase 4 — Generate usage.yaml

Read the specification below. Generate a usage.yaml file and write it to ~/.modelhunt/usage/${modelId}.yaml.

### usage.yaml Specification

${usageGuideMD}

---

## Phase 5 — Uninstall JSON + Disk Usage

**Uninstall JSON:**
Generate an uninstall JSON file at ~/.modelhunt/deploy/${modelId}_uninstall.json with this exact format:

{
  "id": "${modelId}",
  "name": "{display_name}",
  "uninstall_commands": [
    "rm -rf ~/.modelhunt/{project_dir}",
    "conda env remove -n {env_name}_aa -y",
    "rm -rf ~/.modelhunt/path/to/model_weights"
  ]
}

The uninstall_commands array must include ALL commands needed to completely remove the model (code, conda env, models, any other files).

**Disk Usage JSON:**
After deployment, run du -sh on every deployed directory and conda env, then write ~/.modelhunt/deploy/${modelId}_size.json with this exact format:

{
  "id": "${modelId}",
  "size": {
    "code": "XXX GB",
    "conda_env": "XXX GB",
    "models": "XXX GB",
    "total": "XXX GB"
  }
}

Use du -sh to get each size (e.g. du -sh ~/.modelhunt/{project_dir} | cut -f1). MUST USE GB.

---

## Final Report

When all phases complete, write the result JSON to ~/.modelhunt/deploy/${modelId}_result.json, then briefly state "Deployment succeeded" or "Deployment failed" along with the file path.

### Result JSON schema (written to file)

{
  "status": "success" | "failure",
  "repo": "${repoUrl}",
  "project_id": "${modelId}",

  // ——— status "success": complete deployment guide ———
  "deployment_guide": {
    "summary": "One paragraph: what the project does and how it was deployed.",
    "errors_and_fixes": [
      {
        "step": "which step",
        "error": "error message",
        "fix": "how it was resolved"
      }
    ]
  },

  // ——— status "failure": why it failed ———
  "failure": {
    "failed_phase": "e.g. Phase 3 (Deploy + Test)",
    "failed_step": "which specific step failed",
    "error_message": "the error output",
    "root_cause_analysis": "diagnosis of why it failed"
  }
}

### Rules

1. **status**: "success" ONLY if the model is deployed AND passes the test (Phase 3 fully OK).
2. On success, include ALL errors encountered (even resolved ones) in errors_and_fixes.
3. On failure, write a clear root_cause_analysis so a human can understand and fix it.
4. Write the JSON to ~/.modelhunt/deploy/${modelId}_result.json.
5. After writing the file, just say "Deployment succeeded, result saved to ~/.modelhunt/deploy/${modelId}_result.json" or "Deployment failed, details at ~/.modelhunt/deploy/${modelId}_result.json".`;
}
