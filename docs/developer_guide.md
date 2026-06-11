# Developer Guide for VR4Mice 🎉

## Goverance 

This repository is maintained by the Mathis Lab. 

### Core Development Team

- @maryapp is the core developer of the datajoint pipelines 💻
- @mmathislab is the SC member (steering council) 🦄
- @CeliaBenquet is actively developing analysis code
- @tomsains is actively developing analysis code

This codebase uses a “consensus seeking” process for making decisions. The group tries to find a resolution that has no open objections among core developers. Core developers are expected to distinguish between fundamental objections to a proposal and minor perceived flaws that they can live with, and not hold up the decision-making process for the latter. If no option can be found without objections, the decision is escalated to the SC, which will itself use consensus seeking to come to a resolution. In the unlikely event that there is still a deadlock, the proposal will move forward if it has the support of a simple majority of the SC.

Decisions (in addition to adding core developers and SC membership as above) are made according to the following rules:

- Minor documentation changes, such as typo fixes, or addition / correction of a sentence, require approval by a core developer and no disagreement or requested changes by a core developer on the issue or pull request page (lazy consensus). Core developers are expected to give “reasonable time” to others to give their opinion on the pull request if they’re not confident others would agree.

- Code changes and major documentation changes require agreement by one core developer and no disagreement or requested changes by a core developer on the issue or pull-request page (lazy consensus). For all changes of this type, core developers are expected to give “reasonable time” after approval and before merging for others to weigh in on the pull request in its final state.

- Changes to the **API principles require a dedicated issue** on our issue tracker and follow the decision-making process outlined above.

- Changes to this **governance model or our mission, vision, and values** require a dedicated issue on our issue tracker and follow the decision-making process outlined above, unless there is unanimous agreement from core developers on the change in which case it can move forward faster.

- If an objection is raised on a lazy consensus, the proposer can appeal to the community and core developers and the change can be approved or rejected by escalating to the SC.

## Code style

### Style Guide
We use the [Google style guidelines](https://google.github.io/styleguide/). Developers are highly encouraged to have a look at it from time to time. Note that formatting will be enforced by running `black` and `isort`. 

Some rules of interest included in the Google guidelines are:
- Import each module using the full pathname location of the module.
- Follow standard typographic rules for the use of spaces around punctuation.
- Function names, variable names, and filenames should be descriptive; avoid abbreviation. 

### Use Black
Ensure all Python code is formatted with Black before committing (current version 22.6). Black enforces consistency and removes debates over code style. Use the default settings. Command: `black .` (to run in current folder).

### Use isort
Sort your imports to keep them organized. isort should be used to handle import ordering, grouping standard library, third-party, and project-specific imports. Command: `isort .` (to run in current folder).

### Docstrings
All public methods and functions should have docstrings using the [PEP 257 format](https://peps.python.org/pep-0257/). Briefly describe what the function does, its parameters, and return values and add any information that could help your collaborators or future users to understand your code faster.

### Type Annotations
Use type hints to make the code more readable and to help with catching potential bugs early.

### Inline comments
- Use inline comments to explain non-obvious code logic or important context. Make sure they are clear and concise. Avoid comments that state the obvious, as they clutter the code. 
- When using TODO or NOTE comments, always include the name of the person responsible for addressing it (e.g., TODO(username): Refactor this section). From Google style guidelines, TODO comments are for code that is temporary, a short-term solution, or good-enough but not perfect. Provide enough context for the TODO or NOTE to be actionable. Avoid vague comments like "TODO: fix this". Instead, specify what needs to be fixed and why. Do not leave TODO or NOTE comments unresolved in the codebase if they are unclear or outdated. Regularly review and address them to maintain code quality. 

### Jupyter notebooks (`nbstripout`)

Do **not** commit notebook **outputs** (they often contain DB hostnames, connection logs, or local paths).

After cloning, enable the repo filter once:

```bash
pip install -r dj_pipeline/requirements-dev.txt
nbstripout --install --attributes .gitattributes
```

Strip all notebooks manually before a PR if needed:

```bash
find dj_pipeline mouse_task -name '*.ipynb' -exec nbstripout {} +
```

Never commit `.env`, `.env.compose`, `.env-aws`, or any rig-specific GUI config overrides (e.g., your locally edited `gui_transfer/config/config.json`; create it by copying `local_config.json.example`).

CI runs `.github/workflows/security.yml` on PRs to main: **gitleaks**, **nbstripout --verify**, blocklisted tracked files, and internal host pattern checks.

## GitHub Branching, Commits, & Other Guidelines

### Branching Model
- Use the GitHub Flow: Create a branch for every feature or bug fix. **1 feature = 1 branch = 1 PR**.
- Merging Dependent Branches: when multiple branches depend on each other (e.g., branch A is foundational, and branch B adds missing elements such as fixes, DJ integration, or tests), always **merge the first branch (branch A) into main** before merging branch B (either to main, once branch A is merged or to branch A). This approach maintains a clear history, simplifies the review process (by focusing reviews on incremental additional changes) making it more efficient, and minimizes merge conflicts.
- Keep the main branch always deployable. Only merge into main when the feature is complete, fully tested, and reviewed.
- Use descriptive branch names to indicate the purpose of the branch.

### Commit Messages
Write Clear, Concise Commit Messages: Follow the conventional commit style. Break down commits into small, meaningful changes, preferably addressing only one thing per commit.

### Pull Requests
- All changes must go through a pull request (PR), even minor changes.
- Include a summary of what the PR does, and link to the issue it resolves (if any) as soon as you open the PR (even if it is still WIP).
- PRs should include unit tests where applicable, and **pass all CI checks** before merging.

### Code Reviews
- Every PR should be reviewed by at least one other core developer. If the PR was open by one of the core developers, they should ask for a review from at least one of the members of the development team based on their expertise.
- Address all comments before merging. **No conversation should be left open.**