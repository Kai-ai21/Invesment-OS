/**
 * The "(11)" after a section heading.
 *
 * ⚠️ RENDERS NOTHING AT ZERO, which is the entire reason this is a component
 * rather than an interpolation. "Evidence (0)" states an absence twice — once as
 * a number a reader has to parse, and again in the empty state directly below it
 * that says the same thing in words and offers something to do about it. The
 * count earns its place when there is a quantity worth knowing before you scroll.
 *
 * Tabular so a count changing from 9 to 10 doesn't nudge the heading's width.
 */
export function Count({ value }: { value: number }) {
  if (value <= 0) return null

  return (
    <>
      {' '}
      <span className="font-normal tabular-nums text-text-muted">({value})</span>
    </>
  )
}
