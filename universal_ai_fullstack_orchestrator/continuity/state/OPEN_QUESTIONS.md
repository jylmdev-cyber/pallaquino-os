# Open questions

- Q-1 (owner decision): GIT_AUTHORSHIP_POLICY requires `jimdev <jylmdev@gmail.com>` in every repository, including adopting projects and contributor forks, while CONTRIBUTING.md asks contributors to set their own identity. Should the expected identity be configurable per project? Controlling rule until decided: existing policy (validator unchanged; tests isolate it).
- Q-2 (owner decision): the AI tool used for PAL-005 suggested an AI `Co-Authored-By` trailer; repository policy forbids it and the hook and validator reject it. Repository policy was applied. Confirm the prohibition stays.
- Q-3 (approval): merge branch `claude/pallaquino-engineering-os-c7d622`, create tag `v0.3.0` and publish the GitHub Release. Not performed.
