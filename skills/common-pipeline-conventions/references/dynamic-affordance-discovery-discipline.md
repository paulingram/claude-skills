# Dynamic affordance discovery discipline (v2.13.0)

When the pipeline is given a codebase (either to review/audit or to build into), the intake phase MUST scan the codebase for **affordance signatures** — UI elements, libraries, and backend code paths that signal a user-facing capability (file upload, file download, real-time updates, notifications, etc.). Any affordance class that is **present in the code** but **not addressed in the run's requirements inventory** is a discipline failure: the run will silently leave the affordance unsupported and the user will hit it in production.

**Failure shape** (verbatim case in CHANGELOG v2.13.0): a codebase review *"missed dynamic requirements to handle file uplaods despite the site clearly having the need for this"* — the requirements inventory omitted **file-upload** even though the codebase clearly had file-upload code (`<input type="file">`, `enctype="multipart/form-data"`, `import multer`, S3 `PutObject`, "Upload" UI). The user caught it manually; v2.13.0 makes this structurally impossible.

### The rule (non-negotiable)

For every codebase the pipeline operates on, the intake phase produces an **affordance inventory** alongside the requirements inventory. The inventory enumerates which canonical affordance classes are detected in the codebase. Each detected class MUST then be addressed in one of three sanctioned ways:

1. **Addressed in requirements** — the requirements inventory carries an entry covering the affordance (e.g., a requirement for "file upload with progress + virus scan + S3 backing store").
2. **SR routed** — a solution requirement with `origin.kind: "affordance-coverage-gap"` is created so the orchestrator dispatches the right team in a follow-up run.
3. **Confirmed-stub** — an entry in `coverage-map.json` `confirmed_stubs[]` with `user_confirmed_at` explicitly stating the affordance is intentionally out of scope for this run.

A detected affordance class with NONE of the three is `affordance-not-addressed`. The new 13th Layer 3 tool `verify_affordance_coverage` is the gate.

### v2.13.0 ships one canonical affordance class: file-upload

The `_AFFORDANCE_SIGNATURES["file-upload"]` constant carries 25+ signature patterns spanning the full stack:

| Layer | Signature patterns (representative subset) |
|---|---|
| **HTML / DOM** | `<input type="file"`, `accept="image/*"`, `multiple` attribute on file inputs, `enctype="multipart/form-data"` |
| **JavaScript APIs** | `FileReader`, `new FormData()`, `input.files`, `event.dataTransfer.files`, `URL.createObjectURL` |
| **Drag-and-drop libraries** | `react-dropzone`, `@uppy/`, `filepond`, `dropzone-js`, `vue-upload-component`, `ng-file-upload` |
| **Backend middleware** | `multer`, `busboy`, `formidable`, `express-fileupload`, `koa-multer`, Django `FileField`, Flask `request.files`, FastAPI `UploadFile` |
| **Cloud storage SDKs** | AWS S3 `PutObject` / `createPresignedPost` / `getSignedUrl`, GCS `@google-cloud/storage`, Azure `BlobServiceClient`, Cloudinary `uploader.upload`, Uploadcare `uploadFile` |
| **UI text patterns** | "Upload", "Attach", "Add file", "Browse files", "Drop files here", "Choose file" |
| **Server routes** | `POST /upload`, `POST /files`, `POST /attachments`, `PUT /signed-url` |

The framework is extensible: future versions will add `file-download` (export, save-as, blob URLs, CSV/PDF generation), `realtime` (WebSocket, SSE, polling, Pusher, Supabase Realtime), `notifications` (in-app, push, email triggers), and others. v2.13.0 ships file-upload as the first canonical class.

### Severity

Single severity `affordance-not-addressed` with structured evidence:

```json
{
  "severity": "affordance-not-addressed",
  "affordance_kind": "file-upload",
  "signature_id": "html-file-input",
  "signature_pattern": "<input type=\"file\"",
  "matched_files": ["src/components/DocumentsPane.tsx:42", "src/api/routes/upload.ts:18"],
  "evidence": "codebase carries 'file-upload' signatures in 2 files; requirements_inventory.addressed_affordances does NOT include 'file-upload'.",
  "remediation": "Add a 'file-upload' requirement to the inventory, OR route via SR with origin.kind=affordance-coverage-gap, OR mark as confirmed-stub."
}
```

### Cross-references

- `hooks/vao_tools.py::verify_affordance_coverage` — the 13th Layer 3 tool.
- `hooks/vao_tools.py::_AFFORDANCE_SIGNATURES` + `_FILE_UPLOAD_AFFORDANCE_SIGNATURES` — the canonical signature dictionary + the v2.13.0 file-upload subset.
- `agents/system-architect.md` `## Dynamic affordance discovery discipline (v2.13.0)` — intake-mode affordance-scan + Master Review Audit gate.
- `agents/frontend.md` `## Dynamic affordance discovery discipline (v2.13.0)` — implementer cannot ship if a detected affordance is unaddressed.
- `agents/codebase-map-reviewer.md` `## Dynamic affordance discovery discipline (v2.13.0)` — CODEBASE_MAP.md must enumerate detected affordances.
- `tests/fixtures/vao/file-upload-affordance-missed.json` — verbatim user case (codebase carries `<input type="file">` + multer + S3 PutObject + "Upload Document" UI text; requirements miss the file-upload affordance).
- `tests/test_vao_affordance_coverage.py` + `tests/test_dynamic_affordance_discovery_discipline.py` — structural tests.
- New SR origin kind: `affordance-coverage-gap` joins the canonical list (`missing-api-for-frontend-element` / `cross-layer-backend-required` / `cross-layer-frontend-required` / `interaction-gap` / `live-data-wiring-gap` / `persona-path-coverage-gap`).
