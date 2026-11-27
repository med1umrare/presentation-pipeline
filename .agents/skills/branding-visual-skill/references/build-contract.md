# Presentation build contract

Версия контракта: `presentation-build/1.2`. Сборки `1.1` считаются legacy и принимаются валидатором с предупреждением.

```text
presentation-build/
├── README.md
├── build-manifest.json
├── dna-adapter.json           # only when source DNA uses another contract
├── sources.md
├── format-fallbacks.md
├── qa-report.md
├── source/
│   ├── charts/                # *.chart.json, only when the deck has data charts
│   └── data/                  # CSV for the charts
├── output/
└── renders/
```

## build-manifest.json

Include:

- `artifactType: presentation-build`;
- `contract: presentation-build/1.2`;
- `schemaVersion: 1.2`;
- `status: draft | review | approved`;
- `builderVersion`;
- `createdAt`;
- `buildMode: pipeline | one-off`;
- input paths/URLs, контракты, schemaVersion и SHA-256;
- target formats and aspect ratios;
- DNA role mapping;
- font substitutions;
- synthetic/modelled data flags;
- output files;
- `charts`: one entry per chart spec — `chartId`, `location`, `contract: presentation-chart-spec/1.0`, SHA-256;
- status of semantic, visual and technical QA, plus `qa.data` when `charts` is not empty.

Используй [JSON Schema](build-manifest.schema.json). Pipeline mode требует утверждённые `presentation-blueprint/1.2` и `presentation-visual-dna/1.2`. One-off mode требует Blueprint и утверждённый Style Brief, а также `withoutReusableDna: true`. Каждый локальный вход обязан иметь существующий путь и совпадающий SHA-256; не полагайся на историю чата.

## source/

Editable source: HTML/CSS/JS, presentation module, data JSON, assets and formulas. Do not store credentials or private source-system exports.

### source/charts/ и source/data/

Графики данных описываются по [контракту chart-spec](chart-spec.schema.json) и [каталогу](chart-catalog.md). `data.location` в спецификации указывается относительно `source/`, например `data/revenue.csv`. Спецификация хранит SHA-256 своего CSV, а manifest — SHA-256 спецификации, поэтому изменение любого числа обнаруживается финальным валидатором.

## output/

Final HTML, site build, PPTX, PDF or other user-facing files.

## renders/

All slides for static decks and the essential states for interactive artifacts: empty/default, changed inputs, validation/error where relevant, and result state.

## sources.md

Для каждого видимого утверждения или ассета укажи source ID, путь/URL, владельца, статус проверки и разрешённое использование. Отдельно пометь synthetic и modelled data.

## qa-report.md

Используй три раздела: semantic, visual и technical; при наличии графиков — четвёртый раздел data. Для каждой проверки укажи `pass`, `fail`, `warning` или `not-applicable`, доказательство проверки и оставшееся действие. Следуй [QA-шаблону](qa-report-template.md).

Статус `approved` разрешён только при `pass` во всех секциях (включая `data`, если есть графики), пустом `reviewBlockers` и заполненном `approval`.

## format-fallbacks.md

For every behavior that cannot survive export, record:

- original behavior;
- target-format replacement;
- user-visible limitation;
- verification status.
