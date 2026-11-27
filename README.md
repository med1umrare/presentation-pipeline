# Presentation Pipeline для Codex

Скилл ведёт работу над презентацией в одном чате. Codex помогает продумать содержание, выбрать визуальное направление, оформить правила стиля и собрать презентацию с проверками. Вы утверждаете результат каждого этапа перед переходом к следующему.

## Установка для участников курса

1. Примите приглашение в репозиторий и войдите в GitHub под приглашённым аккаунтом. В репозитории нажмите **Code → Download ZIP** и распакуйте архив.
2. Откройте в Codex распакованную папку `presentation-pipeline-main`, в которой лежит этот README. Пять скиллов уже находятся в её папке `.agents/skills`. Если хотите использовать свой проект, скопируйте в его `.agents/skills` все пять папок скиллов.
3. В новом чате Codex введите `$` и выберите **presentation-pipeline**. Если скилл не появился, перезапустите Codex и снова откройте папку проекта.

Прикрепите материалы и отправьте первый запрос.

> Помоги подготовить презентацию на основе этих материалов. Начни с плана и проведи меня по этапам.

Для запуска проверок нужен **Python 3.10 или новее**. Для встроенного рендерера диаграмм в PPTX также понадобятся **Node.js и npm**. Для просмотра и проверки готовых слайдов подойдёт PowerPoint или LibreOffice.

[Справка OpenAI о скиллах Codex](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

## Состав комплекта

- [presentation-pipeline](.agents/skills/presentation-pipeline/SKILL.md) ведёт диалог, сохраняет состояние и запрашивает подтверждение переходов.
- [context-plan-skill](.agents/skills/context-plan-skill/SKILL.md) готовит план презентации.
- [references-to-visual](.agents/skills/references-to-visual/SKILL.md) формулирует визуальное направление по референсам.
- [presentation-style-kit](.agents/skills/presentation-style-kit/SKILL.md) собирает переиспользуемые правила стиля.
- [branding-visual-skill](.agents/skills/branding-visual-skill/SKILL.md) собирает презентацию и проверяет готовые материалы.
