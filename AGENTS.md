# Repository Guidelines

## Project Structure & Module Organization
This repository contains product prompts in `md/` and the runnable frontend app in `frontend/`. Main application code lives in `frontend/src/`:

- `components/` for UI, grouped by feature (`auth/`, `chat/`, `layout/`, `preview/`)
- `stores/` for Zustand state (`authStore.js`, `chatStore.js`)
- `mocks/` and `public/mockServiceWorker.js` for MSW-backed local API mocking
- `assets/` for bundled images and icons

Keep new feature code close to the relevant domain folder. Prefer small JSX modules over large multi-purpose files.

## Build, Test, and Development Commands
Run commands from `frontend/`.

- `npm install` installs dependencies
- `npm run dev` starts the Vite dev server with MSW enabled in development
- `npm run build` creates a production bundle in `frontend/dist`
- `npm run preview` serves the production build locally
- `npm run lint` runs ESLint on all `js` and `jsx` files

## Coding Style & Naming Conventions
The codebase uses ES modules, React function components, and Zustand stores. Follow the existing style:

- 2-space indentation and semicolon-free JavaScript
- Component files in PascalCase, for example `ChatPanel.jsx`
- Store files in camelCase ending with `Store.js`
- Use relative imports within `src/`

Linting is configured in `frontend/eslint.config.js` with `@eslint/js`, `eslint-plugin-react-hooks`, and `eslint-plugin-react-refresh`. Run `npm run lint` before opening a PR.

## Testing Guidelines
There is no automated test framework configured yet. For now, verify changes with:

- `npm run lint`
- `npm run build`
- manual flows in `frontend/TODO.md` such as login, chat streaming, source preview, and logout

If you add tests, place them under `frontend/src/` next to the feature they cover and document the command in `frontend/package.json`.

## Commit & Pull Request Guidelines
Git history currently starts with a single subject-style commit: `Initial commit: ...`. Keep commit messages short, imperative, and descriptive, for example `Add preview loading state`.

PRs should include a clear summary, impacted paths, manual verification steps, and screenshots or short recordings for UI changes. Link related issues or task docs when available.
