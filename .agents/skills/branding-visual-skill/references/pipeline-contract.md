# Presentation pipeline contract

Текущая линия совместимости: `1.2`.

```text
context-plan-skill
  presentation-blueprint/1.2
        ↓
references-to-visual (pipeline mode)
  visual-style-brief/1.2 + Blueprint SHA-256
        ↓
presentation-style-kit
  presentation-visual-dna/1.2 + Style Brief SHA-256
        ↓
branding-visual-skill (pipeline mode)
  presentation-build/1.2 + Blueprint/DNA SHA-256
```

## Gates

1. Каждый этап сохраняет машинный JSON-артефакт; Markdown не заменяет контракт.
2. Следующий этап принимает upstream-файл по `location`, проверяет `contract`, `schemaVersion`, `status` и SHA-256.
3. `approved` требует явного владельца, времени утверждения, пройденных критериев и отсутствия блокеров.
4. Сборка в `pipeline` mode требует утверждённые Blueprint и Visual DNA.
5. Сборка в `one-off` mode может использовать утверждённый Style Brief вместо DNA, но обязана установить `withoutReusableDna: true`.
6. Контракты `1.1` разрешены только как legacy-входы с предупреждением. Новые материалы курса создаются по `1.2`.
7. Графики данных — необязательное расширение линии `1.2`: `datasets` и `visualizationMap[].chartType` в Blueprint, раздел `dataviz` в токенах Visual DNA, `charts` и `qa.data` в build manifest. Каждый график описывается отдельным контрактом `presentation-chart-spec/1.0`, который хранит SHA-256 своих данных; manifest хранит SHA-256 спецификации.

## Ownership

- Blueprint владеет смыслом, доказательствами, маршрутом и действием аудитории.
- Style Brief владеет интерпретацией референсов и правилами направления.
- Visual DNA владеет переносимыми визуальными ролями, токенами, примерами и provenance.
- Presentation Build владеет реализацией, форматными заменами, рендерами и QA, включая chart-spec и Data QA.
- Тип графика и набор данных выбирает Blueprint; цветовые роли графиков — Visual DNA; кодирование, подписи и отрисовку — Presentation Build.

Нижестоящий этап не изменяет upstream-артефакт молча. Любая корректировка получает новый файл, новый SHA-256 и соответствующий статус.
