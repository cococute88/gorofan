---
inclusion: always
---

# Windows / Kiro Shell 실행 규칙

이 프로젝트는 Windows 환경에서 Kiro IDE를 사용한다.

Shell tool 실행 시 다음 규칙을 항상 준수한다.

- 여러 shell command를 `;`, `&&`, `||`로 한 줄에 연결하지 않는다.
- pipe(`|`)를 사용해 여러 명령을 연결하지 않는다.
- 한 tool call에는 하나의 shell command만 실행한다.
- Git 조회 명령은 반드시 각각 별도의 tool call로 실행한다.

예:

허용:
- `git status`
- `git branch --show-current`
- `git log --oneline -5`
- `git diff`
- `git stash list`

금지:
- `git status; git branch --show-current; git log --oneline -5`
- `git status && git diff`

추가 규칙:

- `git *` 전체 trust/permission 허용을 사용자에게 요구하지 않는다.
- read-only Git 명령은 가능한 한 단독 명령으로 실행한다.
- `git reset`, `git clean`, `git rebase`, destructive checkout 등 작업을 덮어쓰거나 삭제할 수 있는 Git 명령은 사용자 명시 승인 없이 실행하지 않는다.
- 기존 stash를 사용자 명시 승인 없이 apply/pop/drop하지 않는다.
- 로컬 사용자 DB를 사용자 명시 승인 없이 수정하거나 migration하지 않는다.
- Windows PowerShell에서 heredoc이나 Unix shell 전용 문법을 사용하지 않는다.
- PowerShell에 맞는 명령을 사용한다.