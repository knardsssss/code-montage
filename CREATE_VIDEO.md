# Create a video

Complete [installation](INSTALLATION.md) first. The brief and starter prompt below are reusable examples: edit them to match your current project.

## 1. Prepare resources and a brief

Place articles, PDF/DOCX documents, media, and reference videos under `resources/` inside this repository. Copy selected news manually from the newsletter process; no scraper integration is needed here. Include the article title, publisher, URL and date with the source text.

From the repository root (`code-montage/`), copy the example into a new run folder:

```bash
mkdir -p runs/my-first-video
cp runs/example/brief.md runs/my-first-video/brief.md
```

Edit the copied brief. Its current fields are **Project ID, Title, Duration, Voiceover language, Subtitles language, Newspaper path, and Remarks**. Add, remove, rename, or change fields as needed. Use Remarks for audience, required points, exclusions, style, budget, or other instructions that matter for this run.

Use paths relative to the repository root for sources. The example's newspaper path is a placeholder: replace it with a real file before starting. Supporting documents and media can be referenced in Remarks or in additional fields. Keep the Project ID unique for each production.

## 2. Launch OpenCode

From the repository root (`code-montage/`), activate the existing environment:

```bash
source venv/bin/activate
```

Choose one interface:

| Interface | Command | Next step |
| --- | --- | --- |
| Terminal / CLI | `opencode` | Enter instructions in the terminal conversation. |
| Web | `opencode web --hostname 127.0.0.1 --port 4096` | Open the printed local URL and select `code-montage` as the project. |

Keep the web server's terminal open while using the browser; stop it with Ctrl+C. If port 4096 is busy, choose another port. Use Build mode when the agent needs to execute production tools.

## 3. Choose or change the model

For now, use **Big Pickle** under the **OpenCode Zen** label. Availability can change without notice. If it is absent, check with the team about a replacement.

- **Terminal:** enter `/models`, find the OpenCode Zen group, and select Big Pickle. To change models later, use `/models` again. If provider authentication is required, use `/connect` and follow the provider's prompts.
- **Web:** open the model selector near the message composer, choose the OpenCode Zen group and Big Pickle, and complete provider connection if prompted. Use the same selector to change models later.

Confirm the selected model before sending the production request. A model-provider connection for OpenCode does not configure OpenMontage's separate production-provider keys.

## 4. Create, switch, or resume a session

| Action | Terminal | Web |
| --- | --- | --- |
| Start a new conversation | Enter `/new`. | Choose the new-session control. |
| Switch conversations | Enter `/sessions` and select the intended session. | Select the session in the project's session list. |
| Resume after closing | Launch `opencode --continue` from the repository root for the last session, or use `/sessions`. | Restart the web server from the repository root and select the existing session. |

Use a new session and Project ID for a separate video. For revisions to an existing video, return to its session and name the relevant artifact/version. A new conversation does not automatically create a separate production directory. Sessions are stored by OpenCode in its local application data, while production artifacts remain in this repository.

## 5. Send an editable starter prompt

Copy this prompt into OpenCode and change the brief path. Adapt the instructions and checkpoints as needed; they are a starting workflow, not a fixed application specification. The agent should use the languages and duration in your current brief.

```text
Use OpenMontage to create a compliance video from
runs/my-first-video/brief.md and the source files it references.
Read OpenMontage/AGENT_GUIDE.md and OpenMontage/PROJECT_CONTEXT.md,
then follow the appropriate pipeline and stage instructions.

Work only inside this code-montage repository. Do not inspect or modify sibling
projects. Run OpenMontage commands from its own directory using the
already activated repository-root venv; do not create another one.
Use the brief's Project ID for OpenMontage/projects/<project-id>/.

Treat the current brief as the source of project requirements. Ask about
missing information that is necessary to proceed. Check that the sources
are readable, the requested narration language and subtitle fonts are
supported, and rendering prerequisites are available. Report any proposed
provider costs before using paid services.

Use programmatic graphics, licensed sourced media, or supplied media.
Do not generate AI images or AI video clips, including fallback assets.
Flag uncertain claims or conflicting sources and cite factual statements.

Start with an alignment proposal and stop for my review. Then work
through script, storyboard/scene plan, media, and final video, waiting
for my explicit approval at each checkpoint before proceeding.
Map these checkpoints to the chosen upstream pipeline before starting.
Save versioned deliverables and provide actual file paths in chat.
Use Backlot-compatible production artifacts where supported.
```

## 6. Review and request revisions

Review the proposal, script, scene plan, media, and final video through the links OpenCode provides. Check factual references, regulatory interpretation, timing, narration, subtitle translation, and audiovisual quality. Scanned PDFs may need OCR; ask the agent to report unreadable source content before drafting.

Send feedback and approvals in OpenCode, for example:

```text
Revise script v1: explain the reporting deadline more clearly and cite
its source. Keep the other approved points. Stop after the revision.
```

```text
Approve script v2. Proceed to the storyboard only, then stop for review.
```

Check that the agent actually pauses at your chosen checkpoints. If an approved script changes, review affected scenes and media again.

## 7. Inspect Backlot and access the video

In a second terminal, from the repository root (`code-montage/`):

```bash
source venv/bin/activate
cd OpenMontage
python -m backlot open
```

To open one production, use its Project ID, for example:

```bash
python -m backlot open my-first-video
```

Backlot reads the production artifacts for visual inspection. Submit feedback and approval through OpenCode. Some documents may be available only through their file links.

Outputs are under `OpenMontage/projects/<project-id>/`, usually in `renders/`. Ask OpenCode for the exact MP4 and subtitle paths, then open them through your file manager. Watch the complete video before final approval.

The example brief is kept in Git; other run files, resources, credentials, and the OpenMontage checkout are ignored locally. Share completed videos deliberately through the team's agreed location.

See the upstream [OpenCode terminal commands](https://opencode.ai/docs/tui/), [web interface](https://opencode.ai/docs/web/), and [Backlot guide](https://github.com/calesthio/OpenMontage/blob/main/backlot/README.md) for interface details.
