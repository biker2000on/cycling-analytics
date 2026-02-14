# Architectural Decisions: Calendar Infinite Scroll

## Decision 1: Hook-Based State Management
**Choice:** Custom `useInfiniteCalendar` hook instead of component-level state

**Rationale:**
- Separates infinite scroll logic from UI concerns
- Reusable if calendar needs to be used elsewhere
- Easier to test month loading logic independently
- Cleaner CalendarPage component focused on rendering

## Decision 2: 24-Month DOM Cap
**Choice:** Hard limit of 24 months in DOM, trim from opposite end

**Rationale:**
- 24 months = 2 years of data (reasonable for most use cases)
- Prevents unbounded memory growth from excessive scrolling
- Virtual scrolling adds complexity without significant benefit at this scale
- Trimming from opposite end maintains natural scroll feel

**Alternatives Considered:**
- Virtual scrolling: Too complex for 24-item list
- Unbounded: Risk of performance degradation
- 12-month cap: Too restrictive for year-over-year analysis

## Decision 3: Three IntersectionObservers
**Choice:** Separate observers for top sentinel, bottom sentinel, and sticky headers

**Rationale:**
- Top/bottom sentinels have different callbacks (loadOlder vs loadNewer)
- Sticky header observer needs different options (root: container)
- Clearer separation of concerns vs. single multi-purpose observer

## Decision 4: Initial 3-Month Load
**Choice:** Start with previous month, current month, next month

**Rationale:**
- Immediate viewport coverage without empty scroll area
- Balanced approach: Not too eager (loading many months), not too lazy (single month)
- Allows both upward and downward scroll immediately

**Alternatives Considered:**
- Single month: Requires scroll before seeing context
- 5 months: Unnecessary API calls on page load

## Decision 5: No Future Months
**Choice:** Block loading months beyond current month

**Rationale:**
- Calendar shows historical training data
- Future months have no meaningful data
- Prevents confusion from empty future months
- Matches user mental model (calendar ends at "now")

## Decision 6: Sticky Headers for Active Month
**Choice:** Use IntersectionObserver on sticky headers vs. scroll position calculation

**Rationale:**
- Browser handles intersection detection efficiently
- No manual scroll position math required
- Works correctly with variable-height month sections
- Automatically handles edge cases (partial visibility)

**Alternatives Considered:**
- Scroll listener + position calculation: More fragile, performance overhead
- Fixed active month: Doesn't reflect actual viewport state

## Decision 7: Data Attributes for Year/Month
**Choice:** Use `data-year` and `data-month` on sticky headers

**Rationale:**
- Clean way to pass metadata to intersection observer callback
- No need for complex element-to-month mapping
- Standard HTML5 pattern for custom metadata

## Decision 8: Preserve Existing Components
**Choice:** Keep MonthView, DayCell, WeeklySummary unchanged

**Rationale:**
- Single Responsibility Principle: These components render a month, not scroll logic
- Existing components are well-tested and working
- Easier to reason about change scope
- Reduces risk of introducing bugs in unrelated functionality

## Decision 9: Background Fetch Pattern
**Choice:** Set loading state immediately, fetch in useEffect with dependency on months array

**Rationale:**
- UI responds instantly to scroll (shows loading state)
- Prevents race conditions with Set-based deduplication
- useEffect auto-triggers when new months added to array
- Clean separation: month addition vs. data fetching

## Decision 10: Error Handling Per Month
**Choice:** Show errors inline per month section, don't block other months

**Rationale:**
- Network issues may be transient or specific to one month
- User can still interact with successfully loaded months
- Clear feedback about which specific month failed
- Retry opportunity on next scroll past that month
