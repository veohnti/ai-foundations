type Props = {
  /** Height of the mark in px; the wordmark scales with it. */
  size?: number
  /** Show "Campus Customs" next to the mark. */
  withWordmark?: boolean
}

// Each C is an arc of radius 13 with its opening on the right (from -42° to
// +42°). The second C is shifted right so the two interlock; it's drawn with
// mix-blend-mode: multiply, so where pink and green cross they deepen to near
// black, the fourth color of the palette.
const R = 13
const A = (42 * Math.PI) / 180
const arc = (cx: number, cy: number) =>
  `M ${cx + R * Math.cos(A)} ${cy - R * Math.sin(A)} A ${R} ${R} 0 1 0 ${cx + R * Math.cos(A)} ${cy + R * Math.sin(A)}`

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg
      className="logo-mark"
      width={(size * 50) / 40}
      height={size}
      viewBox="0 0 50 40"
      role="img"
      aria-label="Campus Customs logo"
    >
      <path d={arc(18, 20)} fill="none" stroke="var(--pink)" strokeWidth="6.5" strokeLinecap="round" />
      <path
        d={arc(31, 20)}
        fill="none"
        stroke="var(--green)"
        strokeWidth="6.5"
        strokeLinecap="round"
        style={{ mixBlendMode: 'multiply' }}
      />
    </svg>
  )
}

export default function Logo({ size = 34, withWordmark = true }: Props) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      {withWordmark && (
        <span className="logo-word">
          Campus <em>Customs</em>
        </span>
      )}
    </span>
  )
}
