# Deployment Path Verification Report

## Issue Identified
The repository was reorganized with all application code moved into the `markdone-universal/` subdirectory. This requires verification that deployment scripts still work correctly.

## Current Directory Structure
```
/Users/linhvh/IBM-Bob/MarkDone-v2/
├── docs/                          # Documentation (repo root)
├── markdone-universal/            # Application subdirectory
│   ├── Containerfile              # Docker/Podman build file
│   ├── deploy.sh                  # Deployment script
│   ├── podman-kube.yaml          # Kubernetes manifest
│   ├── deno.json                 # Deno configuration
│   ├── server.ts                 # Main server file
│   ├── services/                 # Python conversion services
│   ├── static/                   # Frontend files
│   ├── tests/                    # Test files
│   └── ...
```

## Verification Results

### ✅ Containerfile (Lines 48-68)
**Status**: CORRECT

```dockerfile
WORKDIR /app
COPY . /app
```

**Analysis**: 
- Build context is `markdone-universal/` directory (from deploy.sh line 12)
- `COPY . /app` copies everything from `markdone-universal/` into `/app`
- `deno cache server.ts` runs in `/app` where `server.ts` exists
- All paths resolve correctly

### ✅ deploy.sh (Lines 4-12)
**Status**: CORRECT

```bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"
podman build -t "localhost/${IMAGE_NAME}:${IMAGE_TAG}" -f ./Containerfile .
```

**Analysis**:
- `PROJECT_DIR` resolves to `markdone-universal/` directory
- Build context (`.`) is `markdone-universal/`
- Containerfile path (`./Containerfile`) is relative to `markdone-universal/`
- All paths resolve correctly

### ✅ deploy.sh VAULT_PATH (Line 22)
**Status**: CORRECT

```bash
VAULT_PATH="$(cd "${PROJECT_DIR}/../outputs" && pwd)"
```

**Analysis**:
- Goes up one level from `markdone-universal/` to repo root
- Then into `outputs/` directory at repo root level
- This is intentional - vault output is stored outside the container subdirectory
- Path resolves correctly

### ✅ podman-kube.yaml
**Status**: CORRECT

**Analysis**:
- All paths are container-internal (`/app/*`)
- Volume mount maps host `{{VAULT_PATH}}` to container `/app/outputs/vault`
- No dependency on host directory structure
- All paths resolve correctly

### ✅ server.ts Python Subprocess Calls
**Status**: CORRECT

```typescript
const proc = new Deno.Command("python3", {
  args: [
    "services/high_fidelity_pdf.py",  // Relative to cwd
    // ...
  ],
  cwd: Deno.cwd(),  // /app in container, markdone-universal/ in dev
}).spawn();
```

**Analysis**:
- Paths are relative to `Deno.cwd()`
- In container: `/app` (where server.ts is)
- In development: `markdone-universal/` (where server.ts is)
- Python scripts are in `services/` subdirectory in both cases
- All paths resolve correctly

## Potential Issues Found

### ⚠️ Containerfile CMD (Line 72)
**Current**:
```dockerfile
CMD ["deno", "run", "--allow-all", "server.ts"]
```

**Issue**: Uses `--allow-all` (security concern - this is one of the issues we're fixing)

**Fix Required**: Will be addressed in Phase 4 of implementation plan

## Recommendations

### 1. No Path Changes Needed
All deployment paths are correct and work with the `markdone-universal/` subdirectory structure.

### 2. Update Containerfile CMD (Part of Implementation)
When implementing permission restrictions, update line 72:

**Before**:
```dockerfile
CMD ["deno", "run", "--allow-all", "server.ts"]
```

**After**:
```dockerfile
CMD ["deno", "run", "--allow-net", "--allow-read", "--allow-write", "--allow-env", "--allow-run=python3,pandoc", "server.ts"]
```

### 3. Documentation Update
Add note to README.md about the subdirectory structure:

```markdown
## Project Structure

The application code is located in the `markdone-universal/` subdirectory:
- All deployment scripts should be run from within `markdone-universal/`
- The vault output directory is at the repository root level (`../outputs/`)
```

## Testing Checklist

When implementing changes, verify:

- [ ] `cd markdone-universal && ./deploy.sh` builds successfully
- [ ] Container starts and server.ts runs
- [ ] Python scripts execute from correct paths
- [ ] Static files serve correctly
- [ ] Vault output writes to correct host directory
- [ ] All relative paths in server.ts resolve correctly

## Conclusion

✅ **All deployment paths are correct** and work properly with the `markdone-universal/` subdirectory structure. No path fixes are required.

The only change needed is updating the Containerfile CMD to use restricted permissions instead of `--allow-all`, which is already part of the implementation plan (Phase 4).

---

**Verified**: 2026-04-26  
**Status**: Ready for implementation