# @flowra/brand-kit

The single source of truth for FLOWRA Suite design, security, and legal standards.
Every product under the FLOWRA umbrella (`flowralive.in`) imports from this kit.

## What's in here

```
brand-kit/
├── tokens.css                 # CSS variables — colors, fonts, spacing, radius
├── tailwind-preset.js         # Tailwind config preset (extends defaults)
├── components/
│   ├── Header.jsx             # Top navbar (logo + tool switcher + CTA)
│   ├── Footer.jsx             # Universal footer (links, copyright, social)
│   ├── ToolCard.jsx           # Marketing tool-grid card
│   ├── Button.jsx             # Primary/secondary/ghost buttons
│   └── Section.jsx            # Spacing-controlled section wrapper
├── docs/
│   ├── security-checklist.md  # Mandatory security baseline for every FLOWRA app
│   ├── design-principles.md   # Layout, motion, typography rules
│   └── voice-and-tone.md      # Copy guidelines
├── legal/
│   ├── privacy-template.md    # DPDP Act 2023 compliant privacy policy
│   └── terms-template.md      # Standard terms of service
└── assets/
    ├── flowra-logo.svg        # Master vector logo
    └── favicon.svg
```

## Usage in a React app

```bash
# In any FLOWRA product repo:
yarn add @flowra/brand-kit  # (when published; for now use file: link)
```

```js
// tailwind.config.js
module.exports = {
  presets: [require('@flowra/brand-kit/tailwind-preset')],
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
};
```

```jsx
// src/index.js
import '@flowra/brand-kit/tokens.css';

// src/App.jsx
import { Header, Footer, ToolCard } from '@flowra/brand-kit';
```

## Usage in a static HTML page

```html
<link rel="stylesheet" href="https://cdn.flowralive.in/brand-kit/tokens.css" />
```

## Versioning

Semantic versioning. Breaking changes only at major versions (e.g., 1.x → 2.x).
Each FLOWRA app pins to a major version; minor/patch updates auto-flow.

## Mandatory for every FLOWRA app

- [ ] Imports `tokens.css` (or Tailwind preset)
- [ ] Uses `<Header>` and `<Footer>` from kit
- [ ] Implements every item in `docs/security-checklist.md`
- [ ] Privacy + Terms pages copied from `legal/` and tenant-customized
