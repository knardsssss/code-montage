# Installation

Each teammate installs the tools and clones OpenMontage on their own computer. These instructions assume macOS; run the commands in Terminal (Zsh or Bash).

## 1. Create or activate the root virtual environment

Start in the parent repository root (`3-points-project1/`), with `Video-Gen-Test/` directly below it:

```bash
python --version
python -m venv venv
source venv/bin/activate
```

If a compatible `venv/` already exists, skip creation and activate it. Keep it active for subsequent steps. Do not create another environment inside `Video-Gen-Test/` or OpenMontage.

OpenMontage requires Python 3.10 or newer; Python 3.11 is not specifically required. These guides use `python` consistently. If it is missing or points to an older version, install a supported Python from [python.org](https://www.python.org/downloads/). If your system calls it `python3`, use that for the version check and environment creation; after activation, use `python`.

## 2. Install Git and system prerequisites

Install Git, Node.js 22 LTS with npm, and FFmpeg (including `ffprobe`). Skip anything already installed.

With [Homebrew](https://brew.sh/) installed:

```bash
brew install git node@22 ffmpeg
```

Follow Homebrew's PATH instructions for Node. Alternatively, install Git through Apple's command-line tools with `xcode-select --install`, then follow the installer prompts. See the [Git installation guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

Check the installed tools:

```bash
git --version
python --version
node --version
npm --version
ffmpeg -version
ffprobe -version
```

Python requirements do not install these system tools. If you obtained the parent repository as a ZIP, install Git before cloning OpenMontage below.

## 3. Clone OpenMontage and install Python dependencies

From the parent repository root, with `venv/` active:

```bash
git clone https://github.com/calesthio/OpenMontage.git Video-Gen-Test/OpenMontage
python -m pip install --upgrade pip
python -m pip install -r Video-Gen-Test/requirements.txt
```

Skip the clone if you already have that checkout. OpenMontage is an independent, ignored checkout inside the trial folder. It must exist before installing requirements because our requirements file includes its Python requirements. Install only `Video-Gen-Test/requirements.txt` for this trial; sibling projects' requirements are not needed.

## 4. Install the compositor and prepare resources

From the parent repository root:

```bash
cd Video-Gen-Test/OpenMontage
npm install --prefix remotion-composer
test -f .env || cp .env.example .env
cd ..
mkdir -p resources/documents resources/news resources/media resources/references
```

You are now in `Video-Gen-Test/`. The root environment remains active.

OpenMontage's `.env` holds optional production-provider keys; it is separate from OpenCode's model login. Piper narration needs a downloaded voice model as well as the Python package. Ask OpenCode to check the voice model for your chosen language, subtitle fonts, and rendering prerequisites before production. A workflow may also need a browser download, HyperFrames runtime, or additional provider dependencies; follow the checked-out upstream guidance when these are needed.

## 5. Install OpenCode

From `Video-Gen-Test/`:

```bash
npm install -g opencode-ai
opencode --version
```

The executable is installed globally; always launch it with `Video-Gen-Test/` as the working directory. These guides use the OpenCode 1 CLI and `opencode web`. If another OpenCode version is already installed, check its documentation before replacing the shared executable.

The existing `opencode.json` loads the OpenMontage instructions. Keep that file in this directory; no configuration creation or `/init` step is needed. If it is absent from your checkout, obtain the existing file from the team. Global OpenCode configuration may also apply.

Continue with [Create a video](CREATE_VIDEO.md) to launch OpenCode, connect if needed, and select **OpenCode Zen → Big Pickle**.

Setup is based on the [OpenMontage source](https://github.com/calesthio/OpenMontage), its [setup commands](https://github.com/calesthio/OpenMontage/blob/main/Makefile), and [OpenCode installation documentation](https://opencode.ai/docs/). Installation and rendering have not been run as part of this documentation edit.
