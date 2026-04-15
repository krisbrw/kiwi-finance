# Kiwi Finance Design System

## Brand Identity

### Official Logo

**IMPORTANT: The Kiwi Finance logo is defined as an SVG symbol in `_layout.html` with the ID `#kiwi-fruit`.**

#### Usage Rules:
1. **This is the ONLY kiwi image that should appear anywhere in the application**
2. **Never use emoji kiwis (🥝) or other kiwi graphics**
3. **Always reference the SVG symbol using `<use href="#kiwi-fruit"/>`**

#### Logo Definition:
```html
<symbol id="kiwi-fruit" viewBox="0 0 80 80">
  <circle cx="40" cy="40" r="38" fill="#7B5B28"/>
  <circle cx="40" cy="40" r="31" fill="#5A9C28"/>
  <circle cx="40" cy="40" r="28" fill="#7AC83A"/>
  <g fill="#1A0E05">
    <!-- Seeds pattern -->
    <ellipse cx="40" cy="24" rx="2.2" ry="5.5" transform="rotate(0 40 40)"/>
    <!-- ... additional seed ellipses at 30° intervals ... -->
  </g>
  <circle cx="40" cy="40" r="8.5" fill="#F7FFF0"/>
  <circle cx="40" cy="40" r="4" fill="#E4F5C8"/>
</symbol>
```

#### How to Use:

**Navigation (28x28px):**
```html
<svg width="28" height="28"><use href="#kiwi-fruit"/></svg>
```

**Hero/Large Display (96x96px or larger):**
```html
<svg class="about-kiwi" viewBox="0 0 80 80">
    <use href="#kiwi-fruit"/>
</svg>
```

**Footer (24x24px):**
```html
<svg width="24" height="24"><use href="#kiwi-fruit"/></svg>
```

#### Logo Colors:
- Outer brown: `#7B5B28`
- Mid green: `#5A9C28`
- Inner green: `#7AC83A`
- Seeds: `#1A0E05` (dark brown/black)
- Center highlight: `#F7FFF0` (off-white)
- Center core: `#E4F5C8` (light green)

---

## Color Palette

### Primary Colors
- **Green**: `#16a34a` (Primary brand color)
- **Green Light**: `#22c55e`
- **Green Hover**: `#15803d`
- **Green Background**: `#f0fdf4`
- **Green Text**: `#166534`
- **Green Border**: `#bbf7d0`

### Secondary Colors
- **Blue**: `#2563eb`
- **Blue Background**: `#eff6ff`
- **Purple**: `#9333ea`
- **Purple Background**: `#faf5ff`
- **Amber**: `#d97706`
- **Amber Background**: `#fffbeb`
- **Red**: `#dc2626`
- **Red Background**: `#fef2f2`
- **Red Text**: `#991b1b`

### Neutral Colors
- **Text**: `#111827` (Primary text)
- **Text Muted**: `#6b7280` (Secondary text)
- **Text Subtle**: `#9ca3af` (Tertiary text)
- **Surface**: `#ffffff` (White)
- **Border**: `#e5e7eb`
- **Background**: `#f9fafb`
- **Dark**: `#0f172a` (Footer background)

---

## Typography

### Font Family
- **Primary**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- **Monospace**: `'SF Mono', 'Fira Code', monospace` (for console/code)

### Font Weights
- Regular: `400`
- Medium: `500`
- Semibold: `600`
- Bold: `700`
- Extrabold: `800`

### Font Sizes
- Base: `14px`
- Small: `11px-13px`
- Medium: `15px-17px`
- Large: `20px-28px`
- Hero: `36px-56px` (clamp for responsive)

---

## Icons

### Icon System
All icons use SVG symbols defined in `_layout.html` and referenced via `<use href="#icon-name"/>`.

**Available Icons:**
- `icon-chart` - Analytics/Dashboard
- `icon-target` - Budget/Goals
- `icon-view` - Custom views/Grid
- `icon-book` - Education
- `icon-credit-card` - Credit cards
- `icon-info` - Information
- `icon-lock` - Security
- `icon-sync` - Synchronization
- `icon-sparkles` - Custom/Special
- `icon-lightning` - Fast/Performance
- `icon-tool` - Settings/Tools
- `icon-check` - Success/Confirmation
- `icon-globe` - Global/World
- `icon-database` - Data storage
- `icon-link` - Connection/Link
- `icon-cloud` - Cloud storage
- `icon-bank` - Banking/Financial institution
- `icon-document` - Reports/Documents
- `icon-wallet` - Money/Wallet

### Icon Usage
**Never use emojis for UI elements.** Always use SVG icons for a professional appearance.

```html
<!-- Good -->
<svg width="20" height="20"><use href="#icon-chart"/></svg>

<!-- Bad -->
<span>📊</span>
```

---

## Spacing

### Padding/Margin Scale
- `4px` - Minimal spacing
- `8px` - Small spacing
- `12px` - Medium spacing
- `16px` - Default spacing
- `24px` - Large spacing
- `32px` - Extra large spacing
- `48px` - Section spacing
- `64px` - Major section spacing
- `96px` - Page spacing

### Section Vertical Spacing
- Between sections: `56px-72px`
- Page top/bottom: `72px-96px`

---

## Border Radius

- Small: `7px-8px` (buttons, inputs)
- Medium: `10px-12px` (cards, dropdowns)
- Large: `16px-20px` (major containers)
- Pill: `100px` (badges, tags)

---

## Shadows

### Elevation Levels
```css
/* Light shadow - cards */
box-shadow: 0 1px 2px rgba(0,0,0,0.04);

/* Medium shadow - hover states */
box-shadow: 0 4px 14px rgba(0,0,0,0.06);

/* Heavy shadow - modals */
box-shadow: 0 24px 64px rgba(0,0,0,0.18);

/* Colored shadow - primary actions */
box-shadow: 0 6px 18px rgba(22,163,74,0.32);
```

---

## Animations

### Timing Functions
- Default: `ease` or `ease-out`
- Duration: `120ms-200ms` for micro-interactions
- Duration: `400ms-600ms` for page transitions

### Common Animations
```css
/* Fade up */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Fade in */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
```

---

## Components

### Buttons
- Primary: Green background, white text
- Default: White background, border, subtle shadow
- Subtle: Transparent background, border

### Cards
- White background
- 1px border (`var(--border)`)
- 12-16px border radius
- Hover: lift with shadow

### Navigation
- Sticky header
- Backdrop blur effect
- Dropdown menus with smooth transitions

---

## Responsive Breakpoints

```css
/* Tablet */
@media (max-width: 960px) { }

/* Mobile */
@media (max-width: 600px) { }
```

---

## Background Patterns

### Homepage Background
Subtle diagonal gradient rectangles in top-left:
- Green gradient: `rgba(22, 163, 74, 0.08)` to `rgba(22, 163, 74, 0.02)`
- Blue gradient: `rgba(37, 99, 235, 0.06)` to `rgba(37, 99, 235, 0.01)`
- Rotation: `-15deg` and `-20deg`
- Size: `600px x 600px` and `400px x 400px`

---

## Best Practices

1. **Consistency**: Always use design tokens (CSS variables) instead of hardcoded colors
2. **Accessibility**: Maintain WCAG AA contrast ratios (4.5:1 for text)
3. **Performance**: Use SVG symbols for icons to avoid duplicate code
4. **Responsive**: Design mobile-first, enhance for larger screens
5. **Branding**: The kiwi logo is sacred - use it consistently and never substitute
