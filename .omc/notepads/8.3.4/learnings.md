# Learnings: Calendar Infinite Scroll (Plan 8.3.4)

## Implementation Summary

Successfully replaced prev/next navigation with IntersectionObserver-based infinite scroll for the calendar view.

## Technical Patterns

### 1. useInfiniteCalendar Hook
- Manages array of month objects with `{ year, month, data, loading, error }` structure
- Starts with 3 months (prev, current, next) for immediate viewport coverage
- Uses Set-based loading tracker (`loadingRef.current`) to prevent duplicate API calls
- Caps at 24 months in DOM, trimming from opposite end when exceeded
- Separate state management for active month tracking

### 2. IntersectionObserver Pattern
- **Three observers** used:
  1. Top sentinel: Triggers `loadOlder()` when scrolling up
  2. Bottom sentinel: Triggers `loadNewer()` when scrolling down (up to current month)
  3. Sticky headers: Tracks which month is currently visible for navigation title
- Threshold of 0.1 provides smooth loading experience
- Observers properly disconnected in cleanup to prevent memory leaks

### 3. Sticky Headers
- `position: sticky; top: 0; z-index: 5`
- Backdrop blur for glass-morphism effect
- Data attributes (`data-year`, `data-month`) for observer tracking
- Each month section has unique ID (`month-YYYY-MM`) for scroll targeting

### 4. State Management Pattern
```typescript
// Wrapper function for typed setState
const setActiveMonth = useCallback((year: number, month: number) => {
  setActiveMonthState({ year, month });
}, []);
```
This pattern allows exposing a typed function interface while using React's setState internally.

## CSS Architecture

### Key Classes
- `.calendar-scroll-container`: Fixed height container with `overflow-y: auto`
- `.calendar-month-section`: Individual month wrapper
- `.calendar-month-sticky-header`: Sticky positioned with backdrop blur
- `.calendar-sentinel`: Invisible 1px divs for intersection detection

### Height Calculation
```css
height: calc(100vh - var(--topbar-height, 60px) - 200px);
```
Accounts for page header and navigation controls.

## Component Reuse
- `MonthView.tsx`: Unchanged, receives `CalendarMonth` data
- `DayCell.tsx`: Unchanged, renders individual day cells
- `WeeklySummary.tsx`: Unchanged, renders weekly summary sidebar
- Only `CalendarNavigation.tsx` modified to show active month + Today button

## Performance Considerations

### Fetch Optimization
- Loading state prevents duplicate fetches via `loadingRef` Set
- Each month fetches independently, no blocking
- Failed months show error without blocking other months

### DOM Management
- 24-month cap prevents unbounded growth
- Trim strategy: Remove from opposite end of scroll direction
- Virtual scrolling not needed due to cap

### Future Months Prevention
```typescript
if (
  newerMonth.year > currentYear ||
  (newerMonth.year === currentYear && newerMonth.month > currentMonth)
) {
  return prev; // Don't load future months
}
```

## TypeScript Patterns

### Function Signature Mismatch Resolution
When exposing setState as a custom function:
```typescript
// Wrong: Direct exposure causes type mismatch
setActiveMonth: Dispatch<SetStateAction<...>>

// Right: Wrapper function with explicit signature
const setActiveMonth = useCallback((year: number, month: number) => {
  setActiveMonthState({ year, month });
}, []);
```

## Smooth Scroll
- `scroll-behavior: smooth` on container
- `scrollIntoView({ behavior: 'smooth', block: 'start' })` for Today button
- Month ID format: `month-YYYY-MM` for reliable targeting
