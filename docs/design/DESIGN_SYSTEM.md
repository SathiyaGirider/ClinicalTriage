# LifeLine Clinical Design System (Phase 1 Specification)

**Project:** LifeLine OPD Web Application  
**Stitch Project ID:** `746745182743364092`  
**Compliance Standard:** WCAG 2.2 Level AA Contrast & Accessibility Standards  
**Aesthetic Philosophy:** Calm, trustworthy, and functional clinical software. Built for high-volume hospital outpatient departments (OPD). Dense and scannable for clinical staff; calm, reassuring, and effortless for patients.

---

## 1. Core Principles

1. **Strictly Neutral Surfaces:** Off-whites, slate grays, and clear dividers. No gradients, glassmorphism, glowing shadows, or marketing flair.
2. **Clinical Color Reservation:**
   - **Primary Action (Calm Blue `#0369a1`):** Navigation, primary buttons, interactive selection chips, active tabs.
   - **Emergency (Red `#991b1b` / `#dc2626` / `#fef2f2`):** Strictly reserved for triage level Emergency, life-threatening symptoms, or immediate ER transfers.
   - **Urgent / Flagged (Amber `#92400e` / `#d97706` / `#fffbeb`):** Strictly reserved for same-day priority, nurse attention flags, and worsening symptoms.
   - **Routine / Normal (Green `#166534` / `#16a34a` / `#f0fdf4`):** Strictly reserved for stable routine status, normal vitals, and completed encounters.
   - **Rule:** Every clinical status color must be accompanied by both a visible text label and a clinical icon. Color is never the sole indicator.
3. **Typography Scale:**
   - Single font family: **Inter** (with native Tamil fallback `Noto Sans Tamil`).
   - Patient view base: `18px` with generous line-height (`1.5`) and minimum `48px` tap targets.
   - Staff view base (Nurse/Doctor): `15px` to `16px` for high-density tabular scannability and `36px` action targets.
4. **Spacing & Elevation Grid:**
   - Strict 8px modular grid (`4px`, `8px`, `12px`, `16px`, `24px`, `32px`, `40px`).
   - Radius: 4px for buttons, chips, and table cells; 6px for cards and dialogs; 8px for major panels.
   - Near-zero shadows: Subtitle elevation `0 1px 2px 0 rgba(15, 23, 42, 0.05)` and slide-over drawer shadow `-4px 0 16px rgba(15, 23, 42, 0.1)`.

---

## 2. Token Definitions (`frontend/src/shared/theme.css`)

```css
:root {
  /* Surfaces */
  --surface-page: #f8fafc;
  --surface-card: #ffffff;
  --surface-muted: #f1f5f9;
  --surface-subtle: #e2e8f0;

  /* Ink / Typography */
  --ink-primary: #0f172a;     /* 14.8:1 contrast on white */
  --ink-secondary: #334155;   /* 9.7:1 contrast on white */
  --ink-muted: #64748b;       /* 4.8:1 contrast on white (WCAG AA pass) */
  --ink-inverted: #ffffff;

  /* Borders */
  --border-subtle: #e2e8f0;
  --border-strong: #cbd5e1;
  --border-focus: #0284c7;

  /* Primary Brand / Action */
  --primary: #0369a1;         /* 5.9:1 contrast against white */
  --primary-hover: #075985;
  --primary-active: #0c4a6e;
  --primary-subtle: #f0f9ff;
  --primary-border: #bae6fd;
  --primary-ink: #ffffff;

  /* Clinical Emergency (Red) */
  --status-emergency-bg: #fef2f2;
  --status-emergency-border: #fca5a5;
  --status-emergency-ink: #991b1b;
  --status-emergency-solid: #dc2626;

  /* Clinical Urgent / Same-Day (Amber) */
  --status-urgent-bg: #fffbeb;
  --status-urgent-border: #fcd34d;
  --status-urgent-ink: #92400e;
  --status-urgent-solid: #d97706;

  /* Clinical Routine / Normal (Green) */
  --status-routine-bg: #f0fdf4;
  --status-routine-border: #86efac;
  --status-routine-ink: #166534;
  --status-routine-solid: #16a34a;

  /* Spacing Grid (8px) */
  --space-0-5: 4px;
  --space-1: 8px;
  --space-1-5: 12px;
  --space-2: 16px;
  --space-3: 24px;
  --space-4: 32px;
  --space-5: 40px;

  /* Radius & Shadows */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --shadow-none: none;
  --shadow-subtle: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
  --shadow-drawer: -4px 0 16px rgba(15, 23, 42, 0.1);

  /* Typography */
  --font-stack: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Tamil", sans-serif;
  --font-size-base: 18px;
  --font-size-staff: 15px;

  /* Touch Targets */
  --tap-min: 48px;
  --tap-min-staff: 36px;
}
```

---

## 3. UI Component Specifications (`frontend/src/shared/ui/`)

1. **Button:**
   - Variants: `primary`, `secondary`, `outline`, `ghost`, `danger`, `warn`.
   - Sizes: `default` (44-48px min height), `small` (36px for dense staff tables).
   - States: Active, Hover, Focus (accessible 2px solid ring with 2px offset), Disabled, Busy/Loading spinner.
2. **Field & Input / Textarea:**
   - Semantic `<label>` with `<span className="label-text">`.
   - Support for `error` prop with `aria-invalid="true"` and `aria-describedby="{id}-error"`.
   - Built-in character counters where maximum lengths exist (e.g., 2000 chars on notes).
3. **Select:**
   - High-contrast custom or native select with explicit accessible focus ring and clear options.
4. **Chip & Tag:**
   - Toggleable and static pills.
   - Status chips: `emergency`, `urgent`, `routine`, `neutral`. Always accompanied by an SVG icon.
5. **Table:**
   - Dense, scannable tabular display with sticky headers, subtle alternating zebra row highlights, right-aligned numbers, and accessible ARIA column headers.
6. **Drawer (Slide-Over Panel):**
   - Accessible modal drawer with backdrop, focus trap, Escape key dismiss, and `aria-modal="true"`. Used for Nurse Patient Drawer and Walk-in Check-in.
7. **Dialog (Modal Confirmation):**
   - Replaces blocking browser `window.confirm` and `window.prompt`.
   - Focus traps to input/confirm button; accessible title (`aria-labelledby`) and description (`aria-describedby`).
8. **Tabs:**
   - Accessible `role="tablist"` with `aria-selected` and keyboard arrow-key navigation.
9. **Banner:**
   - Top-level sticky disclaimers for synthetic demo data and ICMR-aligned AI decision support notices.
10. **Skeleton & EmptyState:**
    - High contrast empty states with descriptive messages (e.g. "No patients waiting yet. New arrivals will appear here automatically.") and optional action buttons.
11. **Toast Notification:**
    - Non-intrusive bottom-right status announcements (e.g. "Vitals saved", "Token issued") with `role="status"` live region.
