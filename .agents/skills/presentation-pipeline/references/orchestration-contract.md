# Presentation pipeline orchestration contract

Контракт состояния: `presentation-pipeline-session/1.0`.

## Порядок

```text
context → references → style-kit → build → complete
```

Статусы этапа:

- `pending` — этап ещё не начат;
- `active` — идёт Q&A или производство;
- `review` — артефакт создан и ожидает решения пользователя;
- `approved` — артефакт утверждён и валиден;
- `skipped` — пользователь отдельно подтвердил пропуск;
- `blocked` — продолжение невозможно без входа или решения.

Терминальные статусы этапа: `approved`, `skipped`. Этап справа не может стать `active`, `review` или `approved`, пока все этапы слева не терминальны.

## Контракты артефактов

| Stage ID | Skill | Artifact contract | Location kind |
|---|---|---|---|
| `context` | `context-plan-skill` | `presentation-blueprint/1.2` | file |
| `references` | `references-to-visual` | `visual-style-brief/1.2` | file |
| `style-kit` | `presentation-style-kit` | `presentation-visual-dna/1.2` | directory; entrypoint `visual-dna-manifest.json` |
| `build` | `branding-visual-skill` | `presentation-build/1.2` | directory; entrypoint `build-manifest.json` |

SHA-256 считается для файла либо canonical entrypoint каталога. После изменения upstream-файла все зависимые downstream-этапы возвращаются минимум в `review` и повторно валидируются.

## Skip record

`skipped` требует:

- причину запроса;
- непустой список последствий;
- текст отдельного вопроса о подтверждении;
- `confirmed: true`;
- автора и ISO date-time подтверждения.

Если вместо этапа дан совместимый внешний артефакт, сохрани его как `replacementArtifact`. Он не превращает пропуск в обычное прохождение, но даёт downstream-этапу проверяемый вход.

## Ownership

Оркестратор не переписывает профессиональные правила дочерних навыков. Он отвечает только за последовательность, вопросы, состояние, подтверждения, хеши и запуск валидаторов.
